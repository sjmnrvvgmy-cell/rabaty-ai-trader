import ccxt
import pandas as pd

_EXCHANGES: dict[str, object] = {}


def _get_exchange(name: str):
    key = name.strip().lower()
    if key not in _EXCHANGES:
        if key == "okx":
            ex = ccxt.okx({"enableRateLimit": True})
        elif key == "binance":
            ex = ccxt.binance({"enableRateLimit": True})
        else:
            raise ValueError(f"Unsupported exchange: {name}")
        ex.load_markets()
        _EXCHANGES[key] = ex
    return _EXCHANGES[key]


def _symbol_candidates(symbol: str) -> list[str]:
    clean = symbol.strip().upper().replace("-", "/")
    if clean in ("XAU/USD", "XAUUSD", "GOLD"):
        return ["XAUT/USDT", "PAXG/USDT", "PAXG/USD", "XAU/USDT"]
    if clean in ("XAG/USD", "XAGUSD", "SILVER"):
        return ["XAG/USDT", "XAG/USD"]

    if "/" in clean:
        base, quote = clean.split("/", 1)
        out = [f"{base}/{quote}"]
        if quote == "USDT":
            out.extend([f"{base}/USD", f"{base}/USDC"])
        elif quote == "USD":
            out.extend([f"{base}/USDT", f"{base}/USDC"])
        return out

    for quote in ("USDT", "USD", "USDC"):
        if clean.endswith(quote) and len(clean) > len(quote):
            base = clean[: -len(quote)]
            return [f"{base}/{quote}", f"{base}/USDT", f"{base}/USD"]

    return [f"{clean}/USDT", f"{clean}/USD", clean]


def _resolve_market(ex, symbol: str) -> str | None:
    for cand in _symbol_candidates(symbol):
        if cand in ex.markets:
            return cand
    return None


def _resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    out = df.resample(rule).agg(agg).dropna(subset=["open", "high", "low", "close"])
    return out.astype(float)


def _map_timeframe(timeframe: str) -> tuple[str, str | None]:
    tf = timeframe.strip().lower()
    mapping = {
        "1m": ("1m", None),
        "5m": ("5m", None),
        "15m": ("15m", None),
        "30m": ("30m", None),
        "1h": ("1h", None),
        "4h": ("1h", "4h"),
        "1d": ("1d", None),
        "1w": ("1w", None),
    }
    return mapping.get(tf, ("15m", None))


def exchange_ohlcv(exchange_name: str, symbol: str, timeframe: str = "15m", limit: int = 250) -> pd.DataFrame:
    ex = _get_exchange(exchange_name)
    market_symbol = _resolve_market(ex, symbol)
    if not market_symbol:
        raise ValueError(f"{symbol} not found on {exchange_name}.")

    raw_tf, resample_rule = _map_timeframe(timeframe)
    fetch_limit = limit * 5 if resample_rule else limit
    rows = ex.fetch_ohlcv(market_symbol, timeframe=raw_tf, limit=min(fetch_limit, 500))
    if not rows:
        raise ValueError(f"No candle data returned from {exchange_name} for {market_symbol}.")

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").astype(float)
    if resample_rule:
        df = _resample_ohlcv(df, resample_rule)
    return df.tail(limit)


def get_market_data(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    errors: list[str] = []
    for ex_name in ("okx", "binance"):
        try:
            df = exchange_ohlcv(ex_name, symbol, timeframe)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            errors.append(f"{ex_name}: {e}")

    raise ValueError(f"Could not fetch {symbol} ({timeframe}) from OKX or Binance. Details: {' | '.join(errors)}")