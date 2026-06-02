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
            # Try Robinhood first (real money), fall back to Alpaca (paper)
            try:
                token_path = Path(__file__).parent / "robinhood-mcp" / "token.json"
                if token_path.exists():
                    return _get_robinhood()
            except Exception as e:
                print(f"[BrokerFactory] Robinhood unavailable ({e}), trying Alpaca...")
            try:
                return _get_alpaca()
            except Exception as e:
                raise RuntimeError(f"No broker available. Robinhood and Alpaca both failed: {e}")
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
