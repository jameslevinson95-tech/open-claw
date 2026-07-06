# Open Claw — Independent Audit Closure Report

**Date:** 2026-07-06
**Auditor:** Independent code-audit agent (worked from `FULL_PIPELINE_DUMP.md`, a June-3 snapshot)
**Remediation:** Zuck (this session)
**Repo state at closure:** `origin/main` == `private/main` == local `84cd074`

> **Note on the stale dump:** the audit was performed against a June-3 codebase dump.
> Two of the five CRITICALs were *already resolved in HEAD* before this session began —
> the auditor flagged them because the dump predated their fix. Verified against live code below.

---

## CRITICAL findings (5)

| # | Finding | Status | Closed by | Verified in HEAD |
|---|---------|--------|-----------|------------------|
| C1 | `HEARTBEAT_PATH` mismatch — daemon heartbeat written/read at divergent paths | ✅ Pre-resolved | (before session) | `output/daemon_heartbeat.txt` single source |
| C2 | Agent 5 broker hardcoded — bypassed `broker_factory`, ignored `BROKER` env | ✅ Pre-resolved | (before session) | agent5 resolves broker via factory |
| C3 | Thesis/catalyst never wired into orders → drift monitor saw empty string daily | ✅ Fixed | `8f17aa6` | `agent4_risk_manager.py:637-639` emits `thesis`/`catalyst`/`agent2_thesis` |
| C4 | No live re-size on real execution path → a gap-up could ~2x per-trade risk | ✅ Fixed | `32ae51e` | `orchestrator.py:724 run_deferred_execution`, reads `risk_budgeted`, sizes DOWN only |
| C5* | High-severity cluster (see below) — batched, not a single labeled item | ✅ Fixed | `3a45468` + `8f80c33` | per-item below |

\* The audit's fifth tranche of critical/high-severity items was not a single "CRITICAL 5";
it was a cluster remediated across two commits. Enumerated individually:

### C5 cluster — individual items

| Item | Status | Closed by | Verified |
|------|--------|-----------|----------|
| Watchlist-gate bypass (`candidates + ready_candidates` let raw candidates skip the pullback bench) | ✅ | `3a45468` | `orchestrator.py:246` READY-only, deduplicated |
| VIX operator-precedence bug (missing parens in pre-market guard) | ✅ | `3a45468` | `preflight.py:234` parenthesized |
| Drawdown-safe sizing floor (planning floor for settling deposits) | ✅ | `3a45468` | `config.py PLANNING_FLOOR_EXPIRY=2026-06-14` (expired→inactive) + agent4 date-gate |
| Fractional-safe rounding (`int()` truncation killed sub-1-share orders) | ✅ | `32ae51e` | 4dp rounding, `execution_engine` `shares: float` |
| Wide-spread gate absurdly permissive (5%) | ✅ | `32ae51e` | `orchestrator.py:797 MAX_SPREAD_PCT = 0.0075` (0.75%) |
| CURATED_ACCOUNTS divergence (3 copies; Opus told 15, actually 31; stale retail handles) | ✅ | `8f80c33` | `agent3` + `preflight` both `from x_fetch import CURATED_ACCOUNTS` |
| FedWatch FOMC hardcoded 2026-only (vanishes 2027-01-01) | ✅ | `8f80c33` | `fedwatch.py get_fomc_meetings()` auto-extends |
| HY credit spread faked via HYG/LQD (duration-contaminated) | ✅ | `8f80c33` | `preflight.py:362 fetch_hy_oas()` → FRED `BAMLH0A0HYM2`, ETF ratio demoted to fallback |
| Dead `PER_TRADE_RISK_CAP` (conflicting-caps confusion) | ✅ | `8f80c33` | removed; `MAX_RISK_PER_TRADE` is sole ceiling |

### Measurement-loop items (folded into C3 commit)

| Item | Status | Closed by |
|------|--------|-----------|
| `x_bullish_count` / `x_bearish_count` / `hf_principal_signal` never populated (empty journal fields forever) | ✅ | `8f17aa6` — agent3 emits into verification record + output schema |
| Agent 2 original thesis clobbered by qualitative synthesis (catalyst record destroyed) | ✅ | `8f17aa6` — keep both `agent2_thesis` + `qualitative_thesis` |

---

## Post-remediation activation

- **`FRED_API_KEY`** added to `.env` and verified live: HY OAS = 2.75% (2026-07-02) from `BAMLH0A0HYM2`.
  Also arms the existing FRED MOVE fallback.

## Explicitly NOT changed (strategy — require journal evidence, per auditor's closing note)

Vol-regime Python bucketing, hysteresis, relative-strength ranking, chandelier trails,
time stops, sector/correlation caps. These are tuning decisions that need ~30–50 closed
trades of admissible evidence before they're changed. Deferred by design, not oversight.

---

## Repo-hygiene system added this session (prevents recurrence of stale-dump audits)

- `post-commit` hook → auto-regenerates codebase dump + auto-pushes to both remotes
- `scripts/generate_codebase_dump.sh` → reproducible dump (was hand-built → went stale)
- `scripts/check_env_drift.sh` + cron `open-claw-repo-hygiene` (weekdays 17:30 ET) →
  flags unpushed commits / dirty tree / missing env keys; silent on clean, alerts #trading on drift

**Bottom line:** 5/5 CRITICALs closed (2 pre-existing, 3 remediated this session across
`3a45468`, `32ae51e`, `8f17aa6`), plus the full high-severity + measurement-loop cluster in `8f80c33`.
