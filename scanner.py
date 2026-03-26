# scanner.py — stock screener / watchlist scanner

import pandas as pd
import yfinance as yf
from data_fetcher import fetch_ohlcv, fetch_realtime_quote
from strategy import generate_signal, SignalType
import config


# ── Watchlists ───────────────────────────────────────────────────────────────

# Top US large-cap tickers for scanning (curated subset of S&P 500)
SP500_TOP = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B",
    "UNH", "LLY", "JPM", "V", "XOM", "AVGO", "JNJ", "MA", "PG", "HD",
    "COST", "MRK", "ABBV", "CVX", "NFLX", "CRM", "AMD", "KO", "PEP",
    "TMO", "BAC", "ADBE", "WMT", "ACN", "MCD", "CSCO", "LIN", "ABT",
    "ORCL", "DHR", "TXN", "QCOM", "INTC", "CMCSA", "DIS", "NKE", "PM",
    "RTX", "AMAT", "ISRG", "AMGN", "HON",
]

def get_watchlist(name: str = None) -> list[str]:
    """
    Get a list of tickers based on watchlist name.

    Args:
        name: 'sp500' | 'sp500_top' | 'custom'
    """
    if name is None:
        name = config.WATCHLIST

    if name == "sp500" or name == "sp500_top":
        return SP500_TOP
    elif name == "custom":
        # Add your own tickers here
        return ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL"]
    else:
        return SP500_TOP


# ── Filters ──────────────────────────────────────────────────────────────────

def passes_filters(quote: dict) -> bool:
    """Check if a stock passes the minimum price/volume/cap filters."""
    price = quote.get("price", 0)
    volume = quote.get("volume", 0)
    market_cap = quote.get("market_cap", 0)

    if price < config.MIN_PRICE:
        return False
    if volume < config.MIN_VOLUME:
        return False
    if market_cap and market_cap < config.MIN_MARKET_CAP:
        return False
    return True


# ── Scanner ──────────────────────────────────────────────────────────────────

def scan_stocks(tickers: list[str] = None,
                verbose: bool = True) -> list[dict]:
    """
    Scan a list of tickers: fetch data, compute signals, filter, and rank.

    Returns:
        Sorted list of dicts with symbol, score, signal, price, etc.
    """
    if tickers is None:
        tickers = get_watchlist()

    results = []
    total = len(tickers)

    for i, symbol in enumerate(tickers, 1):
        try:
            if verbose:
                print(f"  Scanning {symbol} ({i}/{total})...", end="\r")

            # Quick filter by quote
            quote = fetch_realtime_quote(symbol)
            if not quote or not passes_filters(quote):
                continue

            # Fetch historical data
            df = fetch_ohlcv(symbol, period="6mo")
            if df.empty or len(df) < 50:
                continue

            # Generate signal
            signal = generate_signal(symbol, df)

            results.append({
                "symbol":      symbol,
                "score":       signal.score,
                "signal":      signal.signal_type.value,
                "price":       signal.price,
                "stop_loss":   signal.stop_loss,
                "take_profit": signal.take_profit,
                "change_pct":  quote.get("change_pct", 0),
                "volume":      quote.get("volume", 0),
                "reasons":     signal.reasons,
            })

        except Exception as e:
            if verbose:
                print(f"  ⚠  {symbol}: {e}")
            continue

    # Sort by score (highest first)
    results.sort(key=lambda x: x["score"], reverse=True)

    if verbose:
        print(f"\n  Scanned {total} stocks → {len(results)} passed filters")

    return results


def get_top_picks(n: int = 5, tickers: list[str] = None,
                  verbose: bool = True) -> list[dict]:
    """
    Return the top N stocks above MIN_STOCK_SCORE.
    These are the bot's recommended trades for today.
    """
    results = scan_stocks(tickers, verbose=verbose)
    picks = [r for r in results if r["score"] >= config.MIN_STOCK_SCORE]
    return picks[:n]


def print_scan_results(results: list[dict], max_rows: int = 20):
    """Pretty-print scan results."""
    print(f"\n{'='*70}")
    print(f"  {'Symbol':<8} {'Score':>5} {'Signal':<6} {'Price':>8} "
          f"{'Stop':>8} {'Target':>8} {'Chg%':>6}")
    print(f"{'='*70}")

    for r in results[:max_rows]:
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⏸️"}.get(r["signal"], "")
        print(f"  {r['symbol']:<8} {r['score']:>5} {emoji}{r['signal']:<5} "
              f"${r['price']:>7.2f} ${r['stop_loss']:>7.2f} "
              f"${r['take_profit']:>7.2f} {r['change_pct']:>+5.1f}%")

    print(f"{'='*70}")
    above = sum(1 for r in results if r["score"] >= config.MIN_STOCK_SCORE)
    print(f"  {above} stocks scored ≥ {config.MIN_STOCK_SCORE} (tradeable)")


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Scanning custom watchlist...\n")
    results = scan_stocks(["AAPL", "MSFT", "NVDA", "TSLA", "AMZN",
                           "META", "GOOGL", "AMD", "NFLX", "CRM"])
    print_scan_results(results)

    print("\n\nTop picks:")
    picks = get_top_picks(3, ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN",
                               "META", "GOOGL", "AMD", "NFLX", "CRM"])
    for p in picks:
        print(f"  🎯 {p['symbol']} — Score {p['score']}/100 @ ${p['price']}")
        for r in p["reasons"][:3]:
            print(f"      • {r}")
