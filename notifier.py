# notifier.py — Telegram alerts for trade signals and daily summaries

import requests
import config
from datetime import datetime


def send_telegram(message: str) -> bool:
    """
    Send a message via Telegram Bot API.
    Returns True on success.
    """
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("  ⚠  Telegram not configured — skipping notification")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    config.TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            print(f"  ⚠  Telegram error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ⚠  Telegram send failed: {e}")
        return False


def notify_trade(signal) -> bool:
    """
    Send a formatted trade alert.

    Args:
        signal: Signal object from strategy.py
    """
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⏸️"}
    e = emoji.get(signal.signal_type.value, "❓")

    msg = (
        f"{e} <b>{signal.signal_type.value} Signal — {signal.symbol}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Score: <b>{signal.score}/100</b>\n"
        f"💰 Price: <b>${signal.price:,.2f}</b>\n"
        f"🛑 Stop:  ${signal.stop_loss:,.2f}\n"
        f"🎯 Target: ${signal.take_profit:,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Reasons:</b>\n"
    )
    for r in signal.reasons[:8]:  # cap at 8 reasons
        msg += f"  • {r}\n"

    msg += f"\n⏰ {datetime.now().strftime('%H:%M:%S  %b %d')}"
    return send_telegram(msg)


def notify_order_placed(symbol: str, qty: int, side: str,
                        entry: float, stop: float, target: float) -> bool:
    """Send alert when an order is actually placed."""
    emoji = "🟢" if side == "buy" else "🔴"
    msg = (
        f"{emoji} <b>ORDER PLACED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 {symbol} — {side.upper()} {qty} shares\n"
        f"💰 Entry: ${entry:,.2f}\n"
        f"🛑 Stop:  ${stop:,.2f}\n"
        f"🎯 Target: ${target:,.2f}\n"
        f"💵 Cost: ${qty * entry:,.2f}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    return send_telegram(msg)


def notify_position_closed(symbol: str, pnl: float, pnl_pct: float) -> bool:
    """Send alert when a position is closed."""
    emoji = "✅" if pnl >= 0 else "❌"
    msg = (
        f"{emoji} <b>POSITION CLOSED — {symbol}</b>\n"
        f"P&L: <b>${pnl:,.2f} ({pnl_pct:+.1f}%)</b>\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    return send_telegram(msg)


def notify_daily_summary(trades: list, total_pnl: float,
                         account_value: float, win_count: int,
                         loss_count: int) -> bool:
    """End-of-day recap."""
    emoji = "📈" if total_pnl >= 0 else "📉"
    total_trades = win_count + loss_count
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    msg = (
        f"{emoji} <b>Daily Summary</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Day P&L: <b>${total_pnl:,.2f}</b>\n"
        f"🏦 Account: <b>${account_value:,.2f}</b>\n"
        f"📊 Trades: {total_trades} (W: {win_count} | L: {loss_count})\n"
        f"🎯 Win Rate: {win_rate:.0f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if trades:
        msg += "<b>Trades:</b>\n"
        for t in trades[:10]:
            e = "✅" if t.get("pnl", 0) >= 0 else "❌"
            msg += f"  {e} {t['symbol']}: ${t.get('pnl', 0):,.2f}\n"

    msg += f"\n📅 {datetime.now().strftime('%b %d, %Y')}"
    return send_telegram(msg)


def notify_error(error: str) -> bool:
    """Alert on bot errors."""
    msg = (
        f"🚨 <b>BOT ERROR</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{error}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    return send_telegram(msg)


def notify_bot_started() -> bool:
    """Startup notification."""
    msg = (
        f"🤖 <b>Trading Bot Started</b>\n"
        f"Mode: {'PAPER' if config.PAPER_MODE else '⚠️ LIVE'}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S  %b %d, %Y')}"
    )
    return send_telegram(msg)


def notify_bot_stopped(reason: str = "Manual shutdown") -> bool:
    """Shutdown notification."""
    msg = (
        f"🛑 <b>Trading Bot Stopped</b>\n"
        f"Reason: {reason}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    return send_telegram(msg)


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Sending test message to Telegram...")
    ok = send_telegram("🧪 <b>Test message</b>\nAI Trading Bot is connected!")
    print(f"Sent: {ok}")
