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


def get_broker(broker_name: str = None):
    """
    Get a broker instance.
    
    Args:
        broker_name: "robinhood", "alpaca", or "auto" (default).
                     Auto tries Robinhood first, falls back to Alpaca.
    """
    name = (broker_name or DEFAULT_BROKER).lower().strip()

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


def _get_robinhood():
    from robinhood_broker import RobinhoodBroker
    return RobinhoodBroker()


def _get_alpaca():
    from broker import AlpacaBroker
    return AlpacaBroker()
