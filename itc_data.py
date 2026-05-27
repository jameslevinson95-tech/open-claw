"""
ITC (Into The Cryptoverse) Data Fetcher
Scrapes key macro and crypto risk indicators from app.intothecryptoverse.com

Indicators fetched (from dashboard snapshot):
1. Crypto Risk Summary (composite: Price + On-Chain + Social)
2. BTC/ETH/asset-level Risk Levels (0-1 scale, Ben Cowen's model)
3. Macro Recession Risk (Employment + National Income + Production)
4. BTC Dominance (with/without stablecoins)
5. Market Cap vs Trendline (log regression deviation %)
6. Unemployment Rate, M2 Supply, Consumer Confidence
7. Full asset table (crypto + tradfi with risk scores)

Data is scraped from the dashboard DOM via browser snapshot.
Requires an active browser session (login handled by Zuck).

Usage:
    Called by preflight.py's fetch_itc_data() which delegates to Zuck's browser.
    Data is saved to output/itc_data.json.
    Agent 1 receives it as supplementary macro context via format_itc_for_prompt().
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, Optional


def parse_itc_dashboard_snapshot(snapshot_text: str) -> Dict:
    """
    Parse ITC dashboard data from a browser snapshot (aria tree text).
    
    The compact snapshot format contains:
    - Grid rows with asset data (name, price, changes, risk)
    - Crypto Risk Indicators widget with summary gauge
    - Macro Recession Risk widget
    - Dominance widget
    - Log Regression widget
    - Macro Calendar entries
    
    Returns a structured dict of all extractable indicators.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "source": "intothecryptoverse.com/dashboard",
        "crypto_risk": {},
        "macro_risk": {},
        "dominance": {},
        "valuation": {},
        "macro_calendar": {},
        "assets": [],
    }

    # --- Extract favorite assets from grid rows ---
    # Compact format: row "Name (TICKER) $price change% change% mcap risk ..."
    asset_pattern = re.compile(
        r'row "(?:[\w\s.]+logo\s+)?([\w\s.&\'/]+?)\s*\((\w+)\)\s+'
        r'\$([\d,.]+)\s+'
        r'(-?[\d.]+%|-)\s+'
        r'(-?[\d.]+%|-)\s+'
        r'([\d.]+[TBMK]?|-)\s+'
        r'([\d.]+)'
    )
    
    for match in asset_pattern.finditer(snapshot_text):
        name, ticker, price, change_24h, change_7d, mcap, risk = match.groups()
        asset = {
            "name": name.strip(),
            "ticker": ticker,
            "price": price.replace(",", ""),
            "change_24h": change_24h,
            "change_7d": change_7d,
            "market_cap": mcap,
            "fiat_risk": float(risk),
        }
        result["assets"].append(asset)
        
        # Capture key asset risks
        if ticker == "BTC":
            result["crypto_risk"]["btc_risk"] = float(risk)
            result["crypto_risk"]["btc_price"] = price.replace(",", "")
        elif ticker == "ETH":
            result["crypto_risk"]["eth_risk"] = float(risk)
            result["crypto_risk"]["eth_price"] = price.replace(",", "")
        elif ticker == "SP500":
            result["macro_risk"]["sp500_risk"] = float(risk)
            result["macro_risk"]["sp500_price"] = price.replace(",", "")
        elif ticker == "DXY":
            result["macro_risk"]["dxy_risk"] = float(risk)
            result["macro_risk"]["dxy_value"] = price.replace(",", "")
        elif ticker == "GOLD":
            result["macro_risk"]["gold_risk"] = float(risk)
            result["macro_risk"]["gold_price"] = price.replace(",", "")

    # --- Extract Crypto Risk Summary from img alt text ---
    # Format: "0.239 0.239 0.239 ... Summary: 0.239 Price: 0.200 On-Chain: 0.303 Social: 0.213"
    crypto_risk_pattern = re.compile(
        r'Summary:\s*([\d.]+)\s+Price:\s*([\d.]+)\s+On-Chain:\s*([\d.]+)\s+Social:\s*([\d.]+)'
    )
    crypto_match = crypto_risk_pattern.search(snapshot_text)
    if crypto_match:
        result["crypto_risk"]["summary"] = float(crypto_match.group(1))
        result["crypto_risk"]["price_risk"] = float(crypto_match.group(2))
        result["crypto_risk"]["onchain_risk"] = float(crypto_match.group(3))
        result["crypto_risk"]["social_risk"] = float(crypto_match.group(4))

    # --- Extract Macro Recession Risk from img alt text ---
    # Format: "0.008 0.008 ... Employment: 0.008 National Income And Product: 0.049 Production And Business: 0.008"
    recession_pattern = re.compile(
        r'Employment:\s*([\d.]+)\s+National Income And Product:\s*([\d.]+)\s+Production And Business:\s*([\d.]+)'
    )
    recession_match = recession_pattern.search(snapshot_text)
    if recession_match:
        result["macro_risk"]["recession_employment"] = float(recession_match.group(1))
        result["macro_risk"]["recession_income"] = float(recession_match.group(2))
        result["macro_risk"]["recession_production"] = float(recession_match.group(3))
        # Composite is the max of the three (or the first number in the img text)
        components = [float(recession_match.group(i)) for i in (1, 2, 3)]
        result["macro_risk"]["recession_composite"] = max(components)

    # Also try to extract the headline recession number
    recession_headline = re.compile(r'Macro Recession Risk.*?(\d+\.\d+)', re.DOTALL)
    rh_match = recession_headline.search(snapshot_text)
    if rh_match:
        result["macro_risk"]["recession_risk"] = float(rh_match.group(1))

    # --- Extract BTC Dominance ---
    dom_pattern = re.compile(
        r'With Stables:\s*([\d.]+)%.*?Without Stables:\s*([\d.]+)%'
    )
    dom_match = dom_pattern.search(snapshot_text)
    if dom_match:
        result["dominance"]["btc_with_stables"] = float(dom_match.group(1))
        result["dominance"]["btc_without_stables"] = float(dom_match.group(2))

    # --- Extract Market Cap Log Regression ---
    val_pattern = re.compile(
        r'CMC:\s*([\d.]+[TBMK]?).*?Trend:\s*([\d.]+[TBMK]?).*?(?:Under|Over)valuation:\s*(-?[\d.]+)%'
    )
    val_match = val_pattern.search(snapshot_text)
    if val_match:
        result["valuation"]["cmc"] = val_match.group(1)
        result["valuation"]["trend"] = val_match.group(2)
        result["valuation"]["deviation_pct"] = float(val_match.group(3))

    # --- Extract Current BTC Risk from Color-Coded chart ---
    btc_risk_pattern = re.compile(r'Current risk:\s*([\d.]+)')
    btc_risk_match = btc_risk_pattern.search(snapshot_text)
    if btc_risk_match:
        result["crypto_risk"]["btc_risk_colorcoded"] = float(btc_risk_match.group(1))

    # --- Extract Unemployment Rate ---
    unemp_pattern = re.compile(r'Latest Value:\s*([\d.]+)%\s*\((\d+/\d+/\d+)\)')
    unemp_match = unemp_pattern.search(snapshot_text)
    if unemp_match:
        result["macro_risk"]["unemployment_rate"] = float(unemp_match.group(1))
        result["macro_risk"]["unemployment_date"] = unemp_match.group(2)

    # --- Extract Macro Calendar entries ---
    # M2 Money Supply
    m2_pattern = re.compile(r'M2 Money Supply.*?Result:\s*\$([\d.]+[TBMK]?)', re.DOTALL)
    m2_match = m2_pattern.search(snapshot_text)
    if m2_match:
        result["macro_calendar"]["m2_supply"] = "$" + m2_match.group(1)

    # M1 Money Supply
    m1_pattern = re.compile(r'M1 Money Supply.*?Result:\s*\$([\d.]+[TBMK]?)', re.DOTALL)
    m1_match = m1_pattern.search(snapshot_text)
    if m1_match:
        result["macro_calendar"]["m1_supply"] = "$" + m1_match.group(1)

    # Consumer Confidence
    cc_pattern = re.compile(r'Consumer Confidence.*?Result:\s*([\d.]+)', re.DOTALL)
    cc_match = cc_pattern.search(snapshot_text)
    if cc_match:
        result["macro_calendar"]["consumer_confidence"] = float(cc_match.group(1))

    # Retail Money Market Funds
    rmm_pattern = re.compile(r'Retail Money Market Funds.*?Result:\s*\$([\d.]+[TBMK]?)', re.DOTALL)
    rmm_match = rmm_pattern.search(snapshot_text)
    if rmm_match:
        result["macro_calendar"]["retail_money_market"] = "$" + rmm_match.group(1)

    return result


