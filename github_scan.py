import os
from datetime import datetime, timezone
import requests


def fetch_okx_closed_close(symbol: str, bar: str = "1H") -> float | None:
    """هێنانی نرخی داخرانی کۆتا شمعەی داخراو لە OKX."""
    inst_id = symbol.strip().upper().replace("/", "-")
    url = "https://www.okx.com/api/v5/market/candles"
    try:
        resp = requests.get(
            url,
            params={"instId": inst_id, "bar": bar, "limit": "2"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        candles = data.get("data") or []
        if len(candles) >= 2 and len(candles[1]) >= 5:
            return float(candles[1][4])
        if candles and len(candles[0]) >= 5:
            return float(candles[0][4])
        return None
    except Exception:
        return None


def fetch_binance_closed_close(symbol: str, interval: str = "1h") -> float | None:
    """هێنانی نرخی داخرانی کۆتا شمعەی داخراو لە Binance."""
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


def get_accurate_chart_price(symbol: str, fallback_entry: float | None = None) -> float | None:
    """هێنانی نرخی شمعەی داخراو سەرەتا لە OKX و ئەگەر نەبوو لە Binance."""
    price = fetch_okx_closed_close(symbol, bar="1H")
    if price is not None:
        return price

    price = fetch_binance_closed_close(symbol, interval="1h")
    if price is not None:
        return price

    return fallback_entry


def format_price(price: float | None) -> str:
    """ڕێکخستنی نیشاندانی نرخ بە شێوەی ڕوون و گونجاو."""
    if price is None:
        return "N/A"
    if price < 1:
        return f"{price:.5f}".rstrip("0").rstrip(".")
    if price < 100:
        return f"{price:.4f}".rstrip("0").rstrip(".")
    return f"{price:,.2f}".rstrip("0").rstrip(".")


def build_signal_block(
    symbol: str,
    side_label: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    tp3: float,
    rsi: float,
    reasons: str,
    date_str: str,
    time_12h: str,
    live_price: float | None,
) -> str:
    """دروستکردنی بلۆکی هەر سیگناڵێک بە نرخی ئەو کاتە لە تەنیشت کاتەکەوە."""
    live_price_str = format_price(live_price)
    return (
        f"🗓️ بەروار و کاتی سیگناڵ: {date_str} | {time_12h} | 💰 نرخی ئەو کاتە: {live_price_str}\n"
        f"🔴 {symbol} — {side_label}\n"
        f"تایمفرێم: 1h | خاڵ: 3\n"
        f"نرخی چوونەژوورەوە: {format_price(entry)}\n"
        f"ستۆپ لۆس (SL): {format_price(sl)}\n"
        f"ئامانجی 1 (TP1): {format_price(tp1)}\n"
        f"ئامانجی 2 (TP2): {format_price(tp2)}\n"
        f"ئامانجی 3 (TP3): {format_price(tp3)}\n"
        f"RSI: {rsi:.1f}\n"
        f"هۆکارەکان: {reasons}\n"
        f"تێبینی: ئەمە سیگناڵی تەکنیکییە؛ پێش چوونەناوەوە سپرێد و مەترسی بپشکنە."
    )


def build_full_message(signals: list[dict]) -> str:
    """کۆکردنەوەی هەموو سیگناڵەکان لە یەک نامەی ڕێکخراودا."""
    now_utc = datetime.now(timezone.utc)
    utc_header = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    date_str = now_utc.strftime("%Y-%m-%d")
    time_12h = now_utc.strftime("%I:%M:%S %p")

    header = (
        "📊 ڕەباتی ئەی ئای ترەیدەر (RABATY AI TRADER) — سیگناڵی نوێ\n"
        f"🕒 کات: {utc_header}"
    )

    blocks = [header]
    for item in signals:
        live_price = get_accurate_chart_price(item["symbol"], fallback_entry=item.get("entry"))
        block = build_signal_block(
            symbol=item["symbol"],
            side_label=item["side_label"],
            entry=item["entry"],
            sl=item["sl"],
            tp1=item["tp1"],
            tp2=item["tp2"],
            tp3=item["tp3"],
            rsi=item["rsi"],
            reasons=item["reasons"],
            date_str=date_str,
            time_12h=time_12h,
            live_price=live_price,
        )
        blocks.append(block)

    return "\n\n".join(blocks)


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
    sample_signals = [
        {
            "symbol": "XAUT/USDT",
            "side_label": "فرۆشتن (SELL)",
            "entry": 3620.10,
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
            "entry": 60455.10,
            "sl": 60924.97,
            "tp1": 59985.23,
            "tp2": 59656.32,
            "tp3": 59374.40,
            "rsi": 43.4,
            "reasons": "مەیلی EMA خوارەوەیە، زەبری RSI پاڵپشتی فرۆشتنە",
        },
        {
            "symbol": "ETH/USDT",
            "side_label": "فرۆشتن (SELL)",
            "entry": 1683.41,
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
            "entry": 0.95110,
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
            "entry": 9.35100,
            "sl": 9.43400,
            "tp1": 9.26800,
            "tp2": 9.20991,
            "tp3": 9.16011,
            "rsi": 42.6,
            "reasons": "مەیلی EMA خوارەوەیە، زەبری RSI پاڵپشتی فرۆشتنە",
        },
    ]

    message = build_full_message(sample_signals)
    send_telegram_message(message)


if __name__ == "__main__":
    main()