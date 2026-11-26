import ccxt
import pandas as pd
import yfinance as yf

BYBIT_SYMBOLS = {
    "XAUT/USDT": "XAUT/USDT",
    "BTC/USDT": "BTC/USDT",
    "ETH/USDT": "ETH/USDT",
}

def bybit_ohlcv(symbol: str, timeframe: str = "15m", limit: int = 250) -> pd.DataFrame:
    exchange = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    markets = exchange.load_markets()
    if symbol not in markets:
        raise ValueError(f"{symbol} is not listed on Bybit spot. Check the symbol or market availability.")
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not rows:
        raise ValueError(f"No candle data returned for {symbol}.")
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp").astype(float)

def xauusd_ohlcv(timeframe: str = "15m", period: str = "60d") -> pd.DataFrame:
    # Yahoo Finance ticker for spot gold quoted in USD. Data availability/intervals
    # depend on Yahoo; this is a public-data fallback, not a broker execution quote.
    interval_map = {"5m": "5m", "15m": "15m", "1h": "60m", "4h": "1h", "1d": "1d"}
    interval = interval_map.get(timeframe, "15m")
    data = yf.download("XAUUSD=X", period=period, interval=interval, auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError("Yahoo Finance did not return XAU/USD candles. Try later or use another licensed data provider.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.rename(columns=str.lower)
    required = ["open", "high", "low", "close"]
    data = data[required].dropna()
    data.index = pd.to_datetime(data.index, utc=True)
    data["volume"] = 0.0
    return data[["open", "high", "low", "close", "volume"]].astype(float)

def get_market_data(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    if symbol == "XAU/USD":
        return xauusd_ohlcv(timeframe)
    return bybit_ohlcv(symbol, timeframe)
