import json
import os
from datetime import datetime, timedelta, timezone
import requests
from market_data import get_market_data
from signal_engine import analyze, format_signal

BAGHDAD_TZ = timezone(timedelta(hours=3))
STATE_FILE = "state/last_signals.json"
TELEGRAM_MAX_LEN = 3900

DEFAULT_SYMBOLS = [
    "XAUT/USDT",
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "LINK/USDT",
]

DEFAULT_TIMEFRAMES = ["15m", "1h"]


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    parent = os.path.dirname(STATE_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _split_message(header: str, blocks: list[str], max_len: int = TELEGRAM_MAX_LEN) -> list[str]:
    messages: list[str] = []
    current = header.rstrip() + "\n"

    for block in blocks:
        addition = ("\n" + block) if current.endswith("\n") else ("\n\n" + block)
        if len(current) + len(addition) > max_len and current.strip() != header.strip():
            messages.append(current.strip())
            current = header.rstrip() + "\n\n" + block
        else:
            current += addition

    if current.strip():
        messages.append(current.strip())
    return messages


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids_raw = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_ids_raw:
        raise ValueError("TELEGRAM_BOT_TOKEN یان TELEGRAM_CHAT_ID دیاری نەکراوە.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in [c.strip() for c in chat_ids_raw.split(",") if c.strip()]:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        resp.raise_for_status()


def _format_signal_timestamps() -> tuple[str, str]:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(BAGHDAD_TZ)
    utc_str = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    local_str = now_local.strftime("%Y-%m-%d | %I:%M:%S %p")
    return utc_str, local_str


def _parse_list_env(var_name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(var_name, "").strip()
    if not raw:
        return list(default)
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items if items else list(default)


def scan_all() -> None:
    symbols = _parse_list_env("SCAN_SYMBOLS", DEFAULT_SYMBOLS)
    timeframes = _parse_list_env("SCAN_TIMEFRAMES", DEFAULT_TIMEFRAMES)

    try:
        min_score = int(os.environ.get("MIN_SIGNAL_SCORE", "3").strip())
    except ValueError:
        min_score = 3

    state = _load_state()
    pending_updates: dict[str, str] = {}
    new_blocks: list[str] = []

    utc_header, local_now_str = _format_signal_timestamps()

    for symbol in symbols:
        for tf in timeframes:
            try:
                df = get_market_data(symbol, tf)
                if df is None or df.empty:
                    print(f"[{symbol} | {tf}] Empty market data")
                    continue

                sig = analyze(df, symbol=symbol, timeframe=tf, min_score=min_score)
                if not isinstance(sig, dict):
                    print(f"[{symbol} | {tf}] Invalid analysis output")
                    continue

                action = str(sig.get("action", "WAIT")).upper().strip()
                if action not in ("BUY", "SELL"):
                    print(f"[{symbol} | {tf}] WAIT")
                    continue

                candle_id = str(sig.get("candle_time") or df.index[-1])
                state_key = f"{symbol}_{tf}"
                marker = f"{action}_{candle_id}"

                if state.get(state_key) == marker:
                    print(f"[{symbol} | {tf}] Already sent for candle {candle_id}")
                    continue

                formatted = format_signal(sig)
                if not formatted or not str(formatted).strip():
                    print(f"[{symbol} | {tf}] Empty formatted signal")
                    continue

                block = (
                    f"🗓️ بەروار و کاتی سیگناڵ: {local_now_str}\n"
                    f"{formatted.strip()}"
                )
                new_blocks.append(block)
                pending_updates[state_key] = marker
                print(f"[{symbol} | {tf}] Queued {action} signal at {local_now_str}")

            except Exception as e:
                print(f"[{symbol} | {tf}] Error: {e}")

    if new_blocks:
        header = (
            "📊 ڕەباتی ئەی ئای ترەیدەر (RABATY AI TRADER) — سیگناڵی نوێ\n"
            f"🕒 کات: {utc_header}"
        )
        chunks = _split_message(header, new_blocks)
        for chunk in chunks:
            send_telegram(chunk)

        state.update(pending_updates)
        _save_state(state)
        print(f"Sent {len(new_blocks)} signal(s) in {len(chunks)} message(s).")
    else:
        print("No new signals to send.")


if __name__ == "__main__":
    scan_all()