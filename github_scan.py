import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests


BAGHDAD_TZ = ZoneInfo("Asia/Baghdad")


def format_exact_price(val: float | int) -> str:
    """نیشاندانی نرخ بە 5 خاڵی دەیی ڕێک وەک سیگناڵە دەقیقەکەی سەرەوە."""
    return f"{float(val):.5f}"


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
    current_price_str = format_exact_price(
        request_price_val if request_price_val is not None else entry_val
    )

    entry_str = format_exact_price(entry_val)
    sl_str = format_exact_price(item["sl"])
    tp1_str = format_exact_price(item["tp1"])
    tp2_str = format_exact_price(item["tp2"])
    tp3_str = format_exact_price(item["tp3"])
    rsi_str = f"{float(item['rsi']):.1f}"

    side_emoji = item.get("emoji", "🟢")
    timeframe = item.get("timeframe", "1h")
    score = item.get("score", 4)

    header = (
        "📊 ڕەباتی ئەی ئای ترەیدەر (RABATY AI TRADER) — سیگناڵی نوێ\n"
        f"🕒 کات: {utc_header}"
    )

    block = (
        f"🗓️ بەروار و کاتی سیگناڵ: {date_str} | {time_12h} | 💰 نرخی ئەو کاتە: {current_price_str}\n"
        f"{side_emoji} {item['symbol']} — {item['side_label']}\n"
        f"تایمفرێم: {timeframe} | خاڵ: {score}\n"
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
            "request_price": None,
            "sl": 3645.86786,
            "tp1": 3689.13214,
            "tp2": 3706.43786,
            "tp3": 3721.58036,
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
            "request_price": None,
            "sl": 159.34848,
            "tp1": 159.49951,
            "tp2": 159.55992,
            "tp3": 159.61278,
            "rsi": 68.5,
            "reasons": "مەیلی EMA سەرەوەیە، زەبری RSI پاڵپشتی کڕینە، شکاندنی بەرزایی پێشوو (BOS سەرەوە)",
        },
        {
            "symbol": "USD/JPY",
            "side_label": "کڕین (BUY)",
            "emoji": "🟢",
            "timeframe": "1h",
            "score": 4,
            "entry": 159.42400,
            "request_price": None,
            "sl": 159.29017,
            "tp1": 159.55782,
            "tp2": 159.66488,
            "tp3": 159.75856,
            "rsi": 62.5,
            "reasons": "مەیلی EMA سەرەوەیە، زەبری RSI پاڵپشتی کڕینە، شکاندنی بەرزایی پێشوو (BOS سەرەوە)",
        },
        {
            "symbol": "USD/CHF",
            "side_label": "کڕین (BUY)",
            "emoji": "🟢",
            "timeframe": "1h",
            "score": 4,
            "entry": 0.83608,
            "request_price": None,
            "sl": 0.83473,
            "tp1": 0.83743,
            "tp2": 0.83851,
            "tp3": 0.83946,
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