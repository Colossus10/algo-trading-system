# bot.py — main trading bot orchestrator

import time
import logging
import schedule
from datetime import datetime

import config
from broker import AlpacaBroker
from scanner import get_top_picks, get_watchlist
from strategy import generate_signal, SignalType
from risk_manager import can_trade, validate_trade
from data_fetcher import fetch_ohlcv
from notifier import (
    notify_trade, notify_order_placed, notify_position_closed,
    notify_daily_summary, notify_error, notify_bot_started,
    notify_bot_stopped, send_telegram,
)


# ── Logging setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("TradingBot")


class TradingBot:
    """
    Daily trading bot.

    Workflow:
      1. Pre-market scan → pick top stocks
      2. For each: generate signal → check risk → place bracket order
      3. Monitor positions throughout the day
      4. End of day: close all, send summary
    """

    def __init__(self):
        log.info("Initialising Trading Bot...")
        self.broker = AlpacaBroker()
        self.daily_trades = []

    # ── Core logic ───────────────────────────────────────────────────────

    def scan_and_trade(self):
        """Main trading cycle: scan → score → risk-check → trade."""
        log.info("=" * 50)
        log.info("Starting scan & trade cycle")

        # 1. Get account state
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        log.info(f"Account: ${account['equity']:,.2f}  |  "
                 f"P&L today: ${account['pnl_today']:,.2f}  |  "
                 f"Open: {len(positions)}")

        # 2. Risk gate
        risk_check = can_trade(
            account_balance=account["equity"],
            pnl_today=account["pnl_today"],
            open_positions=len(positions),
        )
        if not risk_check["allowed"]:
            log.warning(f"Risk gate blocked: {risk_check['reason']}")
            send_telegram(f"⚠️ Trading halted: {risk_check['reason']}")
            return

        # 3. Scan top picks
        log.info("Scanning watchlist...")
        picks = get_top_picks(
            n=config.MAX_OPEN_TRADES - len(positions),
            tickers=get_watchlist(),
            verbose=False,
        )

        if not picks:
            log.info("No stocks scored above threshold — standing by")
            return

        log.info(f"Found {len(picks)} candidates above score {config.MIN_STOCK_SCORE}")

        # 4. Trade each pick
        for pick in picks:
            symbol = pick["symbol"]

            # Skip if already holding
            if any(p["symbol"] == symbol for p in positions):
                log.info(f"  Skipping {symbol} — already in position")
                continue

            # Re-check risk gate (may have placed orders since)
            positions = self.broker.get_positions()
            risk_check = can_trade(
                account_balance=account["equity"],
                pnl_today=account["pnl_today"],
                open_positions=len(positions),
            )
            if not risk_check["allowed"]:
                log.warning(f"Risk gate blocked: {risk_check['reason']}")
                break

            # Validate the specific trade
            validation = validate_trade(
                entry=pick["price"],
                stop=pick["stop_loss"],
                target=pick["take_profit"],
                account_size=account["equity"],
            )

            if not validation["valid"]:
                log.info(f"  Skipping {symbol}: {validation['reason']}")
                continue

            # Place the order
            log.info(f"  🟢 Placing order: {symbol}  "
                     f"{validation['shares']} shares @ ${pick['price']:.2f}  "
                     f"Stop: ${pick['stop_loss']:.2f}  "
                     f"Target: ${pick['take_profit']:.2f}")

            if config.PAPER_MODE:
                order = self.broker.place_order(
                    symbol=symbol,
                    qty=validation["shares"],
                    side="buy",
                    stop_loss=pick["stop_loss"],
                    take_profit=pick["take_profit"],
                )

                if "error" not in order:
                    log.info(f"  ✓  Order placed: {order.get('id', 'N/A')}")
                    notify_order_placed(
                        symbol, validation["shares"], "buy",
                        pick["price"], pick["stop_loss"], pick["take_profit"],
                    )
                    self.daily_trades.append({
                        "symbol": symbol,
                        "side":   "buy",
                        "shares": validation["shares"],
                        "price":  pick["price"],
                    })
                else:
                    log.error(f"  ✗  Order failed: {order['error']}")
                    notify_error(f"Order failed for {symbol}: {order['error']}")
            else:
                log.warning(f"  LIVE MODE — order for {symbol} skipped (safety)")

    def check_positions(self):
        """Monitor open positions and log status."""
        positions = self.broker.get_positions()
        if not positions:
            return

        log.info(f"Open positions ({len(positions)}):")
        for p in positions:
            emoji = "📈" if p["pnl"] >= 0 else "📉"
            log.info(f"  {emoji} {p['symbol']}: {p['qty']} shares  "
                     f"Entry: ${p['entry_price']:.2f}  "
                     f"Now: ${p['current_price']:.2f}  "
                     f"P&L: ${p['pnl']:.2f} ({p['pnl_pct']:+.1f}%)")

    def end_of_day(self):
        """Close all positions and send daily summary."""
        log.info("End of day — closing all positions")

        positions = self.broker.get_positions()
        for p in positions:
            self.broker.close_position(p["symbol"])
            notify_position_closed(p["symbol"], p["pnl"], p["pnl_pct"])
            self.daily_trades.append({
                "symbol": p["symbol"],
                "pnl":    p["pnl"],
            })

        # Daily summary
        account = self.broker.get_account()
        total_pnl = account["pnl_today"]
        wins  = sum(1 for t in self.daily_trades if t.get("pnl", 0) > 0)
        losses = sum(1 for t in self.daily_trades if t.get("pnl", 0) <= 0)

        notify_daily_summary(
            trades=self.daily_trades,
            total_pnl=total_pnl,
            account_value=account["equity"],
            win_count=wins,
            loss_count=losses,
        )

        log.info(f"Day P&L: ${total_pnl:,.2f}  |  "
                 f"Account: ${account['equity']:,.2f}")

        # Reset for next day
        self.daily_trades = []

    # ── Run modes ────────────────────────────────────────────────────────

    def run_once(self):
        """
        Run a single scan-and-trade cycle.
        Great for testing without the scheduler.
        """
        log.info("Running single cycle...")
        self.scan_and_trade()
        self.check_positions()
        log.info("Single cycle complete.")

    def run(self):
        """
        Run the bot on a daily schedule.
        Ctrl+C to stop gracefully.
        """
        log.info("=" * 60)
        log.info("  AI TRADING BOT")
        log.info(f"  Mode: {'PAPER' if config.PAPER_MODE else '⚠️  LIVE'}")
        log.info(f"  Schedule: {config.MARKET_OPEN_TIME} – {config.MARKET_CLOSE_TIME}")
        log.info("=" * 60)

        notify_bot_started()

        # Schedule tasks
        schedule.every().day.at(config.MARKET_OPEN_TIME).do(self.scan_and_trade)
        schedule.every(30).minutes.do(self.check_positions)
        schedule.every().day.at(config.MARKET_CLOSE_TIME).do(self.end_of_day)

        try:
            # Check if market is open right now
            if self.broker.is_market_open():
                log.info("Market is currently open — running immediate scan")
                self.scan_and_trade()

            while True:
                schedule.run_pending()
                time.sleep(30)

        except KeyboardInterrupt:
            log.info("\nShutdown requested...")
            notify_bot_stopped("Manual shutdown (Ctrl+C)")
        except Exception as e:
            log.error(f"Fatal error: {e}")
            notify_error(f"Fatal: {e}")
            notify_bot_stopped(f"Error: {e}")
        finally:
            log.info("Bot stopped.")


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    bot = TradingBot()

    if "--once" in sys.argv:
        bot.run_once()
    else:
        bot.run()
