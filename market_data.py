import pandas as pd
import requests
import yfinance as yf

BINANCE_SYMBOLS = {
    "BTC/USDT": "BTCUSDT",
    "ETH/USDT": "ETHUSDT",
    "XAUT/USDT": "XAUTUSDT",
}

BINANCE_INTERVAL_MAP = {
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def binance_ohlcv(symbol: str, timeframe: str = "15m", limit: int = 250) -> pd.DataFrame:
    market_symbol = BINANCE_SYMBOLS.get(symbol)
    if not market_symbol:
        raise ValueError(f"{symbol} is not mapped for Binance public candles.")

    interval = BINANCE_INTERVAL_MAP.get(timeframe, "15m")
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": market_symbol, "interval": interval, "limit": limit}
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    rows = response.json()

    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No candle data returned for {symbol} ({market_symbol}).")

    df = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )[["timestamp", "open", "high", "low", "close", "volume"]]

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp").astype(float)


def xauusd_ohlcv(timeframe: str = "15m", period: str = "60d") -> pd.DataFrame:
    interval_map = {"5m": "5m", "15m": "15m", "1h": "60m", "4h": "1h", "1d": "1d"}
    interval = interval_map.get(timeframe, "15m")

    for ticker in ("XAUUSD=X", "GC=F"):
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

    raise ValueError("Yahoo Finance did not return XAU/USD or GC=F candles.")


def get_market_data(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    if symbol == "XAU/USD":
        return xauusd_ohlcv(timeframe)
    return binance_ohlcv(symbol, timeframe)
