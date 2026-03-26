# strategy.py — signal scoring engine

import pandas as pd
from dataclasses import dataclass
from enum import Enum
from indicators import add_all_indicators
import config


class SignalType(Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    symbol:      str
    signal_type: SignalType
    score:       int          # 0–100
    price:       float
    stop_loss:   float
    take_profit: float
    reasons:     list[str]    # human-readable reasons


def score_trend(df: pd.DataFrame) -> tuple[int, list[str]]:
    """
    Trend alignment score (0–25).
    Checks EMA stack order and price relative to key EMAs.
    """
    latest = df.iloc[-1]
    score = 0
    reasons = []

    # EMA stack: 9 > 21 > 50 (bullish alignment)
    try:
        if latest["EMA_9"] > latest["EMA_21"] > latest["EMA_50"]:
            score += 12
            reasons.append("EMA stack bullish (9>21>50)")
        elif latest["EMA_9"] < latest["EMA_21"] < latest["EMA_50"]:
            score -= 5
            reasons.append("EMA stack bearish")
    except KeyError:
        pass

    # Price above 50 EMA
    if latest["Close"] > latest.get("EMA_50", 0):
        score += 5
        reasons.append("Price above EMA 50")

    # Price above 200 EMA (long-term uptrend)
    if latest["Close"] > latest.get("EMA_200", 0):
        score += 5
        reasons.append("Price above EMA 200")

    # ADX > 25 = strong trend
    adx = latest.get("ADX", 0)
    if pd.notna(adx) and adx > 25:
        score += 3
        reasons.append(f"Strong trend (ADX={adx:.0f})")

    return max(0, min(25, score)), reasons


def score_momentum(df: pd.DataFrame) -> tuple[int, list[str]]:
    """
    RSI momentum score (0–20).
    Sweet spot for entries: RSI 40–60 (not overbought/oversold).
    """
    latest = df.iloc[-1]
    score = 0
    reasons = []

    rsi = latest.get("RSI", 50)
    if pd.isna(rsi):
        return 0, []

    if 40 <= rsi <= 60:
        score += 15
        reasons.append(f"RSI in sweet spot ({rsi:.0f})")
    elif 30 <= rsi < 40:
        score += 12
        reasons.append(f"RSI near oversold — potential bounce ({rsi:.0f})")
    elif 60 < rsi <= 70:
        score += 8
        reasons.append(f"RSI elevated but not extreme ({rsi:.0f})")
    elif rsi > 70:
        score += 2
        reasons.append(f"RSI overbought — caution ({rsi:.0f})")
    elif rsi < 30:
        score += 5
        reasons.append(f"RSI deeply oversold ({rsi:.0f})")

    # Stochastic confirmation
    stoch_k = latest.get("Stoch_K", 50)
    if pd.notna(stoch_k) and 20 < stoch_k < 80:
        score += 5
        reasons.append(f"Stochastic confirms ({stoch_k:.0f})")

    return max(0, min(20, score)), reasons


def score_macd(df: pd.DataFrame) -> tuple[int, list[str]]:
    """
    MACD momentum score (0–20).
    Looks for positive histogram and bullish crossover.
    """
    score = 0
    reasons = []

    if len(df) < 2:
        return 0, []

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    hist      = latest.get("MACD_Hist", 0)
    prev_hist = prev.get("MACD_Hist", 0)

    if pd.isna(hist) or pd.isna(prev_hist):
        return 0, []

    # Histogram positive
    if hist > 0:
        score += 8
        reasons.append("MACD histogram positive")

    # Histogram growing (increasing momentum)
    if hist > prev_hist:
        score += 7
        reasons.append("MACD momentum increasing")

    # Bullish crossover (MACD crossed above signal)
    macd_line = latest.get("MACD", 0)
    signal    = latest.get("MACD_Signal", 0)
    prev_macd = prev.get("MACD", 0)
    prev_sig  = prev.get("MACD_Signal", 0)

    if (pd.notna(macd_line) and pd.notna(signal) and
        pd.notna(prev_macd) and pd.notna(prev_sig)):
        if prev_macd <= prev_sig and macd_line > signal:
            score += 5
            reasons.append("MACD bullish crossover!")

    return max(0, min(20, score)), reasons


def score_volume(df: pd.DataFrame) -> tuple[int, list[str]]:
    """
    Volume confirmation score (0–15).
    Above-average volume on up days validates moves.
    """
    latest = df.iloc[-1]
    score = 0
    reasons = []

    vol     = latest.get("Volume", 0)
    vol_avg = latest.get("Vol_SMA_20", 0)
    obv     = latest.get("OBV", 0)

    if pd.isna(vol) or pd.isna(vol_avg) or vol_avg == 0:
        return 0, []

    vol_ratio = vol / vol_avg

    if vol_ratio > 1.5:
        score += 10
        reasons.append(f"Volume surge ({vol_ratio:.1f}x avg)")
    elif vol_ratio > 1.0:
        score += 7
        reasons.append(f"Above-average volume ({vol_ratio:.1f}x)")
    elif vol_ratio > 0.7:
        score += 3
        reasons.append("Moderate volume")

    # OBV trending up (last 5 days)
    if len(df) >= 5:
        obv_recent = df["OBV"].iloc[-5:]
        if obv_recent.iloc[-1] > obv_recent.iloc[0]:
            score += 5
            reasons.append("OBV trending up (accumulation)")

    return max(0, min(15, score)), reasons


def score_bollinger(df: pd.DataFrame) -> tuple[int, list[str]]:
    """
    Bollinger Band position score (0–10).
    Near lower band = potential buy, near upper = caution.
    """
    latest = df.iloc[-1]
    score = 0
    reasons = []

    bb_pct = latest.get("BB_Pct", 0.5)
    if pd.isna(bb_pct):
        return 0, []

    if bb_pct < 0.2:
        score += 8
        reasons.append(f"Price near lower BB (%%B={bb_pct:.2f}) — potential bounce")
    elif bb_pct < 0.4:
        score += 6
        reasons.append(f"Price in lower BB zone (%%B={bb_pct:.2f})")
    elif 0.4 <= bb_pct <= 0.6:
        score += 4
        reasons.append(f"Price at BB midpoint (%%B={bb_pct:.2f})")
    elif bb_pct > 0.8:
        score += 1
        reasons.append(f"Price near upper BB — caution (%%B={bb_pct:.2f})")

    return max(0, min(10, score)), reasons


def score_vwap(df: pd.DataFrame) -> tuple[int, list[str]]:
    """
    VWAP position score (0–10).
    Price above VWAP = bullish institutional bias.
    """
    latest = df.iloc[-1]
    score = 0
    reasons = []

    vwap  = latest.get("VWAP", 0)
    price = latest["Close"]

    if pd.isna(vwap) or vwap == 0:
        return 0, []

    if price > vwap * 1.01:
        score += 8
        reasons.append("Price above VWAP (bullish)")
    elif price > vwap:
        score += 5
        reasons.append("Price at VWAP")
    else:
        score += 2
        reasons.append("Price below VWAP")

    return max(0, min(10, score)), reasons


def score_stock(df: pd.DataFrame) -> tuple[int, list[str]]:
    """
    Compute composite score (0–100) from all sub-scores.
    Returns (total_score, list_of_reasons).
    """
    if len(df) < 50:
        return 0, ["Insufficient data (need 50+ bars)"]

    total = 0
    all_reasons = []

    for scorer in [score_trend, score_momentum, score_macd,
                   score_volume, score_bollinger, score_vwap]:
        pts, reasons = scorer(df)
        total += pts
        all_reasons.extend(reasons)

    return total, all_reasons


def generate_signal(symbol: str, df: pd.DataFrame,
                    min_score: int = None) -> Signal:
    """
    Generate a BUY / SELL / HOLD signal for a symbol.

    Args:
        symbol:    Ticker
        df:        Raw OHLCV DataFrame (indicators will be added)
        min_score: Minimum score to trigger BUY (default from config)

    Returns:
        Signal object with type, score, prices, and reasons
    """
    if min_score is None:
        min_score = config.MIN_STOCK_SCORE

    # Add all indicators
    enriched = add_all_indicators(df)

    # Score
    score, reasons = score_stock(enriched)

    latest = enriched.iloc[-1]
    price  = latest["Close"]
    atr    = latest.get("ATR", price * 0.02)  # fallback: 2% of price

    if pd.isna(atr) or atr == 0:
        atr = price * 0.02

    stop_loss   = round(price - config.STOP_LOSS_ATR_MULT * atr, 2)
    take_profit = round(price + config.TAKE_PROFIT_ATR_MULT * atr, 2)

    # Determine signal type
    if score >= min_score:
        sig_type = SignalType.BUY
    elif score < 30:
        sig_type = SignalType.SELL
    else:
        sig_type = SignalType.HOLD

    return Signal(
        symbol=symbol,
        signal_type=sig_type,
        score=score,
        price=round(price, 2),
        stop_loss=stop_loss,
        take_profit=take_profit,
        reasons=reasons,
    )


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from data_fetcher import fetch_ohlcv

    for sym in ["AAPL", "MSFT", "NVDA", "TSLA"]:
        df = fetch_ohlcv(sym, period="6mo")
        if df.empty:
            continue
        sig = generate_signal(sym, df)
        print(f"\n{'='*50}")
        print(f"  {sig.symbol}  →  {sig.signal_type.value}  (Score: {sig.score}/100)")
        print(f"  Price: ${sig.price}  |  Stop: ${sig.stop_loss}  |  Target: ${sig.take_profit}")
        for r in sig.reasons:
            print(f"    • {r}")
