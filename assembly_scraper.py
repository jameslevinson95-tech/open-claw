"""
Assembly Private Scraper — Browser-based extraction.

Assembly is a Next.js SPA that renders data client-side.
This scraper uses the browser DOM snapshots (from OCPlatform BrowserControl)
or falls back to a pre-saved JSON file.

For automated pipeline runs, the orchestrator calls scrape via browser,
saves to output/assembly_data.json, and agents read from that file.

Usage:
  python assembly_scraper.py parse-snapshot <snapshot_file>
  python assembly_scraper.py load  (reads from output/assembly_data.json)
"""

import json
import re
import os
from datetime import datetime


def parse_sentiment_from_text(text: str) -> dict:
    """Parse sentiment data from page text content."""
    result = {"timestamp": datetime.utcnow().isoformat(), "source": "assembly_sentiment"}

    # Composite score
    composite_match = re.search(r"(\d+)\s+(Greed|Fear|Neutral|Extreme\s*Greed|Extreme\s*Fear|Ex\.\s*Greed|Ex\.\s*Fear)", text)
    if composite_match:
        result["composite_score"] = int(composite_match.group(1))
        result["composite_label"] = composite_match.group(2)

    # Historical values
    for label, key in [
        ("Prev Close", "prev_close"),
        ("Previous Close", "prev_close"),
        ("1 Week Ago", "one_week_ago"),
        ("1W Ago", "one_week_ago"),
        ("1 Month Ago", "one_month_ago"),
        ("1M Ago", "one_month_ago"),
        ("1 Year Ago", "one_year_ago"),
        ("1Y Ago", "one_year_ago"),
        ("30-Day Avg", "thirty_day_avg"),
        ("52-Week High", "fifty_two_week_high"),
        ("52-Week Low", "fifty_two_week_low"),
    ]:
        match = re.search(rf"{re.escape(label)}\s+(\d+)", text)
        if match and key not in result:
            result[key] = int(match.group(1))

    # Sub-components
    components = {}
    patterns = [
        (r"Market Volatility\s*\(VIX\)\s*(\d+)", "market_volatility_vix"),
        (r"S&P 125-day Momentum\s*(\d+)", "sp500_momentum_125d"),
        (r"S&P 500 Momentum\s*(\d+)", "sp500_momentum"),
        (r"Stock Price Strength\s*(\d+)", "stock_price_strength"),
        (r"Stock Price Breadth\s*(\d+)", "stock_price_breadth"),
        (r"Put\s*/\s*Call Options\s*(\d+)", "put_call_options"),
        (r"Junk Bond Demand\s*(\d+)", "junk_bond_demand"),
        (r"Safe Haven Demand\s*(\d+)", "safe_haven_demand"),
    ]
    for pattern, key in patterns:
        match = re.search(pattern, text)
        if match:
            components[key] = int(match.group(1))

    # VIX actual value
    vix_match = re.search(r"VIX\)\s*\d+\s+(\d+\.?\d*)", text)
    if vix_match:
        components["vix_value"] = float(vix_match.group(1))

    result["components"] = components

    # Sector breadth
    sectors = {}
    sector_pattern = re.findall(
        r"(Energy|Healthcare|Utilities|Real Estate|Consumer Defensive|Technology|"
        r"Communication Services|Consumer Cyclical|Industrials|Financial Services|"
        r"Basic Materials)\s+([+\-]?\d+\.?\d*%)",
        text
    )
    for sector, change in sector_pattern:
        sectors[sector] = change
    result["sector_breadth"] = sectors

    return result


