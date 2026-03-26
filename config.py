# config.py — centralised settings (secrets loaded from .env)

import os
from dotenv import load_dotenv

load_dotenv()

# ── Paper mode ───────────────────────────────────────────────────────────────
PAPER_MODE = True   # change to False only after 2+ weeks of paper trading

# ── Alpaca (US stocks — paper trading) ───────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# ── Telegram alerts ──────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ── Personal risk profile ───────────────────────────────────────────────────
ACCOUNT_SIZE         = 100_000     # paper account size in USD
MAX_RISK_PER_TRADE   = 0.02       # 2 % max risk per trade
MAX_OPEN_TRADES      = 3          # never more than 3 at once
MAX_DAILY_LOSS_PCT   = 0.03       # halt if day loss hits 3 %
MIN_STOCK_SCORE      = 65         # only trade stocks scoring 65+ / 100
STOP_LOSS_ATR_MULT   = 1.5        # stop  = entry − 1.5 × ATR
TAKE_PROFIT_ATR_MULT = 3.0        # target = entry + 3.0 × ATR

# ── Schedule (US Eastern — NYSE/NASDAQ hours) ────────────────────────────────
MARKET_OPEN_TIME  = "09:35"       # 5 min after US market open
MARKET_CLOSE_TIME = "15:50"       # 10 min before close — square off

# ── Scan / filter settings ──────────────────────────────────────────────────
MIN_PRICE      = 5                # ignore penny stocks below $5
MIN_VOLUME     = 500_000          # ignore low-liquidity stocks
MIN_MARKET_CAP = 1e9              # ignore sub-$1 B companies
WATCHLIST      = "sp500"          # sp500 / custom

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FILE  = "trading_bot.log"