"""
Trade Journal — Feedback CSV for the Open Claw pipeline.
One row per closed trade. Appended on every Agent 5 close and manual exit.
All inputs to the sizer, all decision flags, and outcome stats.

The R-multiple is the key field: pnl_dollars / risk_budgeted.
Normalizes across position sizes — comparing EXCEPTIONAL to PASS by dollar
P&L is misleading because EXCEPTIONALs are sized bigger by design.
Comparing by R tells you whether the conviction signal actually predicts outcome.
"""
import csv
from datetime import datetime
from pathlib import Path

JOURNAL_PATH = Path("journal/trades.csv")

FIELDS = [
    # Identity
    "trade_id", "ticker", "theme",
    "entry_dt", "exit_dt", "holding_days",

    # Decision flags (at entry)
    "regime", "vol_regime", "posture",
    "tier", "agent3_verdict", "confirm_enhanced",
    "x_bullish_count", "x_bearish_count", "hf_principal_signal",

    # Sizing
    "entry_price", "stop_price", "stop_distance_pct",
    "shares", "position_value",
    "risk_budgeted", "risk_actual",
    "risk_multiplier", "binding_constraint",

    # Outcome
    "exit_price", "exit_reason",
    "pnl_dollars", "pnl_pct", "r_multiple",

    # Path stats (the underrated fields)
    "max_adverse_excursion_pct",    # worst drawdown before exit
    "max_favorable_excursion_pct",  # best unrealized gain before exit
    "spx_change_over_hold_pct",     # beta context

    # Process notes
    "agent2_thesis_short",  # 1-line, for human review
    "notes",
]


def log_close(trade_record: dict):
    """Append a closed trade to the journal CSV."""
    JOURNAL_PATH.parent.mkdir(exist_ok=True)
    new_file = not JOURNAL_PATH.exists()
    with JOURNAL_PATH.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: trade_record.get(k, "") for k in FIELDS})


def build_trade_record(
    trade_order: dict,
    directive: dict,
    agent3_verification: dict,
    exit_price: float,
    exit_reason: str,
    exit_dt: datetime = None,
    mae_pct: float = None,
    mfe_pct: float = None,
    spx_change_pct: float = None,
    notes: str = "",
) -> dict:
    """
    Build a complete trade record from pipeline outputs.
    Call this when Agent 5 closes a position or on manual exit.
    """
    entry_price = trade_order.get("entry_price", 0)
    shares = trade_order.get("shares", 0)
    risk_budgeted = trade_order.get("risk_budgeted", 0)
    entry_dt_str = trade_order.get("entry_dt", directive.get("timestamp", ""))

    pnl_dollars = round((exit_price - entry_price) * shares, 2)
    pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2) if entry_price else 0
    r_multiple = round(pnl_dollars / risk_budgeted, 2) if risk_budgeted else 0

    # Parse dates for holding days
    exit_dt = exit_dt or datetime.now()
    holding_days = 0
    try:
        if isinstance(entry_dt_str, str) and entry_dt_str:
            entry_parsed = datetime.fromisoformat(entry_dt_str.replace("Z", "+00:00"))
            holding_days = (exit_dt - entry_parsed).days
    except Exception:
        pass

    # Calculate SPX beta context (Did we beat the market?)
    if spx_change_pct is None:
        try:
            import yfinance as yf
            from datetime import timedelta
            if isinstance(entry_dt_str, str) and entry_dt_str:
                entry_parsed_spx = datetime.fromisoformat(entry_dt_str.replace("Z", "+00:00"))
                spy = yf.download(
                    "SPY",
                    start=entry_parsed_spx.strftime("%Y-%m-%d"),
                    end=(exit_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                    progress=False,
                )
                if not spy.empty and len(spy) >= 1:
                    if hasattr(spy.columns, 'levels') and len(spy.columns.levels) > 1:
                        spy_entry = float(spy["Close"]["SPY"].iloc[0])
                        spy_exit = float(spy["Close"]["SPY"].iloc[-1])
                    else:
                        spy_entry = float(spy["Close"].iloc[0])
                        spy_exit = float(spy["Close"].iloc[-1])
                    spx_change_pct = round((spy_exit - spy_entry) / spy_entry * 100, 2)
        except Exception:
            spx_change_pct = None

    # Generate trade ID
    trade_id = f"{trade_order.get('ticker', 'UNK')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return {
        "trade_id": trade_id,
        "ticker": trade_order.get("ticker", ""),
        "theme": trade_order.get("theme", ""),
        "entry_dt": entry_dt_str,
        "exit_dt": exit_dt.isoformat(),
        "holding_days": holding_days,

        "regime": directive.get("regime", ""),
        "vol_regime": directive.get("vol_regime", ""),
        "posture": directive.get("posture", ""),
        "tier": trade_order.get("conviction_tier", ""),
        "agent3_verdict": agent3_verification.get("verdict", ""),
        "confirm_enhanced": trade_order.get("confirm_enhanced", False),
        "x_bullish_count": agent3_verification.get("x_bullish_count", ""),
        "x_bearish_count": agent3_verification.get("x_bearish_count", ""),
        "hf_principal_signal": agent3_verification.get("hf_principal_signal", ""),

        "entry_price": entry_price,
        "stop_price": trade_order.get("stop_loss", ""),
        "stop_distance_pct": trade_order.get("stop_distance_pct", ""),
        "shares": shares,
        "position_value": trade_order.get("position_value", ""),
        "risk_budgeted": risk_budgeted,
        "risk_actual": trade_order.get("risk_actual", ""),
        "risk_multiplier": trade_order.get("risk_multiplier", ""),
        "binding_constraint": trade_order.get("binding_constraint", ""),

        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "pnl_dollars": pnl_dollars,
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,

        "max_adverse_excursion_pct": mae_pct or "",
        "max_favorable_excursion_pct": mfe_pct or "",
        "spx_change_over_hold_pct": spx_change_pct or "",

        "agent2_thesis_short": trade_order.get("thesis", "")[:100],
        "notes": notes,
    }
