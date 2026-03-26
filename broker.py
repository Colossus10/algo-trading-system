# broker.py — broker abstraction layer (Alpaca implementation)

from abc import ABC, abstractmethod
import alpaca_trade_api as tradeapi
import config


# ── Abstract base ────────────────────────────────────────────────────────────

class BaseBroker(ABC):
    """Interface for any broker.  Swap in Zerodha / Angel One later."""

    @abstractmethod
    def get_account(self) -> dict:
        """Return account balance, buying power, etc."""

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Return list of open positions."""

    @abstractmethod
    def place_order(self, symbol: str, qty: int, side: str,
                    stop_loss: float = None, take_profit: float = None) -> dict:
        """Place a market/bracket order."""

    @abstractmethod
    def close_position(self, symbol: str) -> dict:
        """Close a specific position."""

    @abstractmethod
    def close_all_positions(self) -> list[dict]:
        """Close all open positions."""

    @abstractmethod
    def get_order_history(self, limit: int = 20) -> list[dict]:
        """Return recent orders."""


# ── Alpaca implementation ────────────────────────────────────────────────────

class AlpacaBroker(BaseBroker):
    """Paper / live trading via Alpaca Markets (US stocks)."""

    def __init__(self):
        self.api = tradeapi.REST(
            key_id=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY,
            base_url=config.ALPACA_BASE_URL,
            api_version="v2",
        )
        self._validate_connection()

    def _validate_connection(self):
        """Verify API keys work on startup."""
        try:
            acct = self.api.get_account()
            mode = "PAPER" if "paper" in config.ALPACA_BASE_URL else "LIVE"
            print(f"  ✓  Alpaca connected ({mode}) — Cash: ${float(acct.cash):,.2f}")
        except Exception as e:
            print(f"  ✗  Alpaca connection failed: {e}")
            raise

    def get_account(self) -> dict:
        acct = self.api.get_account()
        return {
            "cash":           float(acct.cash),
            "buying_power":   float(acct.buying_power),
            "portfolio_value": float(acct.portfolio_value),
            "equity":         float(acct.equity),
            "pnl_today":      float(acct.equity) - float(acct.last_equity),
            "status":         acct.status,
        }

    def get_positions(self) -> list[dict]:
        positions = self.api.list_positions()
        return [
            {
                "symbol":       p.symbol,
                "qty":          int(p.qty),
                "side":         p.side,
                "entry_price":  float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "pnl":          float(p.unrealized_pl),
                "pnl_pct":      float(p.unrealized_plpc) * 100,
            }
            for p in positions
        ]

    def place_order(self, symbol: str, qty: int, side: str = "buy",
                    stop_loss: float = None, take_profit: float = None) -> dict:
        """
        Place a bracket order (entry + stop + target) or simple market order.

        Args:
            symbol:      Ticker (e.g. 'AAPL')
            qty:         Number of shares
            side:        'buy' or 'sell'
            stop_loss:   Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            Order details dict
        """
        try:
            if stop_loss and take_profit:
                # Bracket order: entry + stop + target
                order = self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type="market",
                    time_in_force="day",
                    order_class="bracket",
                    stop_loss={"stop_price": str(stop_loss)},
                    take_profit={"limit_price": str(take_profit)},
                )
            elif stop_loss:
                # OCO with just stop
                order = self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type="market",
                    time_in_force="day",
                    order_class="oto",
                    stop_loss={"stop_price": str(stop_loss)},
                )
            else:
                # Simple market order
                order = self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type="market",
                    time_in_force="day",
                )

            return {
                "id":         order.id,
                "symbol":     order.symbol,
                "qty":        int(order.qty),
                "side":       order.side,
                "type":       order.type,
                "status":     order.status,
                "created_at": str(order.created_at),
            }

        except Exception as e:
            print(f"  ✗  Order failed for {symbol}: {e}")
            return {"error": str(e)}

    def close_position(self, symbol: str) -> dict:
        try:
            order = self.api.close_position(symbol)
            return {
                "symbol": symbol,
                "status": "closed",
                "order_id": order.id if hasattr(order, 'id') else str(order),
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def close_all_positions(self) -> list[dict]:
        try:
            results = self.api.close_all_positions()
            return [{"status": "all positions closed", "count": len(results)}]
        except Exception as e:
            return [{"error": str(e)}]

    def get_order_history(self, limit: int = 20) -> list[dict]:
        orders = self.api.list_orders(status="all", limit=limit)
        return [
            {
                "id":         o.id,
                "symbol":     o.symbol,
                "qty":        o.qty,
                "side":       o.side,
                "type":       o.type,
                "status":     o.status,
                "filled_avg": o.filled_avg_price,
                "created":    str(o.created_at),
            }
            for o in orders
        ]

    def is_market_open(self) -> bool:
        clock = self.api.get_clock()
        return clock.is_open


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    broker = AlpacaBroker()
    print("\nAccount:")
    acct = broker.get_account()
    for k, v in acct.items():
        print(f"  {k}: {v}")

    print(f"\nMarket open: {broker.is_market_open()}")

    print("\nOpen positions:")
    positions = broker.get_positions()
    if positions:
        for p in positions:
            print(f"  {p['symbol']}: {p['qty']} shares, P&L: ${p['pnl']:.2f}")
    else:
        print("  No open positions")
