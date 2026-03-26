# backtester.py — historical strategy tester

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from data_fetcher import fetch_ohlcv
from indicators import add_all_indicators
from strategy import score_stock
import config


@dataclass
class Trade:
    symbol:       str
    entry_date:   str
    entry_price:  float
    stop_loss:    float
    take_profit:  float
    shares:       int
    exit_date:    str = ""
    exit_price:   float = 0.0
    pnl:          float = 0.0
    pnl_pct:      float = 0.0
    exit_reason:  str = ""


@dataclass
class BacktestResult:
    symbol:         str
    start_date:     str
    end_date:       str
    total_trades:   int = 0
    wins:           int = 0
    losses:         int = 0
    win_rate:       float = 0.0
    total_pnl:      float = 0.0
    avg_pnl:        float = 0.0
    max_drawdown:   float = 0.0
    sharpe_ratio:   float = 0.0
    profit_factor:  float = 0.0
    avg_hold_days:  float = 0.0
    trades:         list = field(default_factory=list)


def backtest(symbol: str, start_date: str = "2024-01-01",
             end_date: str = "2025-01-01",
             initial_capital: float = None,
             verbose: bool = True) -> BacktestResult:
    """
    Backtest the strategy on historical data for a single symbol.

    Args:
        symbol:          Ticker
        start_date:      YYYY-MM-DD
        end_date:        YYYY-MM-DD
        initial_capital: Starting cash (default from config)
        verbose:         Print progress

    Returns:
        BacktestResult with all metrics and trade log
    """
    if initial_capital is None:
        initial_capital = config.ACCOUNT_SIZE

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Backtesting {symbol}  |  {start_date} → {end_date}")
        print(f"  Capital: ${initial_capital:,.0f}  |  Risk/trade: {config.MAX_RISK_PER_TRADE*100:.0f}%")
        print(f"{'='*60}")

    # Fetch data with extra lookback for indicator warmup
    df = fetch_ohlcv(symbol, period="max")
    if df.empty:
        print(f"  ⚠  No data for {symbol}")
        return BacktestResult(symbol=symbol, start_date=start_date,
                              end_date=end_date)

    # Filter to date range (keep extra for indicator warmup)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)  # strip timezone for clean comparison
    warmup_start = pd.to_datetime(start_date) - pd.Timedelta(days=250)
    mask = (df.index >= warmup_start) & (df.index <= pd.to_datetime(end_date))
    df = df[mask]

    if len(df) < 100:
        print(f"  ⚠  Insufficient data ({len(df)} bars)")
        return BacktestResult(symbol=symbol, start_date=start_date,
                              end_date=end_date)

    # Add indicators
    df = add_all_indicators(df)

    # Trim to actual test period (after warmup)
    test_mask = df.index >= pd.to_datetime(start_date)
    test_start_idx = df.index.get_loc(df.index[test_mask][0])

    # Simulation state
    cash = initial_capital
    trades = []
    open_trade = None
    equity_curve = []

    for i in range(test_start_idx, len(df)):
        row = df.iloc[i]
        date = df.index[i].strftime("%Y-%m-%d")
        price = row["Close"]
        atr = row.get("ATR", price * 0.02)
        if pd.isna(atr) or atr == 0:
            atr = price * 0.02

        # ── Check exits first ──
        if open_trade is not None:
            # Stop loss hit
            if row["Low"] <= open_trade.stop_loss:
                open_trade.exit_date = date
                open_trade.exit_price = open_trade.stop_loss
                open_trade.pnl = (open_trade.exit_price - open_trade.entry_price) * open_trade.shares
                open_trade.pnl_pct = (open_trade.exit_price / open_trade.entry_price - 1) * 100
                open_trade.exit_reason = "Stop Loss"
                cash += open_trade.shares * open_trade.exit_price
                trades.append(open_trade)
                open_trade = None

            # Take profit hit
            elif row["High"] >= open_trade.take_profit:
                open_trade.exit_date = date
                open_trade.exit_price = open_trade.take_profit
                open_trade.pnl = (open_trade.exit_price - open_trade.entry_price) * open_trade.shares
                open_trade.pnl_pct = (open_trade.exit_price / open_trade.entry_price - 1) * 100
                open_trade.exit_reason = "Take Profit"
                cash += open_trade.shares * open_trade.exit_price
                trades.append(open_trade)
                open_trade = None

        # ── Check entries ──
        if open_trade is None and i >= test_start_idx + 1:
            # Use lookback window for scoring
            lookback = df.iloc[max(0, i-100):i+1]
            if len(lookback) >= 50:
                score, _ = score_stock(lookback)

                if score >= config.MIN_STOCK_SCORE:
                    stop_loss = round(price - config.STOP_LOSS_ATR_MULT * atr, 2)
                    take_profit = round(price + config.TAKE_PROFIT_ATR_MULT * atr, 2)

                    risk_per_share = price - stop_loss
                    if risk_per_share > 0:
                        dollar_risk = cash * config.MAX_RISK_PER_TRADE
                        shares = int(dollar_risk / risk_per_share)
                        shares = min(shares, int(cash * 0.20 / price))

                        if shares > 0:
                            cost = shares * price
                            cash -= cost
                            open_trade = Trade(
                                symbol=symbol,
                                entry_date=date,
                                entry_price=price,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                shares=shares,
                            )

        # Track equity
        position_value = 0
        if open_trade:
            position_value = open_trade.shares * price
        equity_curve.append(cash + position_value)

    # Close any remaining position at last price
    if open_trade is not None:
        last_price = df.iloc[-1]["Close"]
        open_trade.exit_date = df.index[-1].strftime("%Y-%m-%d")
        open_trade.exit_price = last_price
        open_trade.pnl = (last_price - open_trade.entry_price) * open_trade.shares
        open_trade.pnl_pct = (last_price / open_trade.entry_price - 1) * 100
        open_trade.exit_reason = "End of Period"
        trades.append(open_trade)

    # ── Compute metrics ──
    result = BacktestResult(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        trades=trades,
    )

    if trades:
        result.total_trades = len(trades)
        result.wins = sum(1 for t in trades if t.pnl > 0)
        result.losses = sum(1 for t in trades if t.pnl <= 0)
        result.win_rate = result.wins / result.total_trades * 100
        result.total_pnl = sum(t.pnl for t in trades)
        result.avg_pnl = result.total_pnl / result.total_trades

        # Profit factor
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss   = abs(sum(t.pnl for t in trades if t.pnl <= 0))
        result.profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Max drawdown
        if equity_curve:
            equity = pd.Series(equity_curve)
            peak = equity.expanding().max()
            drawdown = (equity - peak) / peak
            result.max_drawdown = abs(drawdown.min()) * 100

        # Sharpe ratio (annualized, daily returns)
        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            if returns.std() > 0:
                result.sharpe_ratio = round(
                    (returns.mean() / returns.std()) * np.sqrt(252), 2
                )

        # Average holding period
        hold_days = []
        for t in trades:
            if t.entry_date and t.exit_date:
                d = (pd.to_datetime(t.exit_date) - pd.to_datetime(t.entry_date)).days
                hold_days.append(d)
        result.avg_hold_days = np.mean(hold_days) if hold_days else 0

    return result


