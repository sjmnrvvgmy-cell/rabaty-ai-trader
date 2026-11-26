import os
import requests
from scanner import scan_all
from signal_engine import format_signal

def send_telegram(text: str):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    response.raise_for_status()

def main():
    results = scan_all()
    alerts = []
    errors = []
    for s in results:
        if s["side"] in ("BUY", "SELL"):
            alerts.append(format_signal(s))
        elif s["side"] == "ERROR":
            errors.append(f"{s['symbol']} {s['timeframe']}: {s['error'][:140]}")
    if alerts:
        message = "📊 RABATY AI TRADER — NEW SCAN\n\n" + "\n\n".join(alerts)
        # Telegram message limit is 4096 characters.
        send_telegram(message[:3900])
    elif errors:
        send_telegram("⚠️ RABATY AI TRADER — data source issue\n\n" + "\n".join(errors)[:3500])
    else:
        print("No qualified BUY/SELL setup. No Telegram alert sent.")

if __name__ == "__main__":
    main()
