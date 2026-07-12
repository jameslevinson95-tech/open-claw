#!/usr/bin/env python3
"""
Agent 2 Shadow A/B — Claude Fable 5 vs Gemini 3.1 Pro.

PURPOSE
    Evaluate whether swapping Agent 2's fundamental screener from Gemini 3.1 Pro
    to Claude Fable 5 (Anthropic's Mythos-class flagship, released 2026-06-09)
    would change/improve candidate selection — WITHOUT touching the live trading
    path. This is a pure OBSERVER: it re-runs Agent 2's EXACT prompt (same
    directive + screener universe + pre-fetched fundamentals + system prompt)
    against Fable, then logs Gemini's live picks and Fable's shadow picks
    side-by-side for later comparison.

    ZERO live-trade impact:
      - Never called by orchestrator's decision path.
      - Never returns into execution / Agent 3 / Agent 4.
      - Only writes to output/shadow/agent2_fable_shadow_*.json + a running log.

    Honors the hard rule ("Agent 2 uses gemini-3.1-pro-preview ONLY, no
    fallbacks") because the LIVE model is untouched — Fable runs alongside.

USAGE
    # After a normal pipeline run has produced agent2 candidates + the inputs:
    python3 agent2_shadow_fable.py run

    # Or wire it in as a fire-and-forget shadow step (see orchestrator hook note).

ROUTING
    Calls Claude Fable 5 via the local proxy (Claude Max) at 127.0.0.1:18801,
    Anthropic Messages API format. Confirmed reachable 2026-07-12.
"""

import json
import os
import sys
import time
from datetime import datetime

import requests

# Reuse Agent 2's EXACT prompt construction + schema so this is apples-to-apples.
from agent2_fundamental_screener import (
    SYSTEM_PROMPT,
    _build_research_prompt,
    prefetch_fundamental_data,
)