def format_itc_for_prompt(data: Dict) -> str:
    """
    Format ITC data into a clean text block for Agent 1's prompt.
    
    This goes alongside the Assembly data and FRED macro data
    as supplementary context for regime classification.
    """
    if not data or (not data.get("crypto_risk") and not data.get("macro_risk")):
        return "ITC DATA: NOT AVAILABLE"

    lines = [
        "=" * 55,
        f"ITC (INTO THE CRYPTOVERSE) DATA",
        f"Scraped: {data.get('timestamp', 'unknown')}",
        "=" * 55,
    ]

    # Crypto Risk Composite
    cr = data.get("crypto_risk", {})
    if cr:
        lines.append("")
        lines.append("CRYPTO RISK INDICATORS (0 = cycle floor, 1 = cycle peak):")
        if "summary" in cr:
            risk_val = cr["summary"]
            if risk_val < 0.25:
                zone = "ACCUMULATION ZONE — historically best risk/reward"
            elif risk_val < 0.45:
                zone = "LOW RISK — favorable entry conditions"
            elif risk_val < 0.65:
                zone = "MODERATE RISK — mid-cycle"
            elif risk_val < 0.80:
                zone = "ELEVATED RISK — late cycle, trim exposure"
            else:
                zone = "EXTREME RISK — historically near cycle tops"
            lines.append(f"  Summary Risk: {risk_val} → {zone}")
        if "price_risk" in cr:
            lines.append(f"  Price Component: {cr['price_risk']}")
        if "onchain_risk" in cr:
            lines.append(f"  On-Chain Component: {cr['onchain_risk']}")
        if "social_risk" in cr:
            lines.append(f"  Social Component: {cr['social_risk']}")
        if "btc_risk" in cr:
            lines.append(f"  BTC Risk: {cr['btc_risk']}  (price: ${cr.get('btc_price', '?')})")
        if "eth_risk" in cr:
            lines.append(f"  ETH Risk: {cr['eth_risk']}  (price: ${cr.get('eth_price', '?')})")

    # Macro Recession Risk
    mr = data.get("macro_risk", {})
    if mr:
        lines.append("")
        lines.append("MACRO RECESSION RISK (ITC composite model, 0-1 scale):")
        rc = mr.get("recession_composite") or mr.get("recession_risk")
        if rc is not None:
            if rc < 0.05:
                rlabel = "VERY LOW — expansion"
            elif rc < 0.15:
                rlabel = "LOW — no imminent recession signals"
            elif rc < 0.35:
                rlabel = "MODERATE — watch for deterioration"
            elif rc < 0.60:
                rlabel = "ELEVATED — recession becoming probable"
            else:
                rlabel = "HIGH — recession likely underway or imminent"
            lines.append(f"  Recession Risk: {rc} → {rlabel}")
        if "recession_employment" in mr:
            lines.append(f"  Employment sub: {mr['recession_employment']}")
        if "recession_income" in mr:
            lines.append(f"  National Income sub: {mr['recession_income']}")
        if "recession_production" in mr:
            lines.append(f"  Production sub: {mr['recession_production']}")
        if "unemployment_rate" in mr:
            lines.append(f"  Unemployment Rate: {mr['unemployment_rate']}% (as of {mr.get('unemployment_date', '?')})")
        if "sp500_risk" in mr:
            lines.append(f"  S&P 500 Risk: {mr['sp500_risk']}  (price: ${mr.get('sp500_price', '?')})")
        if "dxy_risk" in mr:
            lines.append(f"  DXY Risk: {mr['dxy_risk']}  (value: {mr.get('dxy_value', '?')})")
        if "gold_risk" in mr:
            lines.append(f"  Gold Risk: {mr['gold_risk']}  (price: ${mr.get('gold_price', '?')})")

    # Dominance
    dom = data.get("dominance", {})
    if dom:
        lines.append("")
        lines.append("BTC DOMINANCE (risk rotation signal):")
        if "btc_with_stables" in dom:
            lines.append(f"  With Stablecoins: {dom['btc_with_stables']}%")
        if "btc_without_stables" in dom:
            lines.append(f"  Without Stablecoins: {dom['btc_without_stables']}%")
        dom_val = dom.get("btc_with_stables") or dom.get("btc_without_stables")
        if dom_val:
            if dom_val > 60:
                lines.append("  Interpretation: HIGH dominance → flight to quality within crypto, risk-off signal")
            elif dom_val > 50:
                lines.append("  Interpretation: MODERATE dominance → BTC leading but alts participating")
            elif dom_val > 40:
                lines.append("  Interpretation: LOW dominance → alt season emerging, risk appetite high")
            else:
                lines.append("  Interpretation: VERY LOW dominance → deep alt season, euphoria risk")

    # Valuation
    val = data.get("valuation", {})
    if val:
        lines.append("")
        lines.append("CRYPTO MARKET CAP vs LOG REGRESSION TRENDLINE:")
        if "cmc" in val:
            lines.append(f"  Current Market Cap: ${val['cmc']}")
        if "trend" in val:
            lines.append(f"  Fair Value Trend: ${val['trend']}")
        if "deviation_pct" in val:
            dev = val["deviation_pct"]
            if dev < -40:
                dlabel = "DEEP VALUE — major undervaluation vs historical trend"
            elif dev < -20:
                dlabel = "UNDERVALUED — below fair value trend"
            elif dev < 0:
                dlabel = "SLIGHTLY BELOW trend"
            elif dev < 20:
                dlabel = "SLIGHTLY ABOVE trend"
            elif dev < 50:
                dlabel = "OVERVALUED — above fair value trend"
            else:
                dlabel = "EXTREME OVERVALUATION — historically unsustainable"
            lines.append(f"  Deviation: {dev}% → {dlabel}")

    # Macro Calendar highlights
    mc = data.get("macro_calendar", {})
    if mc:
        lines.append("")
        lines.append("RECENT MACRO CALENDAR (from ITC):")
        for key, val in mc.items():
            label = key.replace("_", " ").title()
            lines.append(f"  {label}: {val}")

    # Asset risk summary table
    assets = data.get("assets", [])
    if assets:
        lines.append("")
        lines.append(f"ASSET RISK TABLE ({len(assets)} assets tracked):")
        # Group by type
        crypto = [a for a in assets if a["ticker"] in 
                  {"BTC","ETH","BNB","XRP","SOL","TRX","DOGE","ADA","XMR","LINK"}]
        tradfi = [a for a in assets if a["ticker"] in 
                  {"SP500","DXY","GOLD","SILVER","AAPL","NFLX","MSTR","TSLA"}]
        
        if crypto:
            lines.append("  Crypto:")
            for a in crypto:
                lines.append(
                    f"    {a['ticker']:6s} ${a['price']:>10s} | 24h: {a['change_24h']:>7s} | "
                    f"7d: {a['change_7d']:>7s} | Risk: {a['fiat_risk']}"
                )
        if tradfi:
            lines.append("  TradFi:")
            for a in tradfi:
                lines.append(
                    f"    {a['ticker']:6s} ${a['price']:>10s} | 24h: {a['change_24h']:>7s} | "
                    f"7d: {a['change_7d']:>7s} | Risk: {a['fiat_risk']}"
                )

    return "\n".join(lines)


