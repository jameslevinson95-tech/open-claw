"""
Broker Factory — Switch between Robinhood and Alpaca execution.

Usage:
  from broker_factory import get_broker
  broker = get_broker()  # Auto-detects based on env/config
  broker = get_broker("robinhood")  # Force Robinhood
  broker = get_broker("alpaca")     # Force Alpaca (paper trading)

Both brokers expose the same interface:
  - get_account_summary()
  - get_positions()
  - get_existing_exposure()
  - get_position_tickers()
  - execute_tear_sheet(orders)
  - close_position(ticker, qty=None)
  - close_all_positions()
  - execute_agent5_decisions(decisions, crisis=False)
  - get_orders_today()
"""
import os
from pathlib import Path


# Default broker — set via BROKER env var or auto-detect
DEFAULT_BROKER = os.environ.get("BROKER", "auto")

# Process-level singleton cache. The Robinhood broker does a 3-round-trip MCP
# handshake (initialize + initialized notification + account discovery) in its
# __init__, so creating a fresh instance per get_broker() call was costing
# ~12+ network round-trips per pipeline run. Caching reuses one live MCP
# session for the lifetime of the process. Key is the RESOLVED broker name.
_BROKER_CACHE = {}


def reset_broker_cache():
    """Drop cached broker instances (e.g. after a token refresh or in tests)."""
    _BROKER_CACHE.clear()


def get_broker(broker_name: str = None, *, fresh: bool = False):
    """
    Get a broker instance (cached per-process by default).

    Args:
        broker_name: "robinhood", "alpaca", or "auto" (default).
                     Auto tries Robinhood first, falls back to Alpaca.
        fresh: If True, bypass the cache and build a new instance (and
               replace the cached one). Use for forced reconnects.
    """
    name = (broker_name or DEFAULT_BROKER).lower().strip()

    def _build():
        if name == "robinhood":
            return _get_robinhood()
        elif name == "alpaca":
            return _get_alpaca()
        elif name == "auto":
            # Resolve to Robinhood (real money). We intentionally do NOT silently
            # fall back to Alpaca paper: a quiet RH->paper fallback meant real-intent
            # trades were being routed into the paper account on any RH hiccup,
            # producing phantom positions (e.g. the ORCL incident, 2026-06-03).
            # Fail LOUD instead. To trade paper, set BROKER=alpaca explicitly.
            token_path = Path(__file__).parent / "robinhood-mcp" / "token.json"
            if not token_path.exists():
                raise RuntimeError(
                    "BROKER=auto resolved to Robinhood but robinhood-mcp/token.json "
                    "is missing. Refusing to silently fall back to Alpaca paper. "
                    "Re-auth Robinhood, or set BROKER=alpaca to paper-trade on purpose."
                )
            try:
                return _get_robinhood()
            except Exception as e:
                raise RuntimeError(
                    f"BROKER=auto: Robinhood broker failed to initialize ({e}). "
                    "Refusing to silently fall back to Alpaca paper. "
                    "Set BROKER=alpaca to paper-trade on purpose."
                )
        else:
            raise ValueError(f"Unknown broker: {name}. Use 'robinhood', 'alpaca', or 'auto'.")

    if fresh:
        broker = _build()
        _BROKER_CACHE[name] = broker
        return broker

    cached = _BROKER_CACHE.get(name)
    if cached is not None:
        return cached

    broker = _build()
    _BROKER_CACHE[name] = broker
    return broker


def _get_robinhood():
    from robinhood_broker import RobinhoodBroker
    return RobinhoodBroker()


def _get_alpaca():
    from broker import AlpacaBroker
    return AlpacaBroker()