def parse_macro_from_snapshot(snapshot_text: str) -> dict:
    """Parse macro data from a browser snapshot."""
    result = {"timestamp": datetime.utcnow().isoformat(), "source": "assembly_macro"}

    # Yield curve
    yield_curve = {}
    for tenor in ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]:
        match = re.search(rf"\b{tenor}\s+(\d+\.?\d*)", snapshot_text)
        if match:
            yield_curve[tenor] = float(match.group(1))
    result["yield_curve"] = yield_curve

    # Key macro
    for label, key in [
        ("Fed Funds", "fed_funds"),
        ("Unemployment", "unemployment"),
    ]:
        match = re.search(rf"{re.escape(label)}\s+([\d.]+%?)", snapshot_text)
        if match:
            result[key] = match.group(1)

    # Cross-asset rotation — parse from structured snapshot
    cross_asset = []
    # Pattern: "SPY US Large Cap Equity $733.73 -0.67% +6.1% +8.4% 91%"
    asset_pattern = re.findall(
        r'([A-Z]{2,5})\s+([\w\s]+?)\s+(Equity|Bond|Commodity|FX|Crypto)\s+\$([\d,.]+)\s+'
        r'([+\-]?\d+\.?\d*%)\s+([+\-]?\d+\.?\d*%)\s+([+\-]?\d+\.?\d*%)\s+(\d+%)',
        snapshot_text
    )
    for ticker, name, asset_class, price, today, vs50, vs200, range52 in asset_pattern:
        cross_asset.append({
            "ticker": ticker.strip(),
            "name": name.strip(),
            "asset_class": asset_class,
            "price": f"${price}",
            "today": today,
            "vs_50d": vs50,
            "vs_200d": vs200,
            "range_52w": range52,
        })
    result["cross_asset_rotation"] = cross_asset

    return result


def format_sentiment_for_prompt(sentiment: dict) -> str:
    """Format sentiment data for Agent 1's system prompt."""
    lines = [
        "ASSEMBLY SENTIMENT DATA",
        "=" * 40,
        f"Composite Score: {sentiment.get('composite_score', '?')} ({sentiment.get('composite_label', '?')})",
        f"Prev Close: {sentiment.get('prev_close', '?')} | 1W Ago: {sentiment.get('one_week_ago', '?')} | 1M Ago: {sentiment.get('one_month_ago', '?')}",
        f"30D Avg: {sentiment.get('thirty_day_avg', '?')} | 52W High: {sentiment.get('fifty_two_week_high', '?')} | 52W Low: {sentiment.get('fifty_two_week_low', '?')}",
        "",
        "Sub-Components:",
    ]
    components = sentiment.get("components", {})
    for key, label in [
        ("market_volatility_vix", "Market Volatility (VIX)"),
        ("vix_value", "VIX Actual"),
        ("sp500_momentum_125d", "S&P 125d Momentum"),
        ("sp500_momentum", "S&P 500 Momentum"),
        ("stock_price_strength", "Stock Price Strength"),
        ("stock_price_breadth", "Stock Price Breadth"),
        ("put_call_options", "Put/Call Options"),
        ("junk_bond_demand", "Junk Bond Demand"),
        ("safe_haven_demand", "Safe Haven Demand"),
    ]:
        val = components.get(key)
        if val is not None:
            lines.append(f"  {label}: {val}")

    sectors = sentiment.get("sector_breadth", {})
    if sectors:
        lines.append("")
        lines.append("Sector Breadth:")
        for sector, change in sectors.items():
            lines.append(f"  {sector}: {change}")

    return "\n".join(lines)


def format_macro_for_prompt(macro: dict) -> str:
    """Format macro data for Agent 1's system prompt."""
    lines = [
        "ASSEMBLY MACRO DATA",
        "=" * 40,
    ]

    yc = macro.get("yield_curve", {})
    if yc:
        curve_str = " | ".join(f"{t}: {v}" for t, v in yc.items())
        lines.append(f"Yield Curve: {curve_str}")

    for key, label in [("fed_funds", "Fed Funds"), ("unemployment", "Unemployment")]:
        if key in macro:
            lines.append(f"{label}: {macro[key]}")

    cross_asset = macro.get("cross_asset_rotation", [])
    if cross_asset:
        lines.append("")
        lines.append("Cross-Asset Rotation:")
        for a in cross_asset:
            lines.append(f"  {a['ticker']} ({a['name']}): {a['price']} | Today: {a['today']} | vs50d: {a['vs_50d']} | vs200d: {a['vs_200d']} | 52wk: {a['range_52w']}")

    return "\n".join(lines)


def load_assembly_data() -> dict:
    """Load pre-scraped Assembly data from output file."""
    path = "output/assembly_data.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "load":
        data = load_assembly_data()
        if "sentiment" in data:
            print(format_sentiment_for_prompt(data["sentiment"]))
            print()
        if "macro" in data:
            print(format_macro_for_prompt(data["macro"]))
    else:
        print("Usage: python assembly_scraper.py load")
        print("  (Assembly data must be scraped via browser and saved to output/assembly_data.json)")
