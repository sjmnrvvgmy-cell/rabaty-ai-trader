import time
import ccxt
import pandas as pd

_EXCHANGES: dict[str, object] = {}


def _build_exchange(key: str):
    common_opts = {
        "enableRateLimit": True,
        "timeout": 15000,
    }
    if key == "okx":
        return ccxt.okx(common_opts)
    if key == "binance":
        return ccxt.binance(common_opts)
    raise ValueError(f"Unsupported exchange: {key}")


def _get_exchange(name: str):
    key = name.strip().lower()
    if key not in _EXCHANGES:
        ex = _build_exchange(key)
        last_err = None
        for attempt in range(2):
            try:
                ex.load_markets()
                last_err = None
                break
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))
        if last_err is not None:
            raise RuntimeError(f"Failed to load markets for {key}: {last_err}")
        _EXCHANGES[key] = ex
    return _EXCHANGES[key]


def _symbol_candidates(symbol: str) -> list[str]:
    clean = symbol.strip().upper().replace("-", "/")
    if clean in ("XAU/USD", "XAUUSD", "GOLD", "XAUT/USDT"):
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
    markets = getattr(ex, "markets", None) or {}
    for cand in _symbol_candidates(symbol):
        if cand in markets:
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
        "2h": ("2h", None),
        "4h": ("4h", None),
        "6h": ("6h", None),
        "12h": ("12h", None),
        "1d": ("1d", None),
        "1w": ("1w", None),
    }
    return mapping.get(tf, ("15m", None))


def _clean_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for col in ("open", "high", "low", "close", "volume"):
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    cleaned = cleaned.dropna(subset=["open", "high", "low", "close"])
    cleaned = cleaned[(cleaned["open"] > 0) & (cleaned["high"] > 0) & (cleaned["low"] > 0) & (cleaned["close"] > 0)]
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")].sort_index()
    return cleaned.astype(float)


def exchange_ohlcv(
    exchange_name: str,
    symbol: str,
    timeframe: str = "15m",
    limit: int = 250,
    retries: int = 2,
) -> pd.DataFrame:
    ex = _get_exchange(exchange_name)
    market_symbol = _resolve_market(ex, symbol)
    if not market_symbol:
        raise ValueError(f"{symbol} not found on {exchange_name}.")

    raw_tf, resample_rule = _map_timeframe(timeframe)
    timeframes_map = getattr(ex, "timeframes", None) or {}
    if raw_tf not in timeframes_map and timeframe.strip().lower() == "4h":
        raw_tf, resample_rule = "1h", "4h"

    fetch_limit = limit * 5 if resample_rule else limit
    rows = None
    last_err = None

    for attempt in range(retries):
        try:
            rows = ex.fetch_ohlcv(market_symbol, timeframe=raw_tf, limit=min(fetch_limit, 500))
            if rows:
                last_err = None
                break
            last_err = ValueError(f"Empty OHLCV list returned for {market_symbol}.")
        except Exception as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(0.8 * (attempt + 1))

    if not rows:
        raise ValueError(f"No candle data returned from {exchange_name} for {market_symbol}: {last_err}")

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df = _clean_ohlcv_df(df)

    if resample_rule:
        df = _resample_ohlcv(df, resample_rule)
        df = _clean_ohlcv_df(df)

    if df.empty:
        raise ValueError(f"Cleaned candle data is empty on {exchange_name} for {market_symbol}.")

    return df.tail(limit)


def get_market_data(symbol: str, timeframe: str = "15m", limit: int = 250) -> pd.DataFrame:
    errors: list[str] = []
    for ex_name in ("okx", "binance"):
        try:
            df = exchange_ohlcv(ex_name, symbol, timeframe=timeframe, limit=limit)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            errors.append(f"{ex_name}: {e}")

    raise ValueError(f"Could not fetch {symbol} ({timeframe}) from OKX or Binance. Details: {' | '.join(errors)}")