import os
from dotenv import load_dotenv
from market_data import get_market_data
from signal_engine import analyze

load_dotenv()

DEFAULT_SYMBOLS = [
    # کانزاکان (Metals)
    "XAU/USD",
    "XAG/USD",
    "XAUT/USDT",
    # دراوەکان (Forex)
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    # کریپتۆکان (Crypto)
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "LINK/USDT",
]


def _get_symbols() -> list[str]:
    env_symbols = os.getenv("SCAN_SYMBOLS", "").strip()
    if env_symbols:
        return [s.strip().upper() for s in env_symbols.split(",") if s.strip()]
    return DEFAULT_SYMBOLS


def scan_all():
    min_score = int(os.getenv("MIN_SIGNAL_SCORE", "4"))
    timeframes = [x.strip() for x in os.getenv("SCAN_TIMEFRAMES", "15m,1h").split(",") if x.strip()]
    symbols = _get_symbols()
    results = []

    for symbol in symbols:
        for tf in timeframes:
            try:
                df = get_market_data(symbol, tf)
                results.append(analyze(df, symbol, tf, min_score))
            except Exception as exc:
                results.append({"symbol": symbol, "timeframe": tf, "side": "ERROR", "error": str(exc)})

    return results