FABLE_MODEL = "claude-fable-5"
PROXY_URL = os.environ.get("SHADOW_PROXY_URL", "http://127.0.0.1:18801/v1/messages")
SHADOW_DIR = "output/shadow"
SHADOW_LOG = os.path.join(SHADOW_DIR, "agent2_fable_shadow_log.jsonl")
MAX_RETRIES = 3
REQUEST_TIMEOUT = 180


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (handles code fences)."""
    text = text.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip().strip("`").strip()
    # Best-effort: find outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    return json.loads(text)


def call_fable(directive: dict, screener_universe: list, fundamental_data: dict,
               held_tickers: list = None) -> dict:
    """
    Run Agent 2's task against Claude Fable 5 via the local proxy.
    Same prompt + system prompt as the live Gemini call; coerces output to the
    same candidate schema. Returns {candidates:[...], _shadow_meta:{...}} or {error}.
    """
    prompt = _build_research_prompt(directive, screener_universe, fundamental_data, held_tickers)

    # Nudge Fable to emit ONLY the strict JSON Agent 2 expects (Gemini gets this
    # via responseSchema; Anthropic has no responseSchema, so we instruct + parse).
    schema_nudge = (
        "\n\nOUTPUT REQUIREMENT: Respond with ONLY a single JSON object, no prose, "
        "no markdown fences. Shape:\n"
        '{"agent":"fundamental_screener","candidates":[{"ticker":"SYM",'
        '"conviction_tier":"PASS|STRONG|EXCEPTIONAL","conviction_score":<0-100>,'
        '"screening_notes":"...","source":"Newsletter|Screener Stage 2"}]}\n'
        "Select 1-3 candidates ONLY from the provided SCREENER_UNIVERSE."
    )

    # NOTE: Fable 5 (Mythos-class) has thinking ALWAYS on and REJECTS the
    # `temperature` param ("temperature is deprecated for this model"). So unlike
    # the live Gemini path (temperature 0.0 for determinism), Fable can't be
    # pinned to 0 — expect slightly less run-to-run determinism. This is itself
    # a relevant data point for the swap decision.
    payload = {
        "model": FABLE_MODEL,
        "max_tokens": 8000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt + schema_nudge}],
    }

    last_error = None
    t0 = time.time()
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Shadow/Fable] Calling {FABLE_MODEL} (attempt {attempt + 1}/{MAX_RETRIES})...")
            resp = requests.post(PROXY_URL, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            # Anthropic Messages: content is a list of blocks; grab text blocks.
            blocks = data.get("content", [])
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            if not text:
                raise RuntimeError(f"Fable returned no text blocks: {json.dumps(data)[:300]}")

            parsed = _extract_json(text)

            # Belt-and-suspenders enum coercion (mirror the live Gemini path).
            for c in parsed.get("candidates", []):
                if c.get("conviction_tier") not in ("PASS", "STRONG", "EXCEPTIONAL"):
                    c["conviction_tier"] = "PASS"
                if c.get("source") not in ("Newsletter", "Screener Stage 2"):
                    c["source"] = "Screener Stage 2"

            usage = data.get("usage", {})
            parsed["_shadow_meta"] = {
                "model": FABLE_MODEL,
                "latency_s": round(time.time() - t0, 1),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            }
            print(f"  [Shadow/Fable] OK — {len(parsed.get('candidates', []))} candidates "
                  f"in {parsed['_shadow_meta']['latency_s']}s")
            return parsed
        except Exception as e:
            last_error = e
            print(f"  [Shadow/Fable] attempt {attempt + 1} failed: {e}")
            time.sleep(2 * (attempt + 1))
    return {"error": f"Fable shadow failed after {MAX_RETRIES} attempts: {last_error}"}


def _load_live_inputs():
    """Load the SAME inputs the live Agent 2 run used, from pipeline output."""
    directive_path = "output/agent1_directive.json"
    candidates_path = "output/agent2_candidates.json"  # live Gemini result

    directive = {}
    if os.path.exists(directive_path):
        with open(directive_path) as f:
            directive = json.load(f)

    live_result = {}
    if os.path.exists(candidates_path):
        with open(candidates_path) as f:
            live_result = json.load(f)

    # Screener universe: prefer the one persisted from preflight if available.
    screener_universe = []
    for p in ("output/screener_universe.json", "output/preflight.json"):
        if os.path.exists(p):
            try:
                with open(p) as f:
                    blob = json.load(f)
                screener_universe = blob.get("screener_universe", blob) if isinstance(blob, dict) else blob
                if screener_universe:
                    break
            except Exception:
                pass

    return directive, screener_universe, live_result


def run_shadow(directive=None, screener_universe=None, fundamental_data=None,
               live_result=None, held_tickers=None) -> dict:
    """
    Run the Fable shadow next to a live Gemini result and log side-by-side.
    Any arg left None is loaded from pipeline output (post-run mode).
    Returns the comparison dict (also appended to SHADOW_LOG).
    """
    os.makedirs(SHADOW_DIR, exist_ok=True)

    if directive is None or screener_universe is None or live_result is None:
        d, su, lr = _load_live_inputs()
        directive = directive or d
        screener_universe = screener_universe or su
        live_result = live_result or lr

    if not screener_universe:
        return {"error": "No screener_universe available — run the live pipeline first."}

    # Re-fetch fundamentals with Agent 2's own pre-fetcher so Fable sees the SAME
    # data contract the live model saw (deterministic; no browsing).
    if fundamental_data is None:
        fundamental_data = prefetch_fundamental_data(screener_universe)

    fable_result = call_fable(directive, screener_universe, fundamental_data, held_tickers)

    def _picks(res):
        return sorted(
            [
                {
                    "ticker": c.get("ticker"),
                    "tier": c.get("conviction_tier"),
                    "score": c.get("conviction_score"),
                }
                for c in (res.get("candidates") or [])
            ],
            key=lambda x: (x.get("ticker") or ""),
        )

    gemini_picks = _picks(live_result)
    fable_picks = _picks(fable_result)
    gemini_tickers = {p["ticker"] for p in gemini_picks}
    fable_tickers = {p["ticker"] for p in fable_picks}

    comparison = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "regime": directive.get("regime", "UNKNOWN"),
        "universe_size": len(screener_universe),
        "gemini": {
            "model": "gemini-3.1-pro-preview",
            "picks": gemini_picks,
        },
        "fable": {
            "model": FABLE_MODEL,
            "picks": fable_picks,
            "meta": fable_result.get("_shadow_meta"),
            "error": fable_result.get("error"),
        },
        "agreement": {
            "overlap": sorted(gemini_tickers & fable_tickers),
            "gemini_only": sorted(gemini_tickers - fable_tickers),
            "fable_only": sorted(fable_tickers - gemini_tickers),
            "identical": gemini_tickers == fable_tickers and bool(gemini_tickers),
        },
    }

    # Persist: dated snapshot + append to running JSONL log.
    snap = os.path.join(SHADOW_DIR, f"agent2_fable_shadow_{comparison['date']}.json")
    with open(snap, "w") as f:
        json.dump({"comparison": comparison, "fable_full": fable_result}, f, indent=2, default=str)
    with open(SHADOW_LOG, "a") as f:
        f.write(json.dumps(comparison, default=str) + "\n")

    # Human-readable summary
    print("\n" + "=" * 60)
    print(f"  AGENT 2 SHADOW A/B — {comparison['date']}  (regime: {comparison['regime']})")
    print("=" * 60)
    print(f"  Gemini (LIVE):  {[p['ticker'] for p in gemini_picks] or '—'}")
    print(f"  Fable (shadow): {[p['ticker'] for p in fable_picks] or '—'}")
    ag = comparison["agreement"]
    if ag["identical"]:
        print("  → IDENTICAL picks")
    else:
        print(f"  → overlap={ag['overlap']}  gemini_only={ag['gemini_only']}  fable_only={ag['fable_only']}")
    print("=" * 60 + "\n")

    return comparison


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        out = run_shadow()
        if out.get("error"):
            print(f"❌ {out['error']}")
            sys.exit(1)
    else:
        print(__doc__)
