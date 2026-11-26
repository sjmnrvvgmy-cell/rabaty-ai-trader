from datetime import datetime, timezone
import os
import requests
from scanner import scan_all
from signal_engine import format_signal


def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variable.")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    response.raise_for_status()


def main():
    results = scan_all()
    alerts = []
    errors = []
    scanned_pairs = []

    for s in results:
        side = s.get("side")
        symbol = s.get("symbol", "نەزانراو")
        tf = s.get("timeframe", "")

        side_ku = {
            "BUY": "کڕین (BUY)",
            "SELL": "فرۆشتن (SELL)",
            "HOLD": "چاوەڕوانی (HOLD)",
            "NONE": "بێ سیگناڵ",
            "ERROR": "هەڵەی داتا",
        }.get(str(side), str(side))

        scanned_pairs.append(f"• {symbol} ({tf}): {side_ku}")

        if side in ("BUY", "SELL"):
            alerts.append(format_signal(s))
        elif side == "ERROR":
            errors.append(f"• {symbol} {tf}: {str(s.get('error', ''))[:140]}")

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if alerts:
        message = (
            f"📊 ڕەباتی ئەی ئای ترەیدەر (RABATY AI TRADER) — سیگناڵی نوێ\n"
            f"🕒 کات: {now_utc}\n\n" + "\n\n".join(alerts)
        )
        send_telegram(message[:3900])
    elif errors:
        message = (
            f"⚠️ ڕەباتی ئەی ئای ترەیدەر — کێشەی سەرچاوەی داتا\n"
            f"🕒 کات: {now_utc}\n\n" + "\n".join(errors)
        )
        send_telegram(message[:3900])
    else:
        summary = "\n".join(scanned_pairs[:12]) if scanned_pairs else "هیچ جووتێک پشکنینی بۆ نەکرا."
        message = (
            f"🟢 ڕەباتی ئەی ئای ترەیدەر — چالاکە (هیچ هەلی کڕین/فرۆشتن نییە)\n"
            f"🕒 کات: {now_utc}\n\n"
            f"{summary}"
        )
        send_telegram(message[:3900])


if __name__ == "__main__":
    main()
