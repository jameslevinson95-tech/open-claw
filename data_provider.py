"""
data_provider.py — Unified Data Provider Abstraction

Single seam for all market data access. Routes through paid vendors
(Massive/Polygon, Schwab) instead of yfinance scraping.

Fallback hierarchy per method:
  get_bars:    Massive → yfinance (deprecated fallback) → raise DataUnavailable
  get_quote:   Schwab → raise DataUnavailable (broker feed ONLY)
  get_index:   Massive I:<SYM> → Schwab → ETF proxy → raise DataUnavailable
  get_corporate_actions: Massive splits → [] with log warning

Rate limiting: Token-bucket for Massive free tier (5 calls/min).
"""
import os
import time
import logging
import threading
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger("DataProvider")


class DataUnavailable(Exception):
    """Raised when no data source can fulfill the request."""
    pass


# ── Rate Limiter ─────────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe token-bucket rate limiter for Massive free tier (5 calls/min).
    
    The read-modify-write on _timestamps is protected by a Lock to prevent
    concurrent ThreadPoolExecutor workers from all seeing "under limit" at
    the same millisecond and firing parallel requests that trigger 429s.
    """

    def __init__(self, max_calls: int = 5, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window = window_seconds
        self._timestamps: list = []
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            self._timestamps = [t for t in self._timestamps if now - t < self.window]
            if len(self._timestamps) >= self.max_calls:
                sleep_time = self.window - (now - self._timestamps[0]) + 0.5
                if sleep_time > 0:
                    logger.info(f"Rate limit: waiting {sleep_time:.1f}s")
                    # Release lock during sleep so other threads can check
                    self._lock.release()
                    time.sleep(sleep_time)
                    self._lock.acquire()
            self._timestamps.append(time.time())


# ── Data Provider ────────────────────────────────────────────────────

class DataProvider:
    """
    Unified market data provider with cascading fallbacks.

    Usage:
        dp = DataProvider()
        bars = dp.get_bars("AAPL", lookback_days=60)
        index = dp.get_index("VIX")
        splits = dp.get_corporate_actions("NVDA", since_days=7)
    """

    def __init__(self):
        self._massive_key = os.environ.get("MASSIVE_API_KEY", "")
        self._massive_base = "https://api.massive.com"
        self._limiter = _TokenBucket(max_calls=5, window_seconds=60)

        # Schwab credentials loaded lazily
        self._schwab_quotes_fn = None

    # ── Public API ───────────────────────────────────────────────────

    def get_bars(
        self,
        ticker: str,
        lookback_days: int = 60,
        timespan: str = "day",
    ) -> pd.DataFrame:
        """
        OHLCV bars, newest last. Columns: Open, High, Low, Close, Volume.
        Fallback: Massive → yfinance (deprecated) → raise DataUnavailable.
        """
        # 1. Massive (Polygon)
        if self._massive_key:
            try:
                df = self._massive_bars(ticker, lookback_days, timespan)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"Massive bars failed for {ticker}: {e}")

        # 2. yfinance fallback (deprecated — will be removed)
        try:
            df = self._yfinance_bars(ticker, lookback_days, timespan)
            if df is not None and not df.empty:
                logger.info(f"[DataProvider] {ticker} served from yfinance fallback")
                return df
        except Exception as e:
            logger.warning(f"yfinance bars failed for {ticker}: {e}")

        raise DataUnavailable(f"No bar data available for {ticker}")

    def get_quote(self, ticker: str) -> dict:
        """
        Live bid/ask/last for execution. Broker feed ONLY.
        Fallback: Schwab → raise DataUnavailable.
        (Execution paths must price against the venue we trade on.)
        """
        # Schwab
        try:
            quotes = self._schwab_quotes([ticker])
            if ticker in quotes:
                return quotes[ticker]
        except Exception as e:
            logger.warning(f"Schwab quote failed for {ticker}: {e}")

        raise DataUnavailable(f"No live quote available for {ticker}")

    def get_index(self, symbol: str) -> dict:
        """
        Index level for VIX/SPX.
        Fallback: Massive I:<SYM> → Schwab $<SYM> → ETF proxy → raise.
        Returns: {'symbol', 'value', 'source', 'is_proxy': bool}
        """
        symbol = symbol.upper().replace("^", "")
        massive_ticker = f"I:{symbol}"
        etf_proxy = {"VIX": "VIXY", "SPX": "SPY"}.get(symbol)

        # 1. Massive index snapshot
        if self._massive_key:
            try:
                val = self._massive_index(massive_ticker)
                if val is not None:
                    return {"symbol": symbol, "value": val, "source": "massive", "is_proxy": False}
            except Exception as e:
                logger.warning(f"Massive index {massive_ticker} failed: {e}")

        # 2. Schwab $VIX / $SPX
        try:
            schwab_ticker = f"${symbol}"
            quotes = self._schwab_quotes([schwab_ticker])
            if schwab_ticker in quotes:
                val = quotes[schwab_ticker].get("last") or quotes[schwab_ticker].get("bid")
                if val and val > 0:
                    return {"symbol": symbol, "value": float(val), "source": "schwab", "is_proxy": False}
        except Exception as e:
            logger.warning(f"Schwab index ${symbol} failed: {e}")

        # 3. ETF proxy
        if etf_proxy:
            try:
                bars = self.get_bars(etf_proxy, lookback_days=5, timespan="day")
                if not bars.empty:
                    proxy_val = float(bars["Close"].iloc[-1])
                    logger.info(f"[DataProvider] {symbol} served via ETF proxy {etf_proxy} = {proxy_val}")
                    return {"symbol": symbol, "value": proxy_val, "source": f"etf_proxy_{etf_proxy}", "is_proxy": True}
            except Exception as e:
                logger.warning(f"ETF proxy {etf_proxy} for {symbol} failed: {e}")

        raise DataUnavailable(f"No index data available for {symbol}")

    def get_corporate_actions(self, ticker: str, since_days: int = 7) -> list:
        """
        Recent splits/dividends.
        Fallback: Massive → [] with log warning.
        """
        # 1. Massive splits endpoint
        if self._massive_key:
            try:
                return self._massive_splits(ticker, since_days)
            except Exception as e:
                logger.warning(f"Massive splits failed for {ticker}: {e}")

        logger.warning(f"[DataProvider] No corporate action data available for {ticker}")
        return []

    def get_news(self, ticker: str, limit: int = 5) -> list:
        """
        Recent news headlines for a ticker.
        Fallback: Massive -> yfinance -> [].
        Returns list of dicts with 'title', 'publisher', 'published'.
        """
        # 1. Massive news endpoint
        if self._massive_key:
            try:
                articles = self._massive_news(ticker, limit)
                if articles:
                    return articles
            except Exception as e:
                logger.warning(f"Massive news failed for {ticker}: {e}")

        # 2. yfinance fallback
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            news_items = stock.news or []
            return [
                {
                    "title": n.get("title", ""),
                    "publisher": n.get("publisher", ""),
                    "published": n.get("providerPublishTime", ""),
                }
                for n in news_items[:limit]
            ]
        except Exception as e:
            logger.warning(f"yfinance news failed for {ticker}: {e}")

        return []

    # ── Massive (Polygon) Internals ──────────────────────────────────

    def _massive_get(self, endpoint: str, params: dict = None) -> dict:
        """Authenticated GET to Massive with rate limiting."""
        self._limiter.wait()
        params = params or {}
        params["apiKey"] = self._massive_key
        url = f"{self._massive_base}{endpoint}"
        # 5s timeout: corp-action/split checks are non-fatal (caller passes on
        # failure), so don't let a slow/down Massive API stall the whole pipeline.
        resp = requests.get(url, params=params, timeout=5)

        if resp.status_code == 403:
            logger.warning(f"Massive 403 (not entitled): {endpoint}")
            return {}
        if resp.status_code == 429:
            logger.warning(f"Massive 429 (rate limited): {endpoint}")
            time.sleep(12)
            resp = requests.get(url, params=params, timeout=5)

        resp.raise_for_status()
        return resp.json()

    def _massive_bars(self, ticker: str, lookback_days: int, timespan: str) -> Optional[pd.DataFrame]:
        """Fetch OHLCV bars from Massive/Polygon aggregates endpoint."""
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        multiplier = 1

        data = self._massive_get(
            f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start}/{end}",
            params={"limit": 5000, "sort": "asc"},
        )

        results = data.get("results", [])
        if not results:
            return None

        df = pd.DataFrame(results)
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume", "t": "timestamp"})
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("Date")
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        return df

    def _massive_index(self, ticker: str) -> Optional[float]:
        """Fetch index snapshot from Massive. Returns value or None."""
        # Try previous day endpoint first (works on broader tiers)
        data = self._massive_get(f"/v2/aggs/ticker/{ticker}/prev")
        results = data.get("results", [])
        if results:
            return float(results[0].get("c", 0))

        # Try snapshot endpoint
        data = self._massive_get("/v3/snapshot/indices", params={"ticker.any_of": ticker})
        results = data.get("results", [])
        if results:
            session = results[0].get("session", {}) or results[0].get("value", {})
            return float(session.get("close", session.get("value", 0)))

        return None

    def _massive_splits(self, ticker: str, since_days: int) -> list:
        """Fetch recent stock splits from Massive/Polygon reference endpoint."""
        data = self._massive_get("/v3/reference/splits", params={
            "ticker": ticker,
            "limit": 10,
            "sort": "execution_date",
            "order": "desc",
        })

        results = data.get("results", [])
        cutoff = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
        recent = []
        for split in results:
            if split.get("execution_date", "1970-01-01") >= cutoff:
                recent.append({
                    "ticker": split.get("ticker"),
                    "execution_date": split.get("execution_date"),
                    "split_from": split.get("split_from"),
                    "split_to": split.get("split_to"),
                })
        return recent

    def _massive_news(self, ticker: str, limit: int = 5) -> list:
        """Fetch news articles from Massive/Polygon reference endpoint."""
        data = self._massive_get("/v2/reference/news", params={
            "ticker": ticker,
            "limit": limit,
            "sort": "published_utc",
            "order": "desc",
        })

        results = data.get("results", [])
        return [
            {
                "title": article.get("title", ""),
                "publisher": article.get("publisher", {}).get("name", "") if isinstance(article.get("publisher"), dict) else str(article.get("publisher", "")),
                "published": article.get("published_utc", ""),
            }
            for article in results
        ]

    # ── Schwab Internals ─────────────────────────────────────────────

    def _schwab_quotes(self, tickers: list) -> dict:
        """Lazy-load and call Schwab quote function."""
        if self._schwab_quotes_fn is None:
            try:
                from schwab_data import fetch_schwab_quotes
                self._schwab_quotes_fn = fetch_schwab_quotes
            except ImportError:
                raise DataUnavailable("Schwab module not available")
        return self._schwab_quotes_fn(tickers)

    # ── yfinance Fallback (deprecated) ───────────────────────────────

    @staticmethod
    def _yfinance_bars(ticker: str, lookback_days: int, timespan: str) -> Optional[pd.DataFrame]:
        """Deprecated yfinance fallback. Will be removed in a future PR."""
        import yfinance as yf
        period_map = {
            "day": f"{lookback_days}d" if lookback_days <= 30 else "3mo" if lookback_days <= 90 else "6mo",
        }
        interval_map = {"day": "1d", "minute": "1m", "hour": "1h"}

        period = period_map.get(timespan, "3mo")
        interval = interval_map.get(timespan, "1d")

        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return None

        # Normalize multi-index columns from yfinance
        if hasattr(data.columns, "levels") and len(data.columns.levels) > 1:
            data = data.droplevel(1, axis=1)

        return data[["Open", "High", "Low", "Close", "Volume"]]


# ── Mock Provider for Testing ────────────────────────────────────────

class MockDataProvider(DataProvider):
    """
    Mock provider for unit tests. Returns canned data, no network calls.

    Usage:
        bars = pd.DataFrame({'Open': [...], 'High': [...], ...})
        dp = MockDataProvider(bars={"AAPL": bars}, indices={"VIX": 18.5})
    """

    def __init__(self, bars: dict = None, quotes: dict = None, indices: dict = None, splits: dict = None, news: dict = None):
        self._canned_bars = bars or {}
        self._canned_quotes = quotes or {}
        self._canned_indices = indices or {}
        self._canned_splits = splits or {}
        self._canned_news = news or {}

    def get_bars(self, ticker: str, lookback_days: int = 60, timespan: str = "day") -> pd.DataFrame:
        if ticker in self._canned_bars:
            return self._canned_bars[ticker]
        raise DataUnavailable(f"MockDataProvider: no bars for {ticker}")

    def get_quote(self, ticker: str) -> dict:
        if ticker in self._canned_quotes:
            return self._canned_quotes[ticker]
        raise DataUnavailable(f"MockDataProvider: no quote for {ticker}")

    def get_index(self, symbol: str) -> dict:
        symbol = symbol.upper().replace("^", "")
        if symbol in self._canned_indices:
            return {"symbol": symbol, "value": self._canned_indices[symbol], "source": "mock", "is_proxy": False}
        raise DataUnavailable(f"MockDataProvider: no index for {symbol}")

    def get_corporate_actions(self, ticker: str, since_days: int = 7) -> list:
        return self._canned_splits.get(ticker, [])

    def get_news(self, ticker: str, limit: int = 5) -> list:
        return self._canned_news.get(ticker, [])


# ── Singleton ────────────────────────────────────────────────────────

_default_provider: Optional[DataProvider] = None


def get_provider() -> DataProvider:
    """Get the default DataProvider singleton."""
    global _default_provider
    if _default_provider is None:
        _default_provider = DataProvider()
    return _default_provider


def set_provider(provider: DataProvider):
    """Override the default DataProvider (for testing)."""
    global _default_provider
    _default_provider = provider
