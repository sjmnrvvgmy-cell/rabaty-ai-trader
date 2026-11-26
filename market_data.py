import ccxt
import pandas as pd
import yfinance as yf

KRAKEN_SYMBOLS = {
    "BTC/USDT": "BTC/USD",
    "ETH/USDT": "ETH/USD",
    "XAUT/USDT": "XAUT/USD",
}


def kraken_ohlcv(symbol: str, timeframe: str = "15m", limit: int = 250) -> pd.DataFrame:
    market_symbol = KRAKEN_SYMBOLS.get(symbol)
    if not market_symbol:
        raise ValueError(f"{symbol} is not mapped for Kraken.")

    exchange = ccxt.kraken({"enableRateLimit": True})
    rows = exchange.fetch_ohlcv(market_symbol, timeframe=timeframe, limit=limit)
    if not rows:
        raise ValueError(f"No candle data returned for {symbol} ({market_symbol}).")

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp").astype(float)


def xauusd_ohlcv(timeframe: str = "15m", period: str = "60d") -> pd.DataFrame:
    interval_map = {"5m": "5m", "15m": "15m", "1h": "60m", "4h": "1h", "1d": "1d"}
    interval = interval_map.get(timeframe, "15m")

    for ticker in ("GC=F", "XAUUSD=X"):
        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
        if data is not None and not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.rename(columns=str.lower)
            required = ["open", "high", "low", "close"]
            if all(col in data.columns for col in required):
                clean = data[required].dropna()
                if not clean.empty:
                    clean.index = pd.to_datetime(clean.index, utc=True)
                    clean["volume"] = 0.0
                    return clean[["open", "high", "low", "close", "volume"]].astype(float)

    raise ValueError("Yahoo Finance did not return gold candles.")


def get_market_data(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    if symbol == "XAU/USD":
        return xauusd_ohlcv(timeframe)
    return kraken_ohlcv(symbol, timeframe)
