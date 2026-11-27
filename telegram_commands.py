import json
import os
from datetime import datetime, timedelta, timezone
import requests
from signal_engine import analyze, format_signal

OFFSET_FILE = "state/telegram_offset.json"
BAGHDAD_TZ = timezone(timedelta(hours=3))

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
    "دۆلار یەن": "USD/JPY",
    "usdjpy": "USD/JPY",
    "بیتکۆین": "BTC/USDT",
    "btc": "BTC/USDT",
    "ئیتەر": "ETH/USDT",
    "eth": "ETH/USDT",
    "سۆلانا": "SOL/USDT",
    "sol": "SOL/USDT",
    "xrp": "XRP/USDT",
    "لینک": "LINK/USDT",
    "link": "LINK/USDT",
}

TIMEFRAME_PATTERNS: list[tuple[str, list[str]]] = [
    ("1m", ["1m", "١ خولەک", "1 خولەک", "١ خولەك", "1 خولەك", "١ دەقە", "1 دەقە"]),
    ("5m", ["5m", "٥ خولەک", "5 خولەک", "٥ خولەك", "5 خولەك", "٥ دەقە", "5 دەقە"]),
    ("15m", ["15m", "١٥ خولەک", "15 خولەک", "١٥ خولەك", "15 خولەك", "١٥ دەقە", "15 دەقە"]),
    ("30m", ["30m", "٣٠ خولەک", "30 خولەک", "٣٠ خولەك", "30 خولەك", "٣٠ دەقە", "30 دەقە"]),
    ("4h", ["4h", "٤ کاتژمێر", "4 کاتژمێر", "٤ سەعات", "4 سەعات"]),
    ("1h", ["1h", "١ کاتژمێر", "1 کاتژمێر", "١ سەعات", "1 سەعات", "کاتژمێر", "سەعات"]),
    ("1d", ["1d", "ڕۆژانە", "رۆژانە", "١ ڕۆژ", "1 ڕۆژ", "١ رۆژ", "1 رۆژ"]),
    ("1w", ["1w", "هەفتانە", "١ هەفتە", "1 هەفتە"]),
]


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
    for tf_code, patterns in TIMEFRAME_PATTERNS:
        if any(_normalize_text(p) in clean for p in patterns):
            timeframe = tf_code
            break

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


def _format_request_timestamp(msg_unix_ts: int | float | None) -> str:
    if isinstance(msg_unix_ts, (int, float)) and msg_unix_ts > 0:
        req_local = datetime.fromtimestamp(msg_unix_ts, tz=BAGHDAD_TZ)
        req_utc = datetime.fromtimestamp(msg_unix_ts, tz=timezone.utc)
        return (
            f"{req_local.strftime('%Y-%m-%d %I:%M:%S %p')} (کاتی داواکاری - کوردستان/بەغدا) "
            f"| {req_utc.strftime('%H:%M:%S UTC')}"
        )
    now_local = datetime.now(BAGHDAD_TZ)
    now_utc = datetime.now(timezone.utc)
    return (
        f"{now_local.strftime('%Y-%m-%d %I:%M:%S %p')} (کاتی شیکاری - کوردستان/بەغدا) "
        f"| {now_utc.strftime('%H:%M:%S UTC')}"
    )


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
    skip_old = os.environ.get("SKIP_OLD_UPDATES", "").strip() in ("1", "true", "yes")
    now_ts = datetime.now(timezone.utc).timestamp()

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

        msg_date = msg.get("date")
        if skip_old and isinstance(msg_date, (int, float)) and (now_ts - msg_date) > 600:
            continue

        symbol, tf = parse_kurdish_request(text)
        req_time_str = _format_request_timestamp(msg_date)
        fetch_local = datetime.now(BAGHDAD_TZ).strftime("%I:%M:%S %p")

        if not symbol:
            no_sym_text = (
                f"🕒 {req_time_str}\n"
                "🤖 بە کوردی بنووسە بۆ کام جووت و تایمفرێم سیگناڵت دەوێت؛ "
                "بۆ نموونە: «زێڕ 1 دەقە»، «زێڕ 5 دەقە»، «زێڕ 1h»، یان «xrp 15m»."
            )
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": no_sym_text},
                timeout=20,
            ).raise_for_status()
            continue

        try:
            df = fetch_df_fn(symbol, tf)
            min_score = int(os.environ.get("MIN_SIGNAL_SCORE", "3"))
            sig = analyze(df, symbol=symbol, timeframe=tf, min_score=min_score)
            live_price = sig.get("price")
            price_str = f"{live_price:.5f}" if isinstance(live_price, (int, float)) else str(live_price)

            reply = (
                f"📩 سیگناڵی داواکراو تەنها بۆ ({symbol} | {tf})\n"
                f"🕒 {req_time_str}\n"
                f"⏱️ کاتی وەرگرتنی نرخ: {fetch_local}\n"
                f"💲 نرخی ئەو ساتە: {price_str}\n\n"
                + format_signal(sig)
            )
        except Exception as e:
            reply = (
                f"⚠️ نەتوانرا شیکاری بۆ {symbol} ({tf}) بکرێت\n"
                f"🕒 {req_time_str}\n"
                f"هۆکار: {e}"
            )

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
            timeout=20,
        ).raise_for_status()

    if max_update_id is not None:
        _save_offset(max_update_id + 1)