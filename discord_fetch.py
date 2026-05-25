"""
Discord Smart Money Fetch — Pulls recent messages from curated Discord channels
for use in the Open Claw trading pipeline (Agent 3 signal verification).

Reads from The Assembly and ClearValue Investing Discord servers.
Filters for ticker mentions and saves structured JSON for Agent 3.

Uses the same Discord token and config as the daily email summarizer.

Usage:
  python3 discord_fetch.py                    # Fetch all high-signal channels (24h)
  python3 discord_fetch.py --tickers V EOG LLY  # Filter for specific tickers
  python3 discord_fetch.py --hours 48          # Custom lookback window
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Discord API
DISCORD_API = "https://discord.com/api/v10"

# Config from discord-summarizer
SUMMARIZER_CONFIG = Path("/Users/chris/code/discord-summarizer/config.json")

# High-signal channels for trading pipeline (skip lounge, scam_alert, youtube, etc.)
# Jamie's curated channel list (May 19, 2026)
HIGH_SIGNAL_CHANNELS = {
    "The Assembly": [
        # MARKETS
        "market-sentiment",    # Sentiment discussion
        "requested-analysis",  # Requested analysis
        "important-news",      # Curated important news
        "live-news",           # Breaking news
        "live-intel",          # Real-time market intelligence
        # INTELLIGENCE
        "insider-moves",       # Insider trading activity
        "flow-desk",           # Options flow, unusual activity
        "institutional-flow",  # Institutional buying/selling
        "macro-desk",          # Macro analysis
        "geo-intel",           # Geopolitical intelligence
        # CONVICTION
        "high-conviction-long-term-ideas",  # High-conviction plays
        "undervalued-stocks",  # Value plays
        "names-we-track",      # Tracked ticker discussion
    ],
    "ClearValue Investing": [
        # JD ORDERS ONLY channel — update channel name once confirmed
        "short-term-trades",   # Placeholder until Jamie confirms exact channel
    ],
}

# Ticker mention patterns
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
TICKER_WORD_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

# Common words that look like tickers but aren't
TICKER_BLACKLIST = {
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER",
    "WAS", "ONE", "OUR", "OUT", "HAS", "HIS", "HOW", "MAN", "NEW", "NOW",
    "OLD", "SEE", "WAY", "WHO", "DID", "GET", "HIM", "LET", "SAY", "SHE",
    "TOO", "USE", "DAY", "HAD", "HOT", "OIL", "SIT", "TOP", "RED", "RUN",
    "YES", "YET", "BIG", "END", "FAR", "PUT", "SET", "TRY", "ASK", "OWN",
    "WHY", "MEN", "READ", "NEED", "LAND", "JUST", "ALSO", "BEEN", "CALL",
    "VERY", "WHEN", "COME", "MADE", "FIND", "BACK", "ONLY", "LONG", "MUCH",
    "TAKE", "THAN", "THEM", "TURN", "INTO", "YEAR", "SOME", "WANT", "SHOW",
    "GOOD", "GIVE", "MOST", "TOLD", "WITH", "THIS", "THAT", "WILL", "EACH",
    "MAKE", "LIKE", "HAVE", "FROM", "WORD", "WHAT", "WERE", "DOES", "KEEP",
    "HIGH", "LOW", "BUY", "SELL", "HOLD", "LONG", "SHORT", "BULL", "BEAR",
    "IPO", "SEC", "GDP", "CPI", "FED", "IMF", "CEO", "CFO", "COO", "ETF",
    "USD", "EUR", "GBP", "JPY", "CNY", "BPS", "YOY", "QOQ", "MOM", "ATH",
    "ATL", "EPS", "PE", "PB", "ROE", "ROA", "FCF", "DCF", "EBITDA", "FOMC",
    "NFP", "PMI", "ISM", "PPI", "PCE", "TIPS", "MOVE", "DIX", "GEX",
    "MAX", "MIN", "AVG", "SUM", "NET", "WIN", "LOSS", "GAIN", "DROP",
    "RISK", "SAFE", "PUMP", "DUMP", "MOON", "DIP", "FOMO", "YOLO",
    "HUGE", "MEGA", "NICE", "LMAO", "BTFD", "HODL", "WAGMI", "NGMI",
    "NEWS", "JUST", "LOOK", "DONT", "STOP", "WAIT", "OPEN", "CLOSE",
    "RIP", "LOL", "BTW", "IMO", "TBH", "NEXT", "LAST", "WEEK", "SURE",
    "PLAY", "MOVE", "TAKE", "BEEN", "DONE", "REAL", "FREE", "BEST",
}


def load_config() -> dict:
    """Load Discord config from the summarizer."""
    if not SUMMARIZER_CONFIG.exists():
        raise FileNotFoundError(f"Discord config not found at {SUMMARIZER_CONFIG}")
    with open(SUMMARIZER_CONFIG) as f:
        return json.load(f)


def snowflake_from_datetime(dt: datetime) -> str:
    """Convert datetime to Discord snowflake for pagination."""
    discord_epoch = 1420070400000
    timestamp_ms = int(dt.timestamp() * 1000)
    return str((timestamp_ms - discord_epoch) << 22)


def fetch_channel_messages(token: str, channel_id: str, after_dt: datetime, limit: int = 200) -> list:
    """Fetch messages from a Discord channel after a given datetime."""
    headers = {"Authorization": token}
    after_snowflake = snowflake_from_datetime(after_dt)
    all_messages = []
    last_id = after_snowflake

    while True:
        params = {"after": last_id, "limit": 100}
        resp = requests.get(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=headers,
            params=params,
        )
        if resp.status_code == 403:
            return []  # No access
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 1)
            time.sleep(retry_after + 0.5)
            continue
        if resp.status_code != 200:
            return []
        messages = resp.json()
        if not messages:
            break
        all_messages.extend(messages)
        if len(messages) < 100 or len(all_messages) >= limit:
            break
        last_id = max(m["id"] for m in messages)
        time.sleep(0.5)

    return all_messages


def extract_tickers(text: str) -> list:
    """Extract stock ticker mentions from message text."""
    tickers = set()

    # $TICKER pattern (high confidence)
    for match in TICKER_PATTERN.findall(text):
        if match not in TICKER_BLACKLIST:
            tickers.add(match)

    return list(tickers)


def fetch_discord_mentions(tickers: list = None, hours: int = 24) -> dict:
    """
    Fetch Discord messages from high-signal channels and extract ticker mentions.

    Args:
        tickers: If provided, only return mentions for these tickers
        hours: Lookback window in hours (default 24)

    Returns:
        {
            "timestamp": "ISO",
            "lookback_hours": 24,
            "channels_scraped": 27,
            "total_messages": 150,
            "mentions": {
                "TICKER": [
                    {
                        "text": "message content",
                        "author": "username",
                        "channel": "channel-name",
                        "server": "server-name",
                        "timestamp": "ISO",
                        "channel_type": "flow-desk"
                    }
                ]
            }
        }
    """
    config = load_config()
    token = config["discord_token"]
    servers = config["servers"]

    after_dt = datetime.now(timezone.utc) - timedelta(hours=hours)

    all_mentions = {}  # ticker -> [mentions]
    total_messages = 0
    channels_scraped = 0

    for server_name, channel_list in HIGH_SIGNAL_CHANNELS.items():
        if server_name not in servers:
            print(f"[Discord] Server '{server_name}' not in config, skipping")
            continue

        server_config = servers[server_name]
        server_channels = server_config["channels"]

        for channel_name in channel_list:
            if channel_name not in server_channels:
                continue

            channel_id = server_channels[channel_name]
            messages = fetch_channel_messages(token, channel_id, after_dt)
            channels_scraped += 1

            for msg in messages:
                total_messages += 1
                content = msg.get("content", "")
                if not content:
                    continue

                # Also check embeds
                for embed in msg.get("embeds", []):
                    if embed.get("title"):
                        content += " " + embed["title"]
                    if embed.get("description"):
                        content += " " + embed["description"]

                found_tickers = extract_tickers(content)
                author = msg.get("author", {}).get("username", "unknown")
                msg_time = msg.get("timestamp", "")

                for ticker in found_tickers:
                    if tickers and ticker not in tickers:
                        continue  # Skip if not in requested ticker list

                    if ticker not in all_mentions:
                        all_mentions[ticker] = []

                    all_mentions[ticker].append({
                        "text": content[:500],  # Truncate long messages
                        "author": author,
                        "channel": channel_name,
                        "server": server_name,
                        "timestamp": msg_time,
                    })

            if messages:
                print(f"  [Discord] {server_name}/{channel_name}: {len(messages)} messages")

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lookback_hours": hours,
        "channels_scraped": channels_scraped,
        "total_messages": total_messages,
        "tickers_found": len(all_mentions),
        "mentions": all_mentions,
    }

    # Save output
    os.makedirs("output", exist_ok=True)
    with open("output/discord_mentions.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Summary
    print(f"\n[Discord] Complete. {channels_scraped} channels, {total_messages} messages, {len(all_mentions)} tickers mentioned")
    for ticker in sorted(all_mentions, key=lambda t: len(all_mentions[t]), reverse=True)[:10]:
        mentions = all_mentions[ticker]
        channels = set(m["channel"] for m in mentions)
        print(f"  {ticker}: {len(mentions)} mentions across {len(channels)} channels")

    return result


def format_discord_for_agent3(discord_data: dict, tickers: list) -> str:
    """Format Discord mentions for Agent 3's prompt."""
    mentions = discord_data.get("mentions", {})
    lines = [
        f"DISCORD SMART MONEY MENTIONS (last {discord_data.get('lookback_hours', 24)}h)",
        f"Sources: The Assembly + ClearValue Investing ({discord_data.get('channels_scraped', 0)} channels)",
        "=" * 50,
    ]

    for ticker in tickers:
        ticker_mentions = mentions.get(ticker, [])
        if not ticker_mentions:
            lines.append(f"\n{ticker} -- 0 Discord mentions (silent)")
        else:
            channels = set(m["channel"] for m in ticker_mentions)
            lines.append(f"\n{ticker} -- {len(ticker_mentions)} mentions across {', '.join(channels)}:")
            for m in ticker_mentions[:5]:  # Cap at 5 per ticker
                lines.append(f"  [{m['server']}/{m['channel']}] @{m['author']}: {m['text'][:200]}")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discord Smart Money Fetch")
    parser.add_argument("--tickers", nargs="*", help="Filter for specific tickers")
    parser.add_argument("--hours", type=int, default=24, help="Lookback hours (default 24)")
    args = parser.parse_args()

    print(f"[Discord] Fetching messages from last {args.hours} hours...")
    result = fetch_discord_mentions(tickers=args.tickers, hours=args.hours)
