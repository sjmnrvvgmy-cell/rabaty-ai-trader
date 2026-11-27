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


def parse_kurdish_request(text: str) -> tuple[str | None, str]:
    clean = _normalize_text(text)

    timeframe = "15m"
    if "5m" in clean or "5 خولەک" in clean or "5 خولەك" in clean:
        timeframe = "5m"
    elif "1h" in clean or "کاتژمێر" in clean or "سەعات" in clean or "1 سەعات" in clean:
        timeframe = "1h"
    elif "15m" in clean or "15 خولەک" in clean or "15 خولەك" in clean:
        timeframe = "15m"

    # پشکنینی زێڕ بە هەموو شێوازە باوەکانی نووسین
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