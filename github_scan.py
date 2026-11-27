import os
import requests
from dotenv import load_dotenv
from market_data import get_market_data
from reversal_monitor import (
    check_reversals,
    load_active_signals,
    record_new_signal,
    save_active_signals,
)
from scanner import scan_all
from signal_engine import format_signal
from telegram_commands import handle_incoming_messages

load_dotenv()


def get_allowed_chat_ids() -> list[str]:
    raw = os.environ.get("TELEGRAM_CHAT_IDS", "").strip()
    if raw:
        return [c.strip() for c in raw.split(",") if c.strip()]

    single = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return [single] if single else []


def send_to_chats(chat_ids: list[str], text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not chat_ids:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_IDS / TELEGRAM_CHAT_ID.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in chat_ids:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
        resp.raise_for_status()


def fetch_ohlcv_for_command(symbol: str, timeframe: str):
    return get_market_data(symbol, timeframe)


def main() -> None:
    chat_ids = get_allowed_chat_ids()
    if not chat_ids:
        raise ValueError("هیچ TELEGRAM_CHAT_ID یان TELEGRAM_CHAT_IDS دیاری نەکراوە.")

    # ١. خوێندنەوەی داواکارییە کوردییەکان و وەڵامدانەوەیان
    handle_incoming_messages(
        allowed_chat_ids=chat_ids,
        fetch_df_fn=fetch_ohlcv_for_command,
        send_fn=lambda msg: send_to_chats(chat_ids, msg),
    )

    # ٢. پشکنینی خۆکاری بازاڕ، پێچەوانەبوونەوە و ناردنی سیگناڵەکان
    results = scan_all()
    signals = load_active_signals()

    reversal_alerts = check_reversals(results, signals)
    for alert in reversal_alerts:
        send_to_chats(chat_ids, alert)

    for item in results:
        if item.get("side") in ("BUY", "SELL"):
            msg = (
                "📡 ڕەباتی ئەی ئای ترەیدەر (RABATY AI TRADER) — سیگناڵی نوێ\n\n"
                + format_signal(item)
            )
            send_to_chats(chat_ids, msg)
            record_new_signal(signals, item)

    save_active_signals(signals)


if __name__ == "__main__":
    main()