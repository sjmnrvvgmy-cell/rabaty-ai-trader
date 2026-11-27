import os
from datetime import datetime, timezone
import requests


def fetch_okx_price(inst_id: str = "BTC-USDT") -> float | None:
    """هێنانی نرخی ئەو کاتەی دراوەکە لە OKX."""
    url = "https://www.okx.com/api/v5/market/ticker"
    try:
        resp = requests.get(url, params={"instId": inst_id}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") or []
        if not items:
            return None
        return float(items[0]["last"])
    except Exception as exc:
        print(f"Debug [{inst_id}] OKX error: {exc}")
        return None


def fetch_binance_price(symbol: str = "BTCUSDT") -> float | None:
    """هێنانی نرخی ئەو کاتەی دراوەکە لە Binance."""
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        resp = requests.get(url, params={"symbol": symbol}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data["price"])
    except Exception as exc:
        print(f"Debug [{symbol}] Binance error: {exc}")
        return None


def fetch_metal_price_usd(metal_code: str) -> float | None:
    """هێنانی نرخی زێڕ (XAU) یان زیو (XAG) بە دۆلار بۆ هەر ئۆنسێک لە چەند سەرچاوەیەکەوە."""
    code = metal_code.upper().strip()
    if code in ("XAU", "GOLD"):
        target = "xau"
    elif code in ("XAG", "SILVER"):
        target = "xag"
    else:
        return None

    # سەرچاوەی یەکەم: open.er-api.com
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        resp.raise_for_status()
        rate = (resp.json().get("rates") or {}).get(target.upper())
        if rate is not None and float(rate) > 0:
            return 1.0 / float(rate)
    except Exception as exc:
        print(f"Debug [{target.upper()}] er-api error: {exc}")

    # سەرچاوەی دووەم: fawazahmed0 currency-api (USD -> XAU/XAG)
    urls = [
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
        "https://latest.currency-api.pages.dev/v1/currencies/usd.json",
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            usd_map = (resp.json().get("usd") or {})
            rate = usd_map.get(target)
            if rate is not None and float(rate) > 0:
                return 1.0 / float(rate)
        except Exception as exc:
            print(f"Debug [{target.upper()}] fallback error ({url}): {exc}")

    return None


def get_live_price(symbol: str = "BTC-USDT") -> float | None:
    """هێنانی نرخی زێڕ، زیو، یان دراوە کریپتۆکان بەپێی هێماکە."""
    clean = symbol.strip().upper()
    clean_no_dash = clean.replace("-", "").replace("/", "")

    if clean in ("XAU", "XAU-USD", "XAUUSD", "GOLD") or clean_no_dash in ("XAUUSD", "GOLD"):
        return fetch_metal_price_usd("XAU")

    if clean in ("XAG", "XAG-USD", "XAGUSD", "SILVER") or clean_no_dash in ("XAGUSD", "SILVER"):
        return fetch_metal_price_usd("XAG")

    okx_price = fetch_okx_price(clean)
    if okx_price is not None:
        return okx_price

    return fetch_binance_price(clean_no_dash)


def format_time_and_price(scan_time: str | None, price: float | int | str | None) -> tuple[str, str]:
    """ڕێکخستنی نرخ و دێڕی کات + نرخ بە شێوازی سەلامەت."""
    try:
        price_val = float(price) if price is not None and str(price).strip() != "" else None
    except (ValueError, TypeError):
        price_val = None

    price_str = f"{price_val:,.4f}".rstrip("0").rstrip(".") if price_val is not None else "N/A"
    time_str = str(scan_time).strip() if scan_time is not None and str(scan_time).strip() != "" else "N/A"
    time_and_price = f"🕒 {time_str} | 💰 نرخ: {price_str}"
    return price_str, time_and_price


def build_watchlist_message(symbols: list[str], signal_text: str, scan_time: str) -> str:
    """دروستکردنی نامەی پشکنین بۆ لیستێک لە دراوەکان، زێڕ، و زیو."""
    lines = [
        f"⚡ سیگناڵ: {signal_text}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for sym in symbols:
        clean_sym = sym.strip().upper()
        if not clean_sym:
            continue
        price = get_live_price(clean_sym)
        _, time_and_price = format_time_and_price(scan_time, price)
        lines.append(f"📌 {clean_sym}: {time_and_price}")
    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    """ناردنی نامە بۆ تێلێگرام ئەگەر TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID دانرابن."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        print("تێبینی: TELEGRAM_BOT_TOKEN یان TELEGRAM_CHAT_ID دیاری نەکراوە؛ نامەکە لە کۆنسۆڵ پیشان دەدرێت:")
        print(text)
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def run_scan(
    symbols: list[str] | None = None,
    signal_text: str = "پشکنینی خۆکار (5m)",
) -> None:
    """ڕاکێشانی پشکنین بۆ لیستەی دراوەکان و زێڕ و زیو و ناردنی ئەنجام."""
    target_symbols = symbols or ["BTC-USDT", "ETH-USDT", "XAU", "XAG"]
    scan_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = build_watchlist_message(
        symbols=target_symbols,
        signal_text=signal_text,
        scan_time=scan_time,
    )
    send_telegram_message(message)


if __name__ == "__main__":
    raw_symbols = os.getenv("SCAN_SYMBOLS", "BTC-USDT,ETH-USDT,XAU,XAG")
    parsed_symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
    target_signal = os.getenv("SCAN_SIGNAL", "پشکنینی خۆکار (5m)").strip() or "پشکنینی خۆکار (5m)"
    run_scan(symbols=parsed_symbols, signal_text=target_signal)