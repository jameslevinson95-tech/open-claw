#!/usr/bin/env python3
"""
RETIRED 2026-06-24 — Schwab was removed from the trading pipeline.
Tiingo is now the sole live market-data source (see market_data.py).

This file is a no-op stub kept ONLY so the lingering system crontab entry
    0 3 */2 * * cd .../trading-pipeline && python3 schwab_reauth.py >> logs/schwab_reauth.log 2>&1
exits cleanly (0) instead of erroring with "file not found".

TO FULLY REMOVE: delete the cron line from a real Terminal with:
    crontab -l | grep -v schwab_reauth | crontab -
(headless agent shells can't write crontab — macOS TCC gate blocks the
setuid `crontab` write and it hangs.)
"""
import sys
from datetime import datetime

print(f"[{datetime.now().isoformat(timespec='seconds')}] schwab_reauth.py is RETIRED "
      f"(Schwab removed; Tiingo is the data source). No-op exit.")
sys.exit(0)
