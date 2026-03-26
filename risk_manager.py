# risk_manager.py — position sizing, stop losses, and daily loss limits

import config


def calculate_position_size(account_size: float, risk_pct: float,
                            entry_price: float, stop_loss: float) -> int:
    """
    Calculate how many shares to buy, risking at most `risk_pct` of account.

    Formula:  shares = (account × risk%) / (entry − stop)

    Returns:
        Number of shares (integer, rounded down)
    """
    risk_per_share = abs(entry_price - stop_loss)

    if risk_per_share <= 0:
        return 0

    dollar_risk = account_size * risk_pct
    shares = int(dollar_risk / risk_per_share)

    # Safety cap: never spend more than 20% of account on one position
    max_cost = account_size * 0.20
    max_shares_by_cost = int(max_cost / entry_price) if entry_price > 0 else 0

    return min(shares, max_shares_by_cost)


def calculate_stop_loss(entry: float, atr: float,
                        multiplier: float = None) -> float:
    """ATR-based stop loss: entry − (ATR × multiplier)."""
    if multiplier is None:
        multiplier = config.STOP_LOSS_ATR_MULT
    return round(entry - atr * multiplier, 2)


def calculate_take_profit(entry: float, atr: float,
                          multiplier: float = None) -> float:
    """ATR-based take profit: entry + (ATR × multiplier)."""
    if multiplier is None:
        multiplier = config.TAKE_PROFIT_ATR_MULT
    return round(entry + atr * multiplier, 2)


def risk_reward_ratio(entry: float, stop: float, target: float) -> float:
    """Calculate the risk:reward ratio.  Want ≥ 2.0."""
    risk   = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return 0.0
    return round(reward / risk, 2)


def check_daily_loss_limit(pnl_today: float, account_size: float = None,
                           max_pct: float = None) -> bool:
    """
    Check if daily loss exceeds the limit.

    Returns:
        True if trading should HALT (loss exceeded)
    """
    if account_size is None:
        account_size = config.ACCOUNT_SIZE
    if max_pct is None:
        max_pct = config.MAX_DAILY_LOSS_PCT

    max_loss = account_size * max_pct
    return pnl_today <= -max_loss


def check_max_open_trades(current_open: int, max_allowed: int = None) -> bool:
    """
    Check if we can open another trade.

    Returns:
        True if we CAN open another trade
    """
    if max_allowed is None:
        max_allowed = config.MAX_OPEN_TRADES
    return current_open < max_allowed


def can_trade(account_balance: float, pnl_today: float,
              open_positions: int) -> dict:
    """
    Master risk gate — checks all conditions before allowing a trade.

    Returns:
        dict with 'allowed' (bool) and 'reason' (str)
    """
    # Check daily loss limit
    if check_daily_loss_limit(pnl_today, account_balance):
        return {
            "allowed": False,
            "reason": f"Daily loss limit hit (P&L: ${pnl_today:,.2f})"
        }

    # Check open trades limit
    if not check_max_open_trades(open_positions):
        return {
            "allowed": False,
            "reason": f"Max open trades reached ({open_positions}/{config.MAX_OPEN_TRADES})"
        }

    # Check minimum account balance (don't trade below 50% of starting)
    if account_balance < config.ACCOUNT_SIZE * 0.5:
        return {
            "allowed": False,
            "reason": f"Account below 50% of starting (${account_balance:,.2f})"
        }

    return {"allowed": True, "reason": "All risk checks passed"}


def validate_trade(entry: float, stop: float, target: float,
                   account_size: float = None) -> dict:
    """
    Validate a specific trade setup before execution.

    Returns:
        dict with 'valid', 'shares', 'risk_amount', 'rr_ratio', 'reason'
    """
    if account_size is None:
        account_size = config.ACCOUNT_SIZE

    rr = risk_reward_ratio(entry, stop, target)
    shares = calculate_position_size(account_size, config.MAX_RISK_PER_TRADE,
                                     entry, stop)
    risk_amount = shares * abs(entry - stop)

    result = {
        "valid":       True,
        "shares":      shares,
        "risk_amount": round(risk_amount, 2),
        "rr_ratio":    rr,
        "cost":        round(shares * entry, 2),
        "reason":      "Trade validated",
    }

    if shares == 0:
        result["valid"] = False
        result["reason"] = "Position size = 0 (stop too close or account too small)"

    if rr < 1.5:
        result["valid"] = False
        result["reason"] = f"Risk:Reward too low ({rr}:1, need ≥ 1.5:1)"

    if risk_amount > account_size * config.MAX_RISK_PER_TRADE:
        result["valid"] = False
        result["reason"] = f"Risk ${risk_amount:.2f} exceeds max ${account_size * config.MAX_RISK_PER_TRADE:.2f}"

    return result


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Risk Manager Tests")
    print("=" * 50)

    entry = 150.00
    atr   = 3.50
    stop  = calculate_stop_loss(entry, atr)
    target = calculate_take_profit(entry, atr)
    shares = calculate_position_size(100_000, 0.02, entry, stop)

    print(f"Entry:  ${entry}")
    print(f"Stop:   ${stop}  (ATR×{config.STOP_LOSS_ATR_MULT})")
    print(f"Target: ${target}  (ATR×{config.TAKE_PROFIT_ATR_MULT})")
    print(f"Shares: {shares}")
    print(f"R:R:    {risk_reward_ratio(entry, stop, target)}:1")
    print(f"Risk $: ${shares * abs(entry - stop):,.2f}")

    print(f"\nCan trade? {can_trade(100_000, -500, 1)}")
    print(f"Can trade? {can_trade(100_000, -3500, 3)}")

    print(f"\nValidate: {validate_trade(entry, stop, target)}")
