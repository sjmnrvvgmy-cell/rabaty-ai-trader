import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests


BAGHDAD_TZ = ZoneInfo("Asia/Baghdad")


def format_exact_price(val: float | int) -> str:
    """نیشاندانی نرخ بە 5 خاڵی دەیی."""
    return f"{float(val):.5f}"


def fetch_okx_price(symbol: str, bar: str = "1H") -> float | None:
    """هێنانی نرخ لە OKX بەپێی تایمفرێم."""
    inst_id = symbol.strip().upper().replace("/", "-")
    url = "https://www.okx.com/api/v5/market/candles"
    try:
        resp = requests.get(
            url,
            params={"instId": inst_id, "bar": bar, "limit": "2"},
            timeout=10,
        )
        resp.raise_for_status()
        candles = (resp.json().get("data") or [])
        if len(candles) >= 2 and len(candles[1]) >= 5:
            return float(candles[1][4])
        if candles and len(candles[0]) >= 5:
            return float(candles[0][4])
        return None
    except Exception:
        return None


def fetch_binance_price(symbol: str, interval: str = "1h") -> float | None:
    """هێنانی نرخ لە Binance بەپێی تایمفرێم."""
    pair = symbol.strip().upper().replace("/", "").replace("-", "")
    url = "https://api.binance.com/api/v3/klines"
    try:
        resp = requests.get(
            url,
            params={"symbol": pair, "interval": interval, "limit": 2},
            timeout=10,
        )
        resp.raise_for_status()
        klines = resp.json()
        if len(klines) >= 2 and len(klines[0]) >= 5:
            return float(klines[0][4])
        if klines and len(klines[0]) >= 5:
            return float(klines[0][4])
        return None
    except Exception:
        return None


def get_live_price_for_signal(item: dict) -> float:
    """هەوڵ دەدات نرخی ئەو کاتە بهێنێت؛ ئەگەر نەبوو نرخی ناو سیگناڵەکە بەکاردەهێنێت."""
    symbol = item["symbol"]
    tf = item.get("timeframe", "1h").lower()

    okx_bar = "1H" if tf == "1h" else "15m"
    bn_interval = "1h" if tf == "1h" else "15m"

    price = fetch_okx_price(symbol, bar=okx_bar)
    if price is not None and price > 0:
        return price

    price = fetch_binance_price(symbol, interval=bn_interval)
    if price is not None and price > 0:
        return price

    return float(item["entry"])


def compute_levels_from_price(entry: float, is_buy: bool = True) -> tuple[float, float, float, float]:
    """حیسابکردنی SL و TP1/TP2/TP3 بە شێوەی هاوسەنگ لەسەر بنەمای نرخی چوونەژوورەوە."""
    step = max(entry * 0.005, 0.0005)
    if is_buy:
        sl = round(entry - step, 5)
        tp1 = round(entry + step, 5)
        tp2 = round(entry + step * 1.8, 5)
        tp3 = round(entry + step * 2.5, 5)
    else:
        sl = round(entry + step, 5)
        tp1 = round(entry - step, 5)
        tp2 = round(entry - step * 1.8, 5)
        tp3 = round(entry - step * 2.5, 5)
    return sl, tp1, tp2, tp3


def pick_active_signal(signals: list[dict], now_local: datetime) -> dict:
    """هەڵبژاردنی تەنها یەک سیگناڵی بەردەست لەو کاتەدا."""
    if not signals:
        raise ValueError("هیچ سیگناڵێک لە لیستەکەدا نییە.")
    idx = now_local.hour % len(signals)
    return signals[idx]


def build_single_signal_message(item: dict, now_utc: datetime, now_local: datetime) -> str:
    """دروستکردنی نامەی تەنها یەک سیگناڵ بە نرخی ئەو کاتەی داواکارییەکە دەکرێت."""
    utc_header = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    date_str = now_local.strftime("%Y-%m-%d")
    time_12h = now_local.strftime("%I:%M:%S %p")

    current_price = get_live_price_for_signal(item)
    is_buy = "BUY" in item.get("side_label", "BUY").upper() or "کڕین" in item.get("side_label", "")
    sl, tp1, tp2, tp3 = compute_levels_from_price(current_price, is_buy=is_buy)

    current_price_str = format_exact_price(current_price)
    entry_str = format_exact_price(current_