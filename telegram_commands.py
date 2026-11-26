import json
import os
import requests
from signal_engine import analyze, format_signal

OFFSET_FILE = "state/telegram_offset.json"

SYMBOL_ALIASES = {
    "زێڕ": "XAU/USD",
    "ئاڵتون": "XAU/USD",
    "gold": "XAU/USD",
    "xau": "XAU/USD",
    "xauusd": "XAU/USD",
    "زیو": "XAG/USD",
    "silver": "XAG/USD",
    "xag": "XAG/USD",
    "یۆرۆ": "EUR/USD",
    "eur": "EUR/USD",
    "پاوەند": "GBP/USD",
    "gbp": "GBP/USD",
    "بیتکۆین": "BTC/USDT",
    "btc": "BTC/USDT",
    "xrp": "XRP/USDT",
}


def _load_offset() -> int | None:
    if not os.path.exists(OFFSET_FILE):
        return None
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("offset")
    except Exception:
        return None


def _save_offset(offset: int) -> None:
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f)


def parse_kurdish_request(text: str) -> tuple[str | None, str]:
    clean = text.strip().lower()
    timeframe = "15m"
    if "5m" in clean or "٥ خولەک" in clean:
        timeframe = "5m"
    elif "1h" in clean or "کاتژمێر" in clean or "١ سەعات" in clean:
        timeframe = "1h"
    elif "15m" in clean or "١٥ خولەک" in clean:
        timeframe = "15m"

    for alias, symbol in SYMBOL_ALIASES.items():
        if alias in clean:
            return symbol, timeframe

    # ئەگەر جووتێکی وەک EUR/USD یان BTC/USDT نووسرابوو
    for token in clean.replace("،", " ").split():
        upper_tok = token.upper()
        if "/" in upper_tok and len(upper_tok) >= 5:
            return upper_tok, timeframe

    return None, timeframe


def handle_incoming_messages(allowed_chat_ids: list[str], fetch_df_fn, send_fn) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not allowed_chat_ids:
        return

    offset = _load_offset()
    params = {"timeout": 5}
    if offset is not None:
        params["offset"] = offset

    resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params, timeout=20)
    resp.raise_for_status()
    updates = resp.json().get("result", [])

    max_update_id = None
    allowed_set = set(str(c).strip() for c in allowed_chat_ids)

    for upd in updates:
        uid = upd.get("update_id")
        if isinstance(uid, int):
            max_update_id = uid if max_update_id is None else max(max_update_id, uid)

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        chat_id = str(msg.get("chat", {}).get("id", "")).strip()
        text = (msg.get("text") or "").strip()
        if not text or chat_id not in allowed_set:
            continue

        symbol, tf = parse_kurdish_request(text)
        if not symbol:
            send_fn(
                "🤖 بە کوردی بنووسە بۆ کام جووت و تایمفرێم سیگناڵت دەوێت؛ "
                "بۆ نموونە: «سیگناڵێکم بۆ زێڕ بنێرە لە 15m» یان «پشکنینی BTC بکە»."
            )
            continue

        try:
            df = fetch_df_fn(symbol, tf)
            min_score = int(os.environ.get("MIN_SIGNAL_SCORE", "3"))
            sig = analyze(df, symbol=symbol, timeframe=tf, min_score=min_score)
            reply = "📩 وەڵامی داواکارییەکەت:\n\n" + format_signal(sig)
        except Exception as e:
            reply = f"⚠️ نەتوانرا شیکاری بۆ {symbol} ({tf}) بکرێت: {e}"

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
            timeout=20,
        ).raise_for_status()

    if max_update_id is not None:
        _save_offset(max_update_id + 1)