import json
import os
import ccxt
import pandas as pd
import requests
import yfinance as yf

_EXCHANGES: dict[str, object] = {}


def _get_exchange(name: str):
    key = name.lower()
    if key not in _EXCHANGES:
        if key == "binance":
            ex = ccxt.binance({"enableRateLimit": True})
        elif key == "okx":
            ex = ccxt.okx({"enableRateLimit": True})
        elif key == "kraken":
            ex = ccxt.kraken({"enableRateLimit": True})
        else:
            raise ValueError(f"Unsupported exchange: {name}")
        ex.load_markets()
        _EXCHANGES[key] = ex
    return _EXCHANGES[key]


def _resolve_ccxt_symbol(ex, symbol: str) -> str | None:
    clean = symbol.strip().upper()
    if clean in ex.markets:
        return clean

    if "/" in clean:
        base, quote = clean.split("/", 1)
        candidates = [f"{base}/{quote}"]
        if quote == "USDT":
            candidates.extend([f"{base}/USD", f"{base}/USDC"])
        elif quote == "USD":
            candidates.extend([f"{base}/USDT", f"{base}/USDC"])
        for cand in candidates:
            if cand in ex.markets:
                return cand
    else:
        for quote in ("USDT", "USD", "USDC"):
            if clean.endswith(quote) and len(clean) > len(quote):
                base = clean[: -len(quote)]
                for q in (quote, "USDT", "USD"):
                    cand = f"{base}/{q}"
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


def _map_ccxt_tf(timeframe: str) -> tuple[str, str | None]:
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
    market_symbol = _resolve_ccxt_symbol(ex, symbol)
    if not market_symbol:
        raise ValueError(f"{symbol} not found on {exchange_name}.")

    raw_tf, resample_rule = _map_ccxt_tf(timeframe)
    fetch_limit = limit * 5 if resample_rule else limit
    rows = ex.fetch_ohlcv(market_symbol, timeframe=raw_tf, limit=min(fetch_limit, 500))
    if not rows:
        raise ValueError(f"No candle data returned from {exchange_name} for {symbol}.")

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").astype(float)
    if resample_rule:
        df = _resample_ohlcv(df, resample_rule)
    return df.tail(limit)


def _mt5_feed_ohlcv(symbol: str, timeframe: str = "15m", limit: int = 250) -> pd.DataFrame | None:
    """
    داتای مۆمەکان لە MT5 دەخوێنێتەوە ئەگەر لە ڕێگەی سکریپتی ویندۆزەوە
    لە state/mt5_feed.json یان MT5_FEED_URL پاشەکەوت کرابێت.
    فۆرماتی چاوەڕوانکراو: {"XAU/USD": {"15m": [[ts_ms, o, h, l, c, v], ...]}}
    """
    payload = None
    feed_url = os.environ.get("MT5_FEED_URL", "").strip()
    feed_file = os.environ.get("MT5_FEED_FILE", "state/mt5_feed.json").strip()

    try:
        if feed_url:
            resp = requests.get(feed_url, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        elif feed_file and os.path.exists(feed_file):
            with open(feed_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    sym_keys = [symbol.strip().upper(), symbol.strip().upper().replace("/", "")]
    sym_block = None
    for k in sym_keys:
        if k in payload and isinstance(payload[k], dict):
            sym_block = payload[k]
            break

    if not sym_block:
        return None

    rows = sym_block.get(timeframe.strip().lower())
    if not isinstance(rows, list) or not rows:
        return None

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp").astype(float).tail(limit)


def _yf_candidates(symbol: str) -> list[str]:
    s = symbol.strip().upper()
    if s == "XAU/USD":
        return ["XAUUSD=X", "GC=F"]
    if s == "XAG/USD":
        return ["XAGUSD=X", "SI=F"]
    if "/" in s:
        base, quote = s.split("/", 1)
        return [f"{base}{quote}=X", f"{base}-{quote}"]
    if not s.endswith("=X") and not s.endswith("=F") and "-" not in s:
        return [s, f"{s}=X"]
    return [s]


def _yf_params(timeframe: str) -> tuple[str, str, str | None]:
    tf = timeframe.strip().lower()
    if tf == "1m":
        return "5d", "1m", None
    if tf == "5m":
        return "30d", "5m", None
    if tf == "15m":
        return "60d", "15m", None
    if tf == "30m":
        return "60d", "30m", None
    if tf == "1h":
        return "90d", "60m", None
    if tf == "4h":
        return "180d", "60m", "4h"
    if tf == "1d":
        return "2y", "1d", None
    if tf == "1w":
        return "5y", "1wk", None
    return "60d", "15m", None


def yf_ohlcv(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    period, interval, resample_rule = _yf_params(timeframe)

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
                    clean = clean[["open", "high", "low", "close", "volume"]].astype(float)
                    if resample_rule:
                        clean = _resample_ohlcv(clean, resample_rule)
                    return clean.tail(250)

    raise ValueError(f"No Yahoo Finance candle data found for {symbol} ({timeframe}).")


def get_market_data(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    s = symbol.strip().upper()
    tf = timeframe.strip().lower()

    # ١. ئەگەر داتای MT5 بەردەست بوو، لە پێش هەموو شت بەکار دەهێنرێت
    mt5_df = _mt5_feed_ohlcv(s, tf)
    if mt5_df is not None and not mt5_df.empty:
        return mt5_df

    fx_or_metals = {
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "USD/CHF",
        "AUD/USD",
        "USD/CAD",
        "NZD/USD",
        "XAU/USD",
        "XAG/USD",
        "XPT/USD",
        "XPD/USD",
    }
    if s in fx_or_metals or s.endswith("=X") or s.endswith("=F"):
        return yf_ohlcv(s, tf)

    # ٢. بۆ کریپتۆکان: سەرەتا Binance، پاشان OKX، پاشان Kraken
    for ex_name in ("binance", "okx", "kraken"):
        try:
            return exchange_ohlcv(ex_name, s, tf)
        except Exception:
            continue

    return yf_ohlcv(s, tf)