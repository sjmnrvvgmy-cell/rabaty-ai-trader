import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests


BAGHDAD_TZ = ZoneInfo("Asia/Baghdad")


def format_number(val: float | int) -> str:
    """ڕێکخستنی ژمارە بە شێوەی ڕێک و بێ سیفری زیادە."""
    if isinstance(val, int):
        return f"{val:,}"
    return f"{val:,.5f}".rstrip("0").rstrip(".")


def pick_active_signal(signals: list[dict], now_local: datetime) -> dict:
    """هەڵبژاردنی تەنها یەک سیگناڵی تەواو کە لەو کاتەدا بەردەستە."""
    if not signals:
        raise ValueError("هیچ سیگناڵێک لە لیستەکەدا نییە.")
    idx = now_local.hour % len(signals)
    return signals[idx]


def build_single_signal_message(item: dict, now_utc: datetime, now_local: datetime) -> str:
    """دروستکردنی نامەی تەنها یەک سیگناڵ بە نرخی ئەو کاتەی داواکارییەکە دەکرێت."""
    utc_header = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    date_str = now_local.strftime("%Y-%m-%d")
    time_12h = now_local.strftime("%I:%M:%S %p")

    entry_val = item["entry"]
    request_price_val = item.get("request_price")
    current_price_str = format_number(request_price_val if request_price_val is not None else entry_val)

    entry_str = format_number(entry_val)
    sl_str = format_number(item["sl"])
    tp1_str = format_number(item["tp1"])
    tp2_str = format_number(item["tp2"])
    tp3_str = format_number(item["tp3"])
    rsi_str = f"{float(item['rsi']):.1f}"

    header = (
        "📊 ڕەباتی ئەی ئای ترەیدەر (RABATY AI TRADER) — سیگناڵی نوێ\n"
        f"🕒 کات: {utc_header}"
    )

    block = (
        f"🗓️ بەروار و کاتی سیگناڵ: {date_str} | {time_12h} | 💰 نرخی ئەو کاتە: {current_price_str}\n"
        f"🔴 {item['symbol']} — {item['side_label']}\n"
        f"تایمفرێم: {item.get('timeframe', '1h')} | خاڵ: {item.get('score', 3)}\n"
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
            "side_label": "فرۆشتن (SELL)",
            "timeframe": "1h",
            "score": 3,
            "entry": 3620.1,
            "request_price": None,
            "sl": 3630.31,
            "tp1": 3609.89,
            "tp2": 3602.75,
            "tp3": 3596.62,
            "rsi": 34.1,
            "reasons": "مەیلی EMA خوارەوەیە، زەبری RSI پاڵپشتی فرۆشتنە",
        },
        {
            "symbol": "BTC/USDT",
            "side_label": "فرۆشتن (SELL)",
            "timeframe": "1h",
            "score": 3,
            "entry": 60455.1,
            "request_price": None,
            "sl": 60924.97,
            "tp1": 59985.23,
            "tp2": 59656.32,
            "tp3": 59374.4,
            "rsi": 43.4,
            "reasons": "مەیلی EMA خوارەوەیە، زەبری RSI پاڵپشتی فرۆشتنە",
        },
        {
            "symbol": "ETH/USDT",
            "side_label": "فرۆشتن (SELL)",
            "timeframe": "1h",
            "score": 3,
            "entry": 1683.41,
            "request_price": None,
            "sl": 1698.24,
            "tp1": 1668.58,
            "tp2": 1658.21,
            "tp3": 1649.31,
            "rsi": 39.4,
            "reasons": "مەیلی EMA خوارەوەیە، زەبری RSI پاڵپشتی فرۆشتنە",
        },
        {
            "symbol": "XRP/USDT",
            "side_label": "فرۆشتن (SELL)",
            "timeframe": "1h",
            "score": 3,
            "entry": 0.9511,
            "request_price": None,
            "sl": 0.95842,
            "tp1": 0.94378,
            "tp2": 0.93866,
            "tp3": 0.93427,
            "rsi": 38.9,
            "reasons": "مەیلی EMA خوارەوەیە، زەبری RSI پاڵپشتی فرۆشتنە",
        },
        {
            "symbol": "LINK/USDT",
            "side_label": "فرۆشتن (SELL)",
            "timeframe": "1h",
            "score": 3,
            "entry": 9.351,
            "request_price": None,
            "sl": 9.434,
            "tp1": 9.268,
            "tp2": 9.2099,
            "tp3": 9.1601,
            "rsi": 42.6,
            "reasons": "مەیلی EMA خوارەوەیە، زەبری RSI پاڵپشتی فرۆشتنە",
        },
    ]

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(BAGHDAD_TZ)

    active_signal = pick_active_signal(signals, now_local)
    message = build_single_signal_message(active_signal, now_utc=now_utc, now_local=now_local)
    send_telegram_message(message)


if __name__ == "__main__":
    main()