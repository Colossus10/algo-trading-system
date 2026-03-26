# indicators.py — technical analysis using the `ta` library

import pandas as pd
import ta


# ── Individual indicators ────────────────────────────────────────────────────

def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Relative Strength Index (0–100).  >70 overbought, <30 oversold."""
    return ta.momentum.RSIIndicator(close=df["Close"], window=period).rsi()


def compute_macd(df: pd.DataFrame) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    macd = ta.trend.MACD(close=df["Close"])
    return pd.DataFrame({
        "MACD":        macd.macd(),
        "MACD_Signal": macd.macd_signal(),
        "MACD_Hist":   macd.macd_diff(),
    })


def compute_ema(df: pd.DataFrame, spans: list[int] = None) -> pd.DataFrame:
    """Exponential Moving Averages for given spans."""
    if spans is None:
        spans = [9, 21, 50, 200]
    result = pd.DataFrame(index=df.index)
    for span in spans:
        result[f"EMA_{span}"] = ta.trend.EMAIndicator(close=df["Close"], window=span).ema_indicator()
    return result


def compute_sma(df: pd.DataFrame, spans: list[int] = None) -> pd.DataFrame:
    """Simple Moving Averages for given spans."""
    if spans is None:
        spans = [20, 50, 200]
    result = pd.DataFrame(index=df.index)
    for span in spans:
        result[f"SMA_{span}"] = ta.trend.SMAIndicator(close=df["Close"], window=span).sma_indicator()
    return result


def compute_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands — upper, middle, lower, and bandwidth."""
    bb = ta.volatility.BollingerBands(close=df["Close"], window=period, window_dev=std_dev)
    return pd.DataFrame({
        "BB_Upper":  bb.bollinger_hband(),
        "BB_Middle": bb.bollinger_mavg(),
        "BB_Lower":  bb.bollinger_lband(),
        "BB_Width":  bb.bollinger_wband(),
        "BB_Pct":    bb.bollinger_pband(),   # %B — where price sits in band
    })


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range — measures volatility, used for stop/target sizing."""
    return ta.volatility.AverageTrueRange(
        high=df["High"], low=df["Low"], close=df["Close"], window=period
    ).average_true_range()


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Volume Weighted Average Price.
    Works best on intraday data. For daily data this is an approximation
    using (H+L+C)/3 * Volume cumulative ratio.
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    cumulative_tp_vol = (typical_price * df["Volume"]).cumsum()
    cumulative_vol = df["Volume"].cumsum()
    return cumulative_tp_vol / cumulative_vol


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index — trend strength (>25 = strong trend)."""
    return ta.trend.ADXIndicator(
        high=df["High"], low=df["Low"], close=df["Close"], window=period
    ).adx()


def compute_stochastic(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Stochastic Oscillator — %K and %D."""
    stoch = ta.momentum.StochasticOscillator(
        high=df["High"], low=df["Low"], close=df["Close"], window=period
    )
    return pd.DataFrame({
        "Stoch_K": stoch.stoch(),
        "Stoch_D": stoch.stoch_signal(),
    })


def compute_obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume — confirms price moves with volume."""
    return ta.volume.OnBalanceVolumeIndicator(
        close=df["Close"], volume=df["Volume"]
    ).on_balance_volume()


# ── Master function — add everything at once ─────────────────────────────────

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all technical indicators to the DataFrame in-place.
    Returns the enriched DataFrame.
    """
    out = df.copy()

    # Trend
    emas = compute_ema(out)
    smas = compute_sma(out)
    for col in emas.columns:
        out[col] = emas[col]
    for col in smas.columns:
        out[col] = smas[col]

    # Momentum
    out["RSI"] = compute_rsi(out)
    macd = compute_macd(out)
    for col in macd.columns:
        out[col] = macd[col]
    stoch = compute_stochastic(out)
    for col in stoch.columns:
        out[col] = stoch[col]

    # Volatility
    bb = compute_bollinger(out)
    for col in bb.columns:
        out[col] = bb[col]
    out["ATR"] = compute_atr(out)

    # Volume
    out["VWAP"] = compute_vwap(out)
    out["OBV"]  = compute_obv(out)

    # Trend strength
    out["ADX"] = compute_adx(out)

    # Volume moving average (for volume confirmation)
    out["Vol_SMA_20"] = out["Volume"].rolling(window=20).mean()

    return out


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from data_fetcher import fetch_ohlcv

    df = fetch_ohlcv("AAPL", period="6mo")
    enriched = add_all_indicators(df)
    print(enriched.tail(3).T)  # transposed for readability
    print(f"\nColumns ({len(enriched.columns)}): {list(enriched.columns)}")
