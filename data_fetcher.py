# data_fetcher.py — market data via yfinance

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def fetch_ohlcv(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Download OHLCV data for a single symbol.

    Args:
        symbol:   Ticker like 'AAPL', 'MSFT'
        period:   '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'
        interval: '1m','5m','15m','1h','1d','1wk'

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        print(f"  ⚠  No data returned for {symbol}")
        return pd.DataFrame()

    # Clean up — drop dividends/splits columns if present
    drop_cols = [c for c in ("Dividends", "Stock Splits", "Capital Gains") if c in df.columns]
    df.drop(columns=drop_cols, inplace=True)

    df.index.name = "Date"
    return df


def fetch_realtime_quote(symbol: str) -> dict:
    """Return latest price, volume, and change for a symbol."""
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info

    try:
        return {
            "symbol":     symbol,
            "price":      round(info.last_price, 2),
            "prev_close": round(info.previous_close, 2),
            "change_pct": round((info.last_price / info.previous_close - 1) * 100, 2),
            "volume":     info.last_volume,
            "market_cap": getattr(info, "market_cap", None),
        }
    except Exception as e:
        print(f"  ⚠  Could not fetch quote for {symbol}: {e}")
        return {}


def fetch_batch_quotes(symbols: list[str]) -> list[dict]:
    """Fetch realtime quotes for multiple symbols."""
    quotes = []
    for sym in symbols:
        q = fetch_realtime_quote(sym)
        if q:
            quotes.append(q)
    return quotes


def fetch_intraday(symbol: str, days_back: int = 5, interval: str = "5m") -> pd.DataFrame:
    """
    Fetch recent intraday data (max 60 days back for 1m–1h intervals).
    Useful for VWAP and intraday strategies.
    """
    end = datetime.now()
    start = end - timedelta(days=days_back)
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start.strftime("%Y-%m-%d"),
                        end=end.strftime("%Y-%m-%d"),
                        interval=interval)

    drop_cols = [c for c in ("Dividends", "Stock Splits", "Capital Gains") if c in df.columns]
    df.drop(columns=drop_cols, inplace=True)
    return df


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching AAPL daily data (3 months)...")
    df = fetch_ohlcv("AAPL", period="3mo")
    print(df.tail())
    print(f"\nRows: {len(df)}")

    print("\nRealtime quote:")
    print(fetch_realtime_quote("AAPL"))
