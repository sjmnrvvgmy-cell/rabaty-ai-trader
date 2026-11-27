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
    "ئیتەر": "ETH/USDT",
    "eth": "ETH/USDT",
    "سۆلانا": "SOL/USDT",
    "sol": "SOL/USDT",
    "xrp": "XRP/USDT",
}


def _normalize_text(text: str) -> str:
    t = text.strip().lower()
    for ch in "«»\"'“”‘’؟،.!:":
        t = t.replace(ch, " ")
    replacements = {
        "ێ": "ی",
        "ئ": "ا",
        "إ": "ا",
        "أ": "ا",
        "ة": "ه",
        "ه": "ە",
        "ڕ": "ر",
        "ۆ": "و",
        "وو": "و",
    }
    for old, new in replacements.items():
        t = t.replace(old, new)
    return " ".join(t.split())


def _load_offset() -> int | None:
    if not os.path.exists(OFFSET_FILE):
        return None
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            val = data.get("offset")
            return int(val) if val is not None else None
    except Exception:
        return None


def _save_offset(offset: int) -> None:
    parent = os.path.dirname(OFFSET_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f)


def parse_kurdish_request(text: str) -> tuple[str | None, str]:
    clean = _normalize_text(text)

    timeframe = "15m"
    if "5m" in clean or "5 خولەک" in clean or "5 خولەك" in clean:
        timeframe = "5m"
    elif "1h" in clean or "کاتژمێر" in clean or "سەعات" in clean or "1 سەعات" in clean:
        timeframe = "1h"
    elif "15m" in clean or "15 خولەک" in clean or "15 خولەك" in clean:
        timeframe = "15m"

    if any(k in clean for k in ["زیر", "زیڕ", "زەر", "زەڕ", "ئالتون", "ئاڵتون", "gold", "xau"]):
        return "XAU/USD", timeframe

    for alias, symbol in SYMBOL_ALIASES.items():
        norm_alias = _normalize_text(alias)
        if norm_alias and norm_alias in clean:
            return symbol, timeframe

    for token in clean.split():
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

    resp = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params=params,
        timeout=20,
    )
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
                "بۆ نموونە: «زێڕ 15m» یان «پشکنینی BTC بکە لە 15m»."
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