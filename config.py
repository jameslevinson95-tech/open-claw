"""
Trading Pipeline Configuration — "Golden Path" v2
Incorporates Jamie's finalized tweaks.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Account
# Robinhood agentic account: $500 funded, sizing to represent ~$5,500 remaining
# budget (out of $10K total project allowance, ~$4K already deployed elsewhere).
# Scale factor: $500 / $5,500 ≈ 9.1% — pipeline sizes as if $500 is the full account,
# so all risk parameters below are calibrated to this amount.
ACCOUNT_SIZE = 500  # $500 Robinhood agentic account (proportional to $5,500 remaining)
DRY_POWDER_FLOOR = 0.20  # Never deploy beyond 80% ($400 max deployed)

# Alpaca
ALPACA_USERNAME = os.environ.get("ALPACA_USERNAME", "")
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"  # Paper trading first

# LLM Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # For Gemini (Agent 2)

# Telegram Output
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Schedule (ET) — Golden Path timing
PREFLIGHT_TIME = "07:55"       # Python pre-flight data fetch
AGENT1_TIME = "08:00"          # Agent 1 - Macro Director
AGENT2_TIME = "08:01"          # Agent 2 - Fundamental Screener
AGENT3_TIME = "08:15"          # Agent 3 - Signal Verifier (Smart Money)
AGENT4_TIME = "08:17"          # Agent 4a/4b - Risk Manager
TEARSHEET_TIME = "08:18"       # Deliver tear sheet
AGENT5_PREFLIGHT_TIME = "15:25"  # Agent 5 pre-flight price snapshot
AGENT5_TIME = "15:30"          # Agent 5 - Position Monitor

# Risk Parameters (scaled to $500 account)
PER_TRADE_RISK_CAP = 7.50      # $7.50 max risk per trade (1.5% of $500)
SESSION_RISK_BUDGET = 50.00    # $50 max session risk (10% of $500)
THEME_CAP = 1                  # Max 1 position per theme per session (tweak #5)

# Screener Rules
SCREENER_MIN_MARKET_CAP = 100_000_000  # $100M minimum
SCREENER_MIN_PRICE = 5.00              # > $5

# Position Sizing — Risk-First Model (v3)
# Sizing starts from RISK DOLLARS, derives shares from stop distance,
# then floors with allocation cap. Binding constraint is logged.

# Posture table (regime -> posture + conviction floor)
POSTURE_TABLE = {
    "Risk-On":          {"posture": "Aggressive",  "conviction_floor": 5},
    "Cautious Risk-On": {"posture": "Offensive",   "conviction_floor": 6},
    "Risk-Off":         {"posture": "Defensive",   "conviction_floor": 7},
    "Crisis":           {"posture": "Bunker",      "conviction_floor": 9},
    "Defer":            {"posture": "Hold",        "conviction_floor": 10},
}

# Agent 1 emits regimes/vols in UPPERCASE; config keys are Title-Case.
# These maps are the single source of truth for normalization.
# Add a new alias here if you ever rename a regime.
_REGIME_CANONICAL = {
    "RISK-ON": "Risk-On",
    "CAUTIOUS RISK-ON": "Cautious Risk-On",
    "RISK-OFF": "Risk-Off",
    "CRISIS": "Crisis",
    "DEFER": "Defer",
}

_VOL_CANONICAL = {
    "COMPRESSED": "Compressed",
    "NORMAL": "Normal",
    "ELEVATED": "Elevated",
    "STRESSED": "Stressed",
}


def normalize_regime(s: str) -> str:
    """Coerce any-casing regime string to canonical POSTURE_TABLE key.
    Raises ValueError on unknown input — DO NOT swallow silently."""
    if not s:
        raise ValueError("normalize_regime: empty/None regime")
    key = s.strip().upper()
    if key in _REGIME_CANONICAL:
        return _REGIME_CANONICAL[key]
    if s in POSTURE_TABLE:  # already canonical
        return s
    raise ValueError(
        f"Unknown regime: {s!r} (expected one of {list(_REGIME_CANONICAL)})"
    )


def normalize_vol_regime(s: str) -> str:
    """Coerce any-casing vol_regime to canonical VOL_RISK_MULT key.
    Raises ValueError on unknown input."""
    if not s:
        raise ValueError("normalize_vol_regime: empty/None vol_regime")
    key = s.strip().upper()
    if key in _VOL_CANONICAL:
        return _VOL_CANONICAL[key]
    if s in VOL_RISK_MULT:
        return s
    raise ValueError(
        f"Unknown vol_regime: {s!r} (expected one of {list(_VOL_CANONICAL)})"
    )

# Risk-first sizing constants (scaled to $500 account)
BASE_RISK = 7.50               # Per-trade $ at neutral conviction (1.5% of $500)
MAX_RISK_PER_TRADE = 10.00     # Hard ceiling regardless of multiplier stack
MIN_RISK_PER_TRADE = 2.50      # Below this, skip (regime says don't trade)
MAX_ALLOCATION_PCT = 0.25      # Share-count cap as % of account

# Tier risk multipliers (replaces numeric conviction_mod)
TIER_RISK_MULT = {
    "PASS": 0.70,
    "STRONG": 1.00,
    "EXCEPTIONAL": 1.20,
}

# Confirm bonus from Agent 3 CONFIRM_ENHANCED verdict
CONFIRM_RISK_MULT = {True: 1.10, False: 1.00}

# Vol regime risk multipliers
VOL_RISK_MULT = {
    "Compressed": 1.10,
    "Normal": 1.00,
    "Elevated": 0.70,
    "Stressed": 0.40,
}

# Posture risk multipliers
POSTURE_RISK_MULT = {
    "Aggressive": 1.00,
    "Offensive": 0.80,
    "Defensive": 0.40,
    "Bunker": 0.00,
}

# Legacy aliases (kept for backward compat, will deprecate)
BASE_ALLOCATION_CAP = 0.15
VOL_REGIME_MOD = VOL_RISK_MULT
CONVICTION_MOD = {}  # Deprecated — use TIER_RISK_MULT

# Curated smart money Twitter/X accounts for Agent 3
SMART_MONEY_ACCOUNTS = [
    # Add Twitter/X handles here when API is set up
    # e.g., "unusual_whales", "DeItaone", "zaborsky", etc.
]

# Portfolio Heat Cap
MAX_PORTFOLIO_HEAT_PCT = 0.06   # 6% of equity — reject all new trades above this
HEAT_WARNING_PCT = 0.04         # 4% — allow trades but print warning

# FRED API key (for MOVE index, credit data)
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# Massive (Polygon-compatible) Market Data API
# Free tier: historical bars, technical indicators (SMA, EMA, RSI, MACD), 5 calls/min
MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "")
