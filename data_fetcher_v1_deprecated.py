"""
Market Data Fetcher
Pulls macro indicators for Agent 1 (Macro Director).
Uses yfinance for free, reliable data.
"""
import yfinance as yf
from datetime import datetime, timedelta
import json


def fetch_macro_data() -> dict:
    """
    Fetch current macro indicators:
    - VIX (^VIX)
    - 10Y Treasury Yield (^TNX)
    - 2Y Treasury Yield (^IRX approximation via 2Y)
    - US Dollar Index (DX-Y.NYB)
    - S&P 500 (^GSPC) - current + recent trend
    - Gold (GC=F) - flight to safety signal
    - HY Credit Spread proxy: HYG vs LQD ratio
    """
    tickers = {
        "VIX": "^VIX",
        "SP500": "^GSPC",
        "TNX_10Y": "^TNX",
        "TWO_YEAR": "2YY=F",
        "DXY": "DX-Y.NYB",
        "GOLD": "GC=F",
        "HYG": "HYG",  # High yield corporate bond ETF
        "LQD": "LQD",  # Investment grade corporate bond ETF
    }

    results = {}
    end = datetime.now()
    start = end - timedelta(days=30)

    for name, ticker in tickers.items():
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                results[name] = {"error": f"No data for {ticker}"}
                continue

            current = float(data["Close"].iloc[-1].item())
            prev_5d = float(data["Close"].iloc[-5].item()) if len(data) >= 5 else current
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current

            results[name] = {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    # Compute yield curve (10Y - 2Y approximation)
    if "TNX_10Y" in results and "TWO_YEAR" in results:
        if "current" in results["TNX_10Y"] and "current" in results["TWO_YEAR"]:
            results["YIELD_CURVE_SPREAD"] = round(
                results["TNX_10Y"]["current"] - results["TWO_YEAR"]["current"], 2
            )

    # HY spread proxy (HYG/LQD ratio - lower = wider spreads = more stress)
    if "HYG" in results and "LQD" in results:
        if "current" in results["HYG"] and "current" in results["LQD"]:
            results["HY_SPREAD_PROXY"] = round(
                results["HYG"]["current"] / results["LQD"]["current"], 4
            )

    results["timestamp"] = datetime.now().isoformat()
    return results


def format_macro_for_prompt(data: dict) -> str:
    """Format macro data into a clean text block for the LLM prompt."""
    lines = [f"MACRO DATA SNAPSHOT — {data.get('timestamp', 'unknown')}", "=" * 50]

    for key, val in data.items():
        if key == "timestamp":
            continue
        if isinstance(val, dict) and "error" in val:
            lines.append(f"{key}: DATA UNAVAILABLE ({val['error']})")
        elif isinstance(val, dict):
            lines.append(
                f"{key}: {val['current']} "
                f"(5d: {val['5d_change_pct']:+.2f}%, 20d: {val['20d_change_pct']:+.2f}%)"
            )
        else:
            lines.append(f"{key}: {val}")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Fetching macro data...")
    data = fetch_macro_data()
    print(json.dumps(data, indent=2))
    print("\n" + format_macro_for_prompt(data))
