import os
from dotenv import load_dotenv
from market_data import get_market_data
from signal_engine import analyze

load_dotenv()
SYMBOLS = ["XAU/USD", "XAUT/USDT", "BTC/USDT", "ETH/USDT"]

def scan_all():
    min_score = int(os.getenv("MIN_SIGNAL_SCORE", "4"))
    timeframes = [x.strip() for x in os.getenv("SCAN_TIMEFRAMES", "15m,1h").split(",") if x.strip()]
    results = []
    for symbol in SYMBOLS:
        for tf in timeframes:
            try:
                df = get_market_data(symbol, tf)
                results.append(analyze(df, symbol, tf, min_score))
            except Exception as exc:
                results.append({"symbol": symbol, "timeframe": tf, "side": "ERROR", "error": str(exc)})
    return results
