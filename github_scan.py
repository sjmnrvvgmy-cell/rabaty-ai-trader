import json
import os
from datetime import datetime, timedelta, timezone
import requests
from market_data import get_market_data
from signal_engine import analyze, format_signal

BAGHDAD_TZ = timezone(timedelta(hours=3))
STATE_FILE = "state/last_signals.json"

# لیستی ئەو جووتانەی دەتەوێت هەر 5 خولەک جارێک پشکنینیان بۆ بکرێت
DEFAULT_SYMBOLS = [
    "PAXG/USDT",  # زێڕ لە Binance/OKX
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
]

# ئەو تایمفرێمانەی دەتەوێت پشکنینیان تێدا بکرێت
DEFAULT_TIMEFRAMES = ["5m", "15m"]


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


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids_raw = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_ids_raw:
        raise ValueError("TELEGRAM_BOT_TOKEN یان TELEGRAM_CHAT_ID دیاری نەکراوە.")

    for chat_id in [c.strip() for c in chat_ids_raw.split(",") if c.strip()]:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
        resp.raise_for_status()


def _current_datetime_str() -> str:
    now_local = datetime.now(BAGHDAD_TZ)
    return now_local.strftime("%Y-%m-%d | %I:%M:%S %p")


def scan_all() -> None:
    symbols_env = os.environ.get("SCAN_SYMBOLS", "").strip()
    symbols = [s.strip() for s in symbols_env.split(",") if s.strip()] if symbols_env else DEFAULT_SYMBOLS

    tfs_env = os.environ.get("SCAN_TIMEFRAMES", "").strip()
    timeframes = [t.strip() for t in tfs_env.split(",") if t.strip()] if tfs_env else DEFAULT_TIMEFRAMES

    min_score = int(os.environ.get("MIN_SIGNAL_SCORE", "3"))
    state = _load_state()
    state_changed = False

    for symbol in symbols:
        for tf in timeframes:
            try:
                df = get_market_data(symbol, tf)
                sig = analyze(df, symbol=symbol, timeframe=tf, min_score=min_score)
                action = str(sig.get("action", "WAIT")).upper()

                if action not in ("BUY", "SELL"):
                    print(f"[{symbol} | {tf}] WAIT")
                    continue

                candle_id = str(sig.get("candle_time") or df.index[-1])
                state_key = f"{symbol}_{tf}"
                last_sent = state.get(state_key)

                # ڕێگری لە ناردنەوەی هەمان سیگناڵ لەسەر هەمان مۆم
                if last_sent == f"{action}_{candle_id}":
                    print(f"[{symbol} | {tf}] Already sent for candle {candle_id}")
                    continue

                now_str = _current_datetime_str()
                msg = (
                    f"📅 بەروار و کات: {now_str}\n"
                    f"📊 جووت: {symbol} ({tf})\n\n"
                    + format_signal(sig)
                )
                send_telegram(msg)
                state[state_key] = f"{action}_{candle_id}"
                state_changed = True
                print(f"[{symbol} | {tf}] Sent {action} signal at {now_str}")

            except Exception as e:
                print(f"[{symbol} | {tf}] Error: {e}")

    if state_changed:
        _save_state(state)


if __name__ == "__main__":
    scan_all()