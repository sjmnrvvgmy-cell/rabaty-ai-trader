import ccxt
import pandas as pd
import yfinance as yf

_KRAKEN_EXCHANGE = None


def _get_kraken():
    global _KRAKEN_EXCHANGE
    if _KRAKEN_EXCHANGE is None:
        ex = ccxt.kraken({"enableRateLimit": True})
        ex.load_markets()
        _KRAKEN_EXCHANGE = ex
    return _KRAKEN_EXCHANGE


def _resolve_kraken_symbol(symbol: str) -> str | None:
    ex = _get_kraken()
    clean = symbol.strip().upper()
    if clean in ex.markets:
        return clean

    if "/" in clean:
        base, quote = clean.split("/", 1)
        candidates = [f"{base}/{quote}"]
        if quote == "USDT":
            candidates.extend([f"{base}/USD", f"{base}/EUR"])
        elif quote == "USD":
            candidates.extend([f"{base}/USDT", f"{base}/EUR"])
        for cand in candidates:
            if cand in ex.markets:
                return cand
    else:
        for quote in ("USD", "USDT", "EUR"):
            if clean.endswith(quote) and len(clean) > len(quote):
                base = clean[: -len(quote)]
                for q in (quote, "USD", "USDT"):
                    cand = f"{base}/{q}"
                    if cand in ex.markets:
                        return cand
    return None


def kraken_ohlcv(symbol: str, timeframe: str = "15m", limit: int = 250) -> pd.DataFrame:
    market_symbol = _resolve_kraken_symbol(symbol)
    if not market_symbol:
        raise ValueError(f"{symbol} not found on Kraken.")

    ex = _get_kraken()
    rows = ex.fetch_ohlcv(market_symbol, timeframe=timeframe, limit=limit)
    if not rows:
        raise ValueError(f"No candle data returned for {symbol} ({market_symbol}).")

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp").astype(float)


def _yf_candidates(symbol: str) -> list[str]:
    s = symbol.strip().upper()
    if s == "XAU/USD":
        return ["GC=F", "XAUUSD=X"]
    if s == "XAG/USD":
        return ["SI=F", "XAGUSD=X"]
    if "/" in s:
        base, quote = s.split("/", 1)
        return [f"{base}{quote}=X", f"{base}-{quote}"]
    if not s.endswith("=X") and not s.endswith("=F") and "-" not in s:
        return [s, f"{s}=X"]
    return [s]


def yf_ohlcv(symbol: str, timeframe: str = "15m", period: str = "60d") -> pd.DataFrame:
    interval_map = {"5m": "5m", "15m": "15m", "1h": "60m", "4h": "1h", "1d": "1d"}
    interval = interval_map.get(timeframe, "15m")

    for ticker in _yf_candidates(symbol):
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

    raise ValueError(f"No Yahoo Finance candle data found for {symbol}.")


def get_market_data(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    s = symbol.strip().upper()
    # ئەگەر جووتەکە لە Kraken هەبوو یان شێوازی کریپتۆ بوو (وەک /USDT یان /USD جگە لە دراوە سەرەکییەکان)
    fx_or_metals = {
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD",
        "XAU/USD", "XAG/USD", "XPT/USD", "XPD/USD",
    }
    if s in fx_or_metals or s.endswith("=X") or s.endswith("=F"):
        return yf_ohlcv(s, timeframe)

    if _resolve_kraken_symbol(s):
        return kraken_ohlcv(s, timeframe)

    return yf_ohlcv(s, timeframe)