# 🤖 AI Trading Bot

An automated stock trading bot that scans the S&P 500 for high-probability setups, executes bracket orders via **Alpaca**, and sends real-time alerts to **Telegram**.

> **⚠️ Paper trading only.** This bot is designed for educational purposes and paper trading. Use at your own risk.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Market Scanner** | Scans S&P 500 stocks for volume, momentum & technical setups |
| **Technical Analysis** | RSI, MACD, Bollinger Bands, ATR, EMAs, VWAP & more |
| **Scoring Engine** | Scores each stock 0–100 based on multi-indicator strategy |
| **Risk Management** | Per-trade risk limits, max daily loss, position sizing |
| **Bracket Orders** | Auto stop-loss & take-profit via ATR multipliers |
| **Telegram Alerts** | Real-time notifications for trades, errors & daily summaries |
| **Backtesting** | Test strategies against historical data before going live |
| **Modular Design** | Swap brokers (Alpaca → Zerodha / Angel One) via abstract interface |

---

## 🏗️ Architecture

```
bot.py              → Main orchestrator (scheduler + trading loop)
├── scanner.py      → Scans S&P 500, ranks by composite score
├── strategy.py     → Generates BUY / SELL / HOLD signals
├── indicators.py   → Technical indicator calculations
├── data_fetcher.py → OHLCV data via yfinance
├── risk_manager.py → Position sizing, risk gates, trade validation
├── broker.py       → Broker abstraction (Alpaca implementation)
├── notifier.py     → Telegram Bot API notifications
├── backtester.py   → Historical backtesting engine
└── config.py       → Centralised settings (reads .env)
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/yourusername/ai-trading-bot.git
cd ai-trading-bot
pip install -r requirements.txt
```

### 2. Configure API keys

Copy the example environment file and add your keys:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Alpaca (https://app.alpaca.markets)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Telegram (https://t.me/BotFather)
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Verify setup

```bash
python test_setup.py
```

### 4. Run the bot

```bash
# Single scan-and-trade cycle (great for testing)
python bot.py --once

# Full scheduled mode (runs during market hours)
python bot.py
```

---

## ⚙️ Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `PAPER_MODE` | `True` | Paper vs live trading |
| `MAX_RISK_PER_TRADE` | `2%` | Max risk per trade as % of account |
| `MAX_OPEN_TRADES` | `3` | Maximum concurrent positions |
| `MAX_DAILY_LOSS_PCT` | `3%` | Halt trading if daily loss exceeds this |
| `MIN_STOCK_SCORE` | `65` | Only trade stocks scoring ≥ 65/100 |
| `STOP_LOSS_ATR_MULT` | `1.5` | Stop loss = Entry − 1.5 × ATR |
| `TAKE_PROFIT_ATR_MULT` | `3.0` | Target = Entry + 3.0 × ATR |
| `MIN_PRICE` | `$5` | Ignore penny stocks |
| `MIN_VOLUME` | `500K` | Minimum daily volume |

---

## 📊 How It Works

```
Market Opens
     │
     ▼
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Scanner    │────▶│  Strategy    │────▶│ Risk Manager  │
│  (S&P 500)  │     │  (Score 0-100)│     │ (Size + Gate) │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                    ┌─────────────▼─────────────┐
                                    │      Bracket Order        │
                                    │  Entry + Stop + Target    │
                                    └─────────────┬─────────────┘
                                                  │
                              ┌────────────────────┼────────────────────┐
                              ▼                    ▼                    ▼
                        📱 Telegram          📈 Alpaca            📋 Log File
                         Alert              Execution             Record
```

1. **Scan** — Fetches OHLCV data for S&P 500 stocks, calculates technical indicators
2. **Score** — Each stock gets a composite score (RSI, MACD, Bollinger, volume, trend)
3. **Filter** — Only stocks scoring ≥ 65/100 pass through
4. **Risk Check** — Validates position size, daily loss limit, max open trades
5. **Execute** — Places bracket order (market entry + stop-loss + take-profit)
6. **Notify** — Sends trade details to Telegram in real-time

---

## 📱 Telegram Notifications

The bot sends formatted alerts for:

- 🟢 **Order placed** — symbol, shares, entry, stop, target
- ✅❌ **Position closed** — P&L and percentage
- 📊 **Daily summary** — total P&L, win rate, trade list
- 🚨 **Errors** — any failures or risk gate triggers
- 🤖 **Bot start / stop** — status updates

---

## 🧪 Backtesting

```bash
python backtester.py
```

Test the strategy against historical data to validate performance before paper trading.

---

## 📋 Requirements

- Python 3.10+
- [Alpaca](https://alpaca.markets/) account (free paper trading)
- [Telegram Bot](https://t.me/BotFather) (free)

---

## 📄 License

This project is for educational purposes. Use at your own risk. Not financial advice.
