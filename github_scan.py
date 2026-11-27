import csv
import io
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests


BAGHDAD_TZ = ZoneInfo("Asia/Baghdad")


def format_exact_price(val: float | int) -> str:
    """نیشاندانی نرخ بە 5 خاڵی دەیی."""
    return f"{float(val):.5f}"


def to_stooq_symbol(symbol: str) -> str | None:
    """گۆڕینی هێمای سیگناڵ بۆ هێمای بازاڕی جیهانی لە Stooq."""
    clean = symbol.strip().upper().replace("/", "").replace("-", "")
    mapping = {
        "XAUTUSDT": "xauusd",
        "XAUUSDT": "xauusd",
        "XAUUSD": "xauusd",
        "XAU": "xauusd",
        "GOLD": "xauusd",
        "USDJPY": "usdjpy",
        "USDCHF": "usdchf",
        "EURUSD": "eurusd",
        "GBPUSD": "gbpusd",
        "BTCUSDT": "btcusd",
        "BTCUSD": "btcusd",
        "ETHUSDT": "ethusd",
        "ETHUSD": "ethusd",
    }
    if clean in mapping:
        return mapping[clean]
    if clean.endswith("USDT") and len(clean) > 4:
        return (clean[:-4] + "USD").lower()
    return clean.lower() if clean else None


def fetch_global_stooq_price(symbol: str) -> float | None:
    """هێنانی کۆتا نرخ لە بازاڕی جیهانی (Stooq)."""
    stooq_sym = to_stooq_symbol(symbol)
    if not stooq_sym:
        return None

    url = f"https://stooq.com/q/l/?s={stooq_sym}&f=sd2t2ohlcv&h&e=csv"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        row = next(reader, None)
        if not row:
            return None
        close_val = (row.get("Close") or "").strip()
        if not close_val or close_val.upper() in ("N/D", "NONE"):
            return None
        price = float(close_val)
        return price if price > 0 else None
    except Exception:
        return None


def fetch_global_fx_price(symbol: str) -> float | None:
    """هێنانی نرخی جوتی دراوی فۆرێکس لە سەرچاوەی جیهانی (Frankfurter)."""
    clean = symbol.strip().upper().replace("/", "").replace("-", "")
    if len(clean) != 6:
        return None
    base, quote = clean[:3], clean[3:]
    if base == quote:
        return None
    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": base, "to": quote},
            timeout=10,
        )
        resp.raise_for_status()
        rates = resp.json().get("rates") or {}
        val = rates.get(quote)
        if val is not None:
            price = float(val)
            return price if price > 0 else None
        return None
    except Exception:
        return None


def get_global_market_price(item: dict) -> float:
    """وەرگرتنی نرخی بازاڕی جیهانی؛ ئەگەر نەبوو نرخی ناو سیگناڵەکە بەکاردەهێنێت."""
    symbol = item["symbol"]
    price = fetch_global_stooq_price(symbol)
    if price is not None:
        return price

    fx_price = fetch_global_fx_price(symbol)
    if fx_price is not None:
        return fx_price

    return float(item["entry"])


def compute_levels_from_price(entry: float, is_buy: bool = True) -> tuple[float, float, float, float]:
    """حیسابکردنی SL و TP1/TP2/TP3 بە شێوەی هاوسەنگ لەسەر بنەمای نرخی ئەو کاتە."""
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
    """دروستکردنی نامەی تەنها یەک سیگناڵ بە نرخی بازاڕی جیهانی لە کاتی داواکاری."""
    utc_header = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    date_str = now_local.strftime("%Y-%m-%d")
    time_12h = now_local.strftime("%I:%M:%S %p")

    current_price = get_global_market_price(item)
    is_buy = "BUY" in item.get("side_label", "BUY").upper() or "کڕین" in item.get("side_label", "")
    sl, tp1, tp2, tp3 = compute_levels_from_price(current_price, is_buy=is_buy)

    current_price_str = format_exact_price(current_price)
    entry_str = format_exact_price(current_price)
    sl_str = format_exact_price(sl)
    tp1_str = format_exact_price(tp1)
    tp2_str = format_exact_price(tp2)
    tp3_str = format_exact_price(tp3)
    rsi_str = f"{float(item['rsi']):.1f}"

    header = (
        "📊 ڕەباتی ئەی ئای ترەیدەر (RABATY AI TRADER) — سیگناڵی نوێ\n"
        f"🕒 کات: {utc_header}"
    )

    block = (
        f"🗓️ بەروار و کاتی سیگناڵ: {date_str} | {time_12h} | 💰 نرخی ئەو کاتە: {current_price_str}\n"
        f"{item.get('emoji', '🟢')} {item['symbol']} — {item['side_label']}\n"
        f"تایمفرێم: {item.get('timeframe', '1h')} | خاڵ: {item.get('score', 4)}\n"
        f"نرخی چوونەژوورەوە: {entry_str}\n"
        f"ستۆپ لۆس (SL): {sl_str}\n"
        f"ئامانجی 1 (TP1): {tp1_str}\n"
        f"ئامانجی 2 (TP2): {tp2_str}\n"
        f"ئامانجی 3 (TP3): {tp3_str}\n"
        f"RSI: {rsi_str}\n"
        f"هۆکارەکان: {item['reasons']}\n"
        f"تێبینی: ئەمە سیگناڵی تەکنیکییە؛ پێش چوونەناوەوە سپرێد و مەترسی بپشکنە."
    )

    return f"{header}\n\n{block}"


def send_telegram_message(text: str) -> None:
    """ناردنی نامە بۆ تێلێگرام."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    print(text)

    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def main() -> None:
    signals = [
        {
            "symbol": "XAUT/USDT",
            "side_label": "کڕین (BUY)",
            "emoji": "🟢",
            "timeframe": "1h",
            "score": 4,
            "entry": 3667.50000,
            "rsi": 78.6,
            "reasons": "مەیلی EMA سەرەوەیە، شکاندنی بەرزایی پێشوو (BOS سەرەوە)، دروستبوونی FVG سەرەوە",
        },
        {
            "symbol": "USD/JPY",
            "side_label": "کڕین (BUY)",
            "emoji": "🟢",
            "timeframe": "15m",
            "score": 4,
            "entry": 159.42400,
            "rsi": 68.5,
            "reasons": "مەیلی EMA سەرەوەیە، زەبری RSI پاڵپشتی کڕینە، شکاندنی بەرزایی پێشوو (BOS سەرەوە)",
        },
        {
            "symbol": "USD/CHF",
            "side_label": "کڕین (BUY)",
            "emoji": "🟢",
            "timeframe": "1h",
            "score": 4,
            "entry": 0.83608,
            "rsi": 66.7,
            "reasons": "زەبری RSI پاڵپشتی کڕینە، شکاندنی بەرزایی پێشوو (BOS سەرەوە)، دروستبوونی FVG سەرەوە",
        },
    ]

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(BAGHDAD_TZ)

    active_signal = pick_active_signal(signals, now_local)
    message = build_single_signal_message(active_signal, now_utc=now_utc, now_local=now_local)
    send_telegram_message(message)


if __name__ == "__main__":
    main()