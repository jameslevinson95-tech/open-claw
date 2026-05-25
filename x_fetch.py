"""
X/Twitter Smart Money Fetch — Official X Developer API
Uses the search/recent endpoint with X_BEARER_TOKEN (pay-per-use tier).

Queries surviving tickers against CURATED_ACCOUNTS list over a 7-day window.
Saves clean JSON to output/smart_money_mentions.json for Agent 3.

Usage:
  python3 x_fetch.py MSFT JPM           # Fetch mentions for specific tickers
  python3 x_fetch.py --from-agent2      # Read tickers from Agent 2 output
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# X API v2 search/recent endpoint
X_API_URL = "https://api.twitter.com/2/tweets/search/recent"

# Curated smart money accounts — INSTITUTIONAL MACRO/QUANT/FUNDAMENTAL ONLY
# Retail, options flow, and finfluencer handles PURGED per Jamie's directive (May 19)
# REMOVED: unusual_whales, WallStJesus, OptionsHawk, jimcramer, DumbMoneyTV
CURATED_ACCOUNTS = [
    # --- MACRO FLOW/SENTIMENT (institutional grade) ---
    "DeItaone",            # Institutional news wire
    "Fxhedgers",           # Macro/FX institutional feed
    "zaborsky",            # Macro strategist
    "GurufocusData",       # Fundamental data aggregator
    "PeterSchiff",         # Macro economist, hard assets
    "TruthGundlach",       # Jeffrey Gundlach, DoubleLine Capital
    "elerianm",            # Mohamed El-Erian, Allianz/PIMCO
    "SqueezeMetrics",      # DIX/GEX quant model
    "sentimentrader",      # Institutional sentiment data
    "DarkPoolChart",       # Dark pool flow analytics
    "VolSignals",          # Volatility structure analysis
    # --- MACRO_ANALYSTS (central bank, liquidity, regime) ---
    "MacroAlf",            # Alfonso Peccatiello, ex-ING $20B portfolio
    "FedGuy12",            # Joseph Wang, ex-NY Fed open market desk
    "biancoresearch",      # Jim Bianco, Bianco Research
    "TheMichaelEvery",     # Michael Every, Rabobank Global Strategist
    # --- SECTOR_SPECIALISTS ---
    "Josh_Young_1",        # Energy/oil specialist
    "brandon_munro",       # Uranium/nuclear sector
    "UraniumInsider",      # Uranium sector intelligence
    "PeterKolchinsky",     # Biotech/healthcare specialist
    "dylanpatel",          # Semiconductor/AI sector (SemiAnalysis)
    # --- QUANT_SYSTEMATIC (gamma, vol structure, quant models) ---
    "spotgamma",           # Options gamma exposure modeling
    "choffstein",          # Corey Hoffstein, Newfound Research
    "nope_its_lily",       # Lily Francus, options/vol quant
    # --- HEDGE_FUND_PRINCIPALS ---
    "boazweinstein",       # Boaz Weinstein, Saba Capital
    "CliffordAsness",      # Cliff Asness, AQR Capital
    "DylanLeClair_",       # Dylan LeClair, BTC/macro analyst
    "cngarabedian",        # Institutional fund manager
    "RayDalio",            # Ray Dalio, Bridgewater founder
    # --- CONTRARIAN_VOICES ---
    "WallStCynic",         # Contrarian macro voice
    "rampagingruss",       # Contrarian analyst
    "orrdavid",            # David Orr, contrarian macro
    # REMOVED per Jamie directive (May 19): benjamincowen, 0xReflection,
    # InTheAssembly, NoLimitGains, realDonaldTrump, TheGoldPrairie, great_martis
]

# Chunking config: X API Basic tier has 512-char query limit
# ~11 accounts per chunk keeps queries under limit for 31 accounts (3 chunks)
ACCOUNTS_PER_CHUNK = 11

# Rate limit: 450 requests per 15-min window on Basic tier
# We pace our requests to stay well under
REQUEST_DELAY = 2  # seconds between requests


def get_bearer_token() -> str:
    """Get X_BEARER_TOKEN from environment."""
    token = os.environ.get("X_BEARER_TOKEN", "")
    if not token:
        raise RuntimeError(
            "X_BEARER_TOKEN not set. Add it to .env or set as environment variable."
        )
    return token


def build_query(ticker: str, accounts: list) -> str:
    """
    Build a Twitter API v2 search query for a ticker filtered by a chunk of accounts.
    Query must stay under 512 chars for Basic tier.
    
    Example: ($MSFT OR MSFT) (from:DeItaone OR from:MacroAlf OR ...)
    """
    ticker_terms = f"(${ticker} OR {ticker})"
    account_filters = " OR ".join([f"from:{acct}" for acct in accounts])
    query = f"{ticker_terms} ({account_filters})"
    
    if len(query) > 512:
        print(f"  [X Fetch] WARNING: Query chunk for {ticker} is {len(query)} chars (over 512 limit)")
    
    return query


def chunk_accounts(accounts: list, chunk_size: int = None) -> list:
    """
    Split the curated accounts into chunks that produce queries under 512 chars.
    Returns list of account-list chunks.
    """
    size = chunk_size or ACCOUNTS_PER_CHUNK
    return [accounts[i:i + size] for i in range(0, len(accounts), size)]


def search_recent_tweets(
    query: str,
    bearer_token: str,
    max_results: int = 100,
    start_time: str = None,
) -> list:
    """
    Call X API v2 search/recent endpoint.
    Returns list of tweet objects.
    """
    headers = {
        "Authorization": f"Bearer {bearer_token}",
    }
    
    params = {
        "query": query,
        "max_results": min(max_results, 100),  # API max is 100 per page
        "tweet.fields": "created_at,author_id,public_metrics,text",
        "user.fields": "username,name",
        "expansions": "author_id",
    }
    
    if start_time:
        params["start_time"] = start_time
    
    all_tweets = []
    next_token = None
    pages = 0
    max_pages = 5  # Cap pagination to avoid runaway costs
    
    while pages < max_pages:
        if next_token:
            params["next_token"] = next_token
        
        response = requests.get(X_API_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code == 429:
            # Rate limited — wait and retry
            retry_after = int(response.headers.get("x-rate-limit-reset", 60)) - int(time.time())
            retry_after = max(retry_after, 15)
            print(f"  [X Fetch] Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        
        if response.status_code != 200:
            print(f"  [X Fetch] API error {response.status_code}: {response.text[:200]}")
            break
        
        data = response.json()
        
        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        
        # Enrich tweets with username
        for tweet in tweets:
            author_id = tweet.get("author_id")
            if author_id in users:
                tweet["username"] = users[author_id].get("username", "unknown")
                tweet["author_name"] = users[author_id].get("name", "unknown")
        
        all_tweets.extend(tweets)
        
        # Check for pagination
        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break
        
        pages += 1
        time.sleep(REQUEST_DELAY)
    
    return all_tweets


def fetch_smart_money_mentions(tickers: list) -> dict:
    """
    Fetch smart money X mentions for a list of tickers.
    7-day lookback window using search/recent endpoint.
    
    Returns: {
        "MSFT": [{"text": "...", "username": "...", "created_at": "...", ...}, ...],
        "JPM": [...],
        ...
    }
    """
    bearer_token = get_bearer_token()
    
    # 7-day lookback window (search/recent max is ~7 days anyway)
    start_time = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    mentions = {}
    
    # Chunk accounts to keep queries under 512-char API limit
    account_chunks = chunk_accounts(CURATED_ACCOUNTS)
    print(f"[X Fetch] Split {len(CURATED_ACCOUNTS)} accounts into {len(account_chunks)} chunks of ~{ACCOUNTS_PER_CHUNK}")
    
    for ticker in tickers:
        print(f"[X Fetch] Searching for {ticker} mentions from curated accounts...")
        
        all_tweets_for_ticker = []
        
        for chunk_idx, chunk in enumerate(account_chunks):
            query = build_query(ticker, chunk)
            
            try:
                tweets = search_recent_tweets(
                    query=query,
                    bearer_token=bearer_token,
                    max_results=100,
                    start_time=start_time,
                )
                all_tweets_for_ticker.extend(tweets)
            except Exception as e:
                print(f"  [X Fetch] {ticker} chunk {chunk_idx + 1}: Error -- {e}")
            
            # Pace between chunks
            time.sleep(REQUEST_DELAY)
        
        # Deduplicate by tweet ID
        seen_ids = set()
        clean_tweets = []
        for t in all_tweets_for_ticker:
            tid = t.get("id", "")
            if tid in seen_ids:
                continue
            seen_ids.add(tid)
            clean_tweets.append({
                "text": t.get("text", ""),
                "username": t.get("username", "unknown"),
                "author_name": t.get("author_name", "unknown"),
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),
            })
        
        mentions[ticker] = clean_tweets
        print(f"  [X Fetch] {ticker}: {len(clean_tweets)} mentions found ({len(account_chunks)} chunks queried)")
    
    return mentions


def run_x_fetch(tickers: list = None) -> dict:
    """
    Main entry point. Fetches X mentions and saves to output file.
    """
    # Load tickers from Agent 2 if not provided
    if not tickers:
        agent2_path = "output/agent2_candidates.json"
        if os.path.exists(agent2_path):
            with open(agent2_path) as f:
                agent2 = json.load(f)
            tickers = [c.get("ticker") for c in agent2.get("candidates", [])]
        
        if not tickers:
            raise RuntimeError("No tickers provided and no Agent 2 candidates found.")
    
    print(f"[X Fetch] Fetching smart money mentions for: {tickers}")
    print(f"[X Fetch] Curated accounts: {len(CURATED_ACCOUNTS)}")
    print(f"[X Fetch] Lookback: 7 days")
    
    mentions = fetch_smart_money_mentions(tickers)
    
    # Save output
    output = {
        "timestamp": datetime.now().isoformat(),
        "lookback_days": 7,
        "curated_accounts": CURATED_ACCOUNTS,
        "tickers_queried": tickers,
        "mentions": mentions,
        "total_mentions": sum(len(m) for m in mentions.values()),
    }
    
    os.makedirs("output", exist_ok=True)
    output_path = "output/smart_money_mentions.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n[X Fetch] Complete. {output['total_mentions']} total mentions saved to {output_path}")
    
    # Summary
    for ticker, tweets in mentions.items():
        if tweets:
            accounts_seen = set(t["username"] for t in tweets)
            print(f"  {ticker}: {len(tweets)} mentions from {len(accounts_seen)} accounts ({', '.join(accounts_seen)})")
        else:
            print(f"  {ticker}: No mentions from curated accounts")
    
    return output


if __name__ == "__main__":
    if "--from-agent2" in sys.argv:
        run_x_fetch()
    elif len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:] if not t.startswith("-")]
        run_x_fetch(tickers)
    else:
        print("Usage:")
        print("  python3 x_fetch.py MSFT JPM        # Specific tickers")
        print("  python3 x_fetch.py --from-agent2    # Read from Agent 2 output")
