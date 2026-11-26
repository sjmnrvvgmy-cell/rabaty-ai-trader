import json
import os
from datetime import datetime, timezone

STATE_FILE = os.environ.get("SIGNAL_STATE_FILE", "state/active_signals.json")


def load_active_signals() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_active_signals(signals: dict) -> None:
    parent = os.path.dirname(STATE_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)


def record_new_signal(signals: dict, sig: dict) -> None:
    key = f"{sig['symbol']}|{sig['timeframe']}"
    signals[key] = {
        "symbol": sig["symbol"],
        "timeframe": sig["timeframe"],
        "side": sig["side"],
        "entry": sig["price"],
        "sl": sig.get("stop_loss"),
        "tps": sig.get("take_profits", []),
        "score": sig.get("score"),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def check_reversals(results: list[dict], signals: dict) -> list[str]:
    """
    پشکنینی پێچەوانەبوونەوەی سیگناڵە چالاکەکان:
    1) ئەگەر سیگناڵی پێشوو BUY بوو و ئێستا SELL هات (یان بە پێچەوانەوە) -> پێچەوانەبوونەوەی تەواو.
    2) ئەگەر سیگناڵی پێشوو BUY بوو و نرخ بە ڕوونی کەوتە ژێر ئاستی SL یان دۆخی SELL بەهێز بوو -> ئاگاداری داخستن/پاراستن.
    """
    alerts = []

    for item in results:
        side = item.get("side")
        symbol = item.get("symbol")
        tf = item.get("timeframe")
        if not symbol or not tf:
            continue

        key = f"{symbol}|{tf}"
        prev = signals.get(key)
        if not prev:
            continue

        prev_side = prev.get("side")
        price = item.get("price")

        # حاڵەتی یەکەم: گۆڕانی ئاراستەی سیگناڵ لە BUY بۆ SELL یان بە پێچەوانەوە
        if prev_side in ("BUY", "SELL") and side in ("BUY", "SELL") and side != prev_side:
            old_label = "کڕین (BUY)" if prev_side == "BUY" else "فرۆشتن (SELL)"
            new_label = "فرۆشتن (SELL)" if side == "SELL" else "کڕین (BUY)"

            if prev_side == "BUY":
                guidance = (
                    "• ڕێنمایی: ئەگەر پۆزیسیۆنی کڕینت هەیە، بیر لە داخستنی بکەرەوە یان "
                    "ستۆپ لۆس (SL) زۆر نزیک بخەرەوە بۆ پاراستنی قازانج/کەمکردنەوەی زیان؛ "
                    "چاوەڕوانی داخستنی مۆمیش بە ئەگەر لە کورت مەودادایت."
                )
            else:
                guidance = (
                    "• ڕێنمایی: ئەگەر پۆزیسیۆنی فرۆشتنت هەیە، بیر لە داخستنی بکەرەوە یان "
                    "ستۆپ لۆس (SL) بێنە خوارەوە بۆ خاڵی بێ زیان (Break-even)؛ "
                    "بە وریایی مامەڵە بکە چونکە زەبری سەرەوە دەرکەوتووە."
                )

            msg = (
                f"⚠️ ئاگاداری پێچەوانەبوونەوەی سیگناڵ!\n"
                f"جووت: {symbol} | تایمفرێم: {tf}\n"
                f"سیگناڵی پێشوو: {old_label} (چوونەژوورەوە: {prev.get('entry', 0):.5f})\n"
                f"دۆخی نوێ: {new_label} (نرخی ئێستا: {price:.5f} | خاڵ: {item.get('score', 0)})\n"
                f"{guidance}"
            )
            alerts.append(msg)
            # سیگناڵی پێشوو لە چالاکەکان لادەبرێت تا سیگناڵە نوێیەکە جێگەی بگرێتەوە
            del signals[key]

        # حاڵەتی دووەم: شکانی ستۆپ لۆسی سیگناڵی پێشوو تەنانەت ئەگەر سیگناڵی پێچەوانەی تەواویش نەهاتبێت
        elif isinstance(price, (int, float)) and prev.get("sl") is not None:
            sl = prev["sl"]
            if prev_side == "BUY" and price <= sl:
                alerts.append(
                    f"🛑 شکانی ستۆپ لۆس (SL) بۆ سیگناڵی کڕین (BUY)\n"
                    f"جووت: {symbol} | تایمفرێم: {tf}\n"
                    f"نرخی ئێستا ({price:.5f}) گەیشتە ژێر SL ({sl:.5f}).\n"
                    f"• ڕێنمایی: ئەگەر هێشتا کراوەیە، پێداچوونەوە بە داخستنی پۆزیسیۆنەکە بکە و دژی مەیل مەوەستە."
                )
                del signals[key]
            elif prev_side == "SELL" and price >= sl:
                alerts.append(
                    f"🛑 شکانی ستۆپ لۆس (SL) بۆ سیگناڵی فرۆشتن (SELL)\n"
                    f"جووت: {symbol} | تایمفرێم: {tf}\n"
                    f"نرخی ئێستا ({price:.5f}) گەیشتە سەرووی SL ({sl:.5f}).\n"
                    f"• ڕێنمایی: ئەگەر هێشتا کراوەیە، پێداچوونەوە بە داخستنی پۆزیسیۆنەکە بکە و دژی مەیل مەوەستە."
                )
                del signals[key]

    return alerts