def print_report(result: BacktestResult):
    """Print a formatted backtest report."""
    print(f"\n{'='*60}")
    print(f"  BACKTEST REPORT: {result.symbol}")
    print(f"  Period: {result.start_date} → {result.end_date}")
    print(f"{'='*60}")
    print(f"  Total Trades:    {result.total_trades}")
    print(f"  Wins / Losses:   {result.wins} / {result.losses}")
    print(f"  Win Rate:        {result.win_rate:.1f}%")
    print(f"  Total P&L:       ${result.total_pnl:,.2f}")
    print(f"  Avg P&L/Trade:   ${result.avg_pnl:,.2f}")
    print(f"  Profit Factor:   {result.profit_factor:.2f}")
    print(f"  Sharpe Ratio:    {result.sharpe_ratio:.2f}")
    print(f"  Max Drawdown:    {result.max_drawdown:.1f}%")
    print(f"  Avg Hold Days:   {result.avg_hold_days:.1f}")
    print(f"{'='*60}")

    if result.trades:
        print(f"\n  {'Date':<12} {'Entry':>8} {'Exit':>8} {'P&L':>10} {'Reason':<12}")
        print(f"  {'-'*52}")
        for t in result.trades:
            emoji = "✅" if t.pnl > 0 else "❌"
            print(f"  {t.entry_date:<12} ${t.entry_price:>7.2f} "
                  f"${t.exit_price:>7.2f} {emoji}${t.pnl:>+9.2f} {t.exit_reason}")


def backtest_portfolio(symbols: list[str], start_date: str = "2024-01-01",
                       end_date: str = "2025-01-01") -> list[BacktestResult]:
    """Backtest multiple symbols and return aggregated results."""
    results = []
    for sym in symbols:
        r = backtest(sym, start_date, end_date, verbose=False)
        results.append(r)

    # Summary
    total_pnl = sum(r.total_pnl for r in results)
    total_trades = sum(r.total_trades for r in results)
    total_wins = sum(r.wins for r in results)

    print(f"\n{'='*60}")
    print(f"  PORTFOLIO BACKTEST SUMMARY")
    print(f"  {len(symbols)} stocks  |  {start_date} → {end_date}")
    print(f"{'='*60}")
    print(f"  Total P&L:     ${total_pnl:,.2f}")
    print(f"  Total Trades:  {total_trades}")
    print(f"  Overall Win%:  {total_wins/total_trades*100:.1f}%" if total_trades > 0 else "  No trades")
    print(f"{'='*60}")

    for r in sorted(results, key=lambda x: x.total_pnl, reverse=True):
        emoji = "📈" if r.total_pnl > 0 else "📉"
        print(f"  {emoji} {r.symbol:<6} {r.total_trades:>3} trades  "
              f"Win: {r.win_rate:>5.1f}%  P&L: ${r.total_pnl:>+10,.2f}")

    return results


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Single stock backtest
    result = backtest("AAPL", "2024-01-01", "2025-01-01")
    print_report(result)

    # Portfolio backtest
    print("\n\n")
    backtest_portfolio(["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"],
                       "2024-01-01", "2025-01-01")
