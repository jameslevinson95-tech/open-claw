#!/usr/bin/env python3
"""
daemon_watchdog.py — Execution-daemon liveness check for Open Claw.

The execution daemon writes output/daemon_heartbeat.txt every ~10s. If that
file goes stale, the daemon is wedged/dead and the naked-stop safety net is
NOT running — protective stops won't auto-heal. This script reports that so a
scheduled job can alert #trading.

Exit codes:
  0 = healthy (hb_signal fresh AND process found)
  2 = STALE/DOWN (hb_signal older than threshold, or process missing)
  3 = UNKNOWN (hb_signal file missing entirely)

--json prints a machine-readable status line for the scheduler to act on.
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path

HB_SIGNAL_PATH = Path(__file__).parent / "output" / "daemon_hb_signal.txt"
# Daemon writes every 10s; flag stale only after a comfortable margin so we
# don't false-alarm on a slow loop or the atomic-rename window.
STALE_AFTER_SECONDS = 120

# Alert de-dupe: once we alert, stay quiet for this long before re-alerting on a
# still-down daemon (so a long outage doesn't spam #trading every poll).
ALERT_STATE_PATH = Path(__file__).parent / "output" / ".watchdog_last_alert"
ALERT_COOLDOWN_SECONDS = 1800  # 30 min


def should_alert() -> bool:
    """True if we haven't alerted within the cooldown window. Records the time."""
    now = time.time()
    try:
        if ALERT_STATE_PATH.exists():
            last = float(ALERT_STATE_PATH.read_text().strip() or 0)
            if now - last < ALERT_COOLDOWN_SECONDS:
                return False
    except Exception:
        pass
    try:
        ALERT_STATE_PATH.write_text(str(now))
    except Exception:
        pass
    return True


def clear_alert_state():
    """Called when healthy so the next outage alerts immediately."""
    try:
        if ALERT_STATE_PATH.exists():
            ALERT_STATE_PATH.unlink()
    except Exception:
        pass


def _proc_alive() -> bool:
    """True if run_execution_daemon.py is running."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", "run_execution_daemon.py"],
            capture_output=True, text=True, timeout=8,
        )
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return False


def check() -> dict:
    now = time.time()
    proc = _proc_alive()

    if not HB_SIGNAL_PATH.exists():
        return {
            "status": "unknown",
            "healthy": False,
            "code": 3,
            "reason": "hb_signal file missing",
            "hb_signal_age_s": None,
            "proc_alive": proc,
        }

    age = round(now - HB_SIGNAL_PATH.stat().st_mtime, 1)
    stale = age > STALE_AFTER_SECONDS

    if stale or not proc:
        reasons = []
        if stale:
            reasons.append(f"hb_signal stale ({age}s > {STALE_AFTER_SECONDS}s)")
        if not proc:
            reasons.append("daemon process not found")
        return {
            "status": "down",
            "healthy": False,
            "code": 2,
            "reason": "; ".join(reasons),
            "heartbeat_age_s": age,
            "proc_alive": proc,
        }

    return {
        "status": "healthy",
        "healthy": True,
        "code": 0,
        "reason": f"hb_signal fresh ({age}s) and process alive",
        "hb_signal_age_s": age,
        "proc_alive": proc,
    }


if __name__ == "__main__":
    result = check()

    # --alert-gate: for the scheduled job. Prints exactly one of:
    #   OK                          -> daemon healthy (or already alerted recently)
    #   ALERT <one-line reason>     -> daemon down AND outside cooldown -> POST IT
    # This lets the agent turn stay silent unless there's a fresh, real problem.
    if "--alert-gate" in sys.argv:
        if result["healthy"]:
            clear_alert_state()
            print("OK")
        elif should_alert():
            age = result.get("hb_signal_age_s")
            age_str = f"{age}s" if age is not None else "n/a"
            print(
                f"ALERT \U0001f6a8 Open Claw EXECUTION DAEMON DOWN — {result['reason']} "
                f"(hb_signal age {age_str}, process_alive={result['proc_alive']}). "
                f"The naked-stop safety net is NOT running. Protective stops will "
                f"not auto-heal until the daemon is restarted: "
                f"`bash /Users/chris/code/trading-pipeline/run_execution_daemon.sh` "
                f"is the supervisor — check it / kill the wedged python child so it respawns."
            )
        else:
            print("OK")  # down but within cooldown — already alerted, stay quiet
        sys.exit(0)

    if "--json" in sys.argv:
        print(json.dumps(result))
    else:
        icon = "🟢" if result["healthy"] else ("🔴" if result["code"] == 2 else "⚪")
        print(f"{icon} execution daemon: {result['status'].upper()} — {result['reason']}")
    sys.exit(result["code"])
