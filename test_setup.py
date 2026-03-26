# test_setup.py — verify all dependencies and connections

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

print("=" * 50)
print("  AI Trading Bot - Setup Check")
print("=" * 50)

# ── Dependencies ─────────────────────────────────────────────────────────────
deps = {
    "dotenv":          "python-dotenv",
    "pandas":          "pandas",
    "numpy":           "numpy",
    "yfinance":        "yfinance",
    "ta":              "ta",
    "alpaca_trade_api": "alpaca-trade-api",
    "requests":        "requests",
    "schedule":        "schedule",
    "colorama":        "colorama",
    "matplotlib":      "matplotlib",
}

print("\n1. Checking dependencies...\n")
missing = []
for module, pip_name in deps.items():
    try:
        __import__(module)
        print(f"   [OK]  {pip_name}")
    except ImportError:
        print(f"   [X]   {pip_name}  ->  pip install {pip_name}")
        missing.append(pip_name)

if missing:
    print(f"\n   Install missing: pip install {' '.join(missing)}")

# ── Config ───────────────────────────────────────────────────────────────────
print("\n2. Checking config...\n")
try:
    import config
    checks = {
        "ALPACA_API_KEY":    bool(config.ALPACA_API_KEY),
        "ALPACA_SECRET_KEY": bool(config.ALPACA_SECRET_KEY),
        "TELEGRAM_TOKEN":    bool(config.TELEGRAM_TOKEN),
        "TELEGRAM_CHAT_ID":  bool(config.TELEGRAM_CHAT_ID),
    }
    for key, ok in checks.items():
        status = "[OK] " if ok else "[X]  "
        label = "set" if ok else "MISSING - check .env"
        print(f"   {status} {key}: {label}")
except Exception as e:
    print(f"   [X]  Config error: {e}")

# ── Alpaca connection ────────────────────────────────────────────────────────
print("\n3. Testing Alpaca connection...\n")
try:
    import alpaca_trade_api as tradeapi
    api = tradeapi.REST(
        config.ALPACA_API_KEY,
        config.ALPACA_SECRET_KEY,
        config.ALPACA_BASE_URL,
    )
    account = api.get_account()
    print(f"   [OK]  Connected to Alpaca (Paper)")
    print(f"         Cash: ${float(account.cash):,.2f}")
    print(f"         Equity: ${float(account.equity):,.2f}")
    print(f"         Status: {account.status}")
except Exception as e:
    print(f"   [X]   Alpaca error: {e}")

# ── yfinance data ────────────────────────────────────────────────────────────
print("\n4. Testing market data (yfinance)...\n")
try:
    import yfinance as yf
    ticker = yf.Ticker("AAPL")
    hist = ticker.history(period="5d")
    if not hist.empty:
        last = hist.iloc[-1]
        print(f"   [OK]  AAPL last close: ${last['Close']:.2f}")
        print(f"         Volume: {last['Volume']:,.0f}")
    else:
        print("   [!]   No data returned for AAPL")
except Exception as e:
    print(f"   [X]   yfinance error: {e}")

# ── Telegram ─────────────────────────────────────────────────────────────────
print("\n5. Testing Telegram...\n")
try:
    import requests as req
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getMe"
    resp = req.get(url, timeout=10)
    if resp.status_code == 200 and resp.json().get("ok"):
        bot_name = resp.json()["result"]["username"]
        print(f"   [OK]  Telegram bot: @{bot_name}")
    else:
        print(f"   [X]   Telegram error: {resp.text}")
except Exception as e:
    print(f"   [X]   Telegram error: {e}")

# ── Module imports ───────────────────────────────────────────────────────────
print("\n6. Testing bot modules...\n")
modules = [
    "config", "data_fetcher", "indicators", "strategy",
    "risk_manager", "notifier",
]
for mod in modules:
    try:
        __import__(mod)
        print(f"   [OK]  {mod}")
    except Exception as e:
        print(f"   [X]   {mod}: {e}")

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
if not missing:
    print("  All checks passed - ready to trade!")
else:
    print(f"  Fix {len(missing)} missing dependencies first")
print(f"{'='*50}\n")