def load_itc_data(path: str = "output/itc_data.json") -> Optional[Dict]:
    """Load pre-scraped ITC data from output file."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[ITC] Failed to load data: {e}")
        return None


def save_itc_data(data: Dict, path: str = "output/itc_data.json"):
    """Save ITC data to output file."""
    os.makedirs(os.path.dirname(path) or "output", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[ITC] Data saved to {path}")


def is_itc_stale(path: str = "output/itc_data.json", max_hours: float = 18) -> bool:
    """Check if ITC data file is stale (older than max_hours)."""
    if not os.path.exists(path):
        return True
    try:
        with open(path) as f:
            data = json.load(f)
        ts = data.get("timestamp", "")
        if not ts:
            return True
        data_time = datetime.fromisoformat(ts.split("+")[0])
        age_hours = (datetime.now() - data_time).total_seconds() / 3600
        print(f"[ITC] Data age: {age_hours:.1f}h (stale threshold: {max_hours}h)")
        return age_hours > max_hours
    except Exception:
        return True


if __name__ == "__main__":
    # Test: load and display
    data = load_itc_data()
    if data:
        print(format_itc_for_prompt(data))
    else:
        print("No ITC data found. Run the browser scraper first.")
        print("To test parsing, pass a snapshot text file as argument.")
