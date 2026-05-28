# Data Parity Matrix — yfinance Removal Status

Last verified: 2026-05-28 01:52 ET

## Current Vendor Coverage

| Data Type | Massive (Free) | Schwab | yfinance | Status |
|-----------|---------------|--------|----------|--------|
| Daily OHLCV bars | ✅ 200 | ❌ Not impl | ✅ Fallback | **Routed via DataProvider** |
| 1-min intraday bars | ✅ 200 (~6hr delay) | ❌ Not impl | ✅ Live | **yfinance required for live** |
| News headlines | ✅ 200 | ❌ Not impl | ✅ Fallback | **Routed via DataProvider** |
| Options OI / P-C ratio | ❌ 403 (paid) | ❌ Not impl | ✅ Only source | **yfinance required** |
| Short interest % float | ❌ 404 (no endpoint) | ❌ Not impl | ✅ Only source | **yfinance required** |
| Stock splits | ✅ 200 | ❌ Not impl | Removed | **Routed via DataProvider** |
| Index VIX/SPX | ❌ 403 (paid) | ✅ $VIX/$SPX | ✅ ETF proxy | **DataProvider fallback chain** |
| Live quotes (NBBO) | N/A | ✅ Primary | N/A | **Broker feed only** |
| Earnings dates | N/A | N/A | ✅ Only source | **yfinance required** |

## What Blocks PR3 (full yfinance removal)

Before yfinance can be deleted, one of these must be implemented:

1. **Options OI**: Upgrade to Massive paid tier for options snapshots, OR implement Schwab options chain endpoint
2. **Short Interest**: Find alternative source (Massive doesn't have it, Schwab TBD)
3. **Earnings Dates**: Alternative source needed (possibly Massive ticker events?)
4. **Intraday 1-min bars**: Schwab historical bars endpoint, OR accept Massive's EOD delay
5. **Historical bars fallback**: Without yfinance, Massive becomes SPOF for ATR/correlation

## Current yfinance Usage (files that still import it)

- `agent3_synthesizer.py` — Options OI, short interest (sandboxed in `fetch_single()`)
- `broker.py` — 1-min intraday tape for cross-reference price
- `preflight.py` — Macro data (VIX, MOVE, yield curve), technicals local calc
- `safeguards.py` — Earnings dates
- `trade_journal.py` — SPX benchmark calculation
- `data_provider.py` — Deprecated fallback for EOD bars + news fallback

## Files Fully Off yfinance

- `agent4_risk_manager.py` ✅ — All via DataProvider
- `flash_crash_daemon.py` ✅ — All via DataProvider
