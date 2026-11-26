import numpy as np
import pandas as pd


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def analyze(df: pd.DataFrame, symbol: str, timeframe: str, min_score: int = 3) -> dict:
    """Rule-based short-term signal engine. Not financial advice or a guarantee."""
    if len(df) < 60:
        raise ValueError("At least 60 candles are required for analysis.")

    d = df.copy()
    d["ema20"] = d.close.ewm(span=20, adjust=False).mean()
    d["ema50"] = d.close.ewm(span=50, adjust=False).mean()
    d["rsi"] = _rsi(d.close)
    d["atr"] = _atr(d)

    last = d.iloc[-1]
    recent = d.iloc[-16:-1] if timeframe in ("5m", "15m") else d.iloc[-21:-1]

    score_buy = 0
    score_sell = 0
    reasons_buy, reasons_sell = [], []

    if last.close > last.ema20 > last.ema50:
        score_buy += 1
        reasons_buy.append("مەیلی EMA سەرەوەیە")
    if last.close < last.ema20 < last.ema50:
        score_sell += 1
        reasons_sell.append("مەیلی EMA خوارەوەیە")

    if 50 <= last.rsi <= 72:
        score_buy += 1
        reasons_buy.append("زەبری RSI پاڵپشتی کڕینە")
    if 28 <= last.rsi <= 50:
        score_sell += 1
        reasons_sell.append("زەبری RSI پاڵپشتی فرۆشتنە")

    # شکاندنی پێکهاتەی کورت مەودا (BOS)
    if last.close > recent.high.max():
        score_buy += 2
        reasons_buy.append("شکاندنی بەرزایی پێشوو (BOS سەرەوە)")
    if last.close < recent.low.min():
        score_sell += 2
        reasons_sell.append("شکاندنی نزمترین نرخی پێشوو (BOS خوارەوە)")

    # ڕاماڵینی سیولە (Liquidity Sweep)
    prior_high, prior_low = recent.high.max(), recent.low.min()
    if last.high > prior_high and last.close < prior_high:
        score_sell += 1
        reasons_sell.append("ڕاماڵینی سیولەی سەرەوە (Liquidity Sweep)")
    if last.low < prior_low and last.close > prior_low:
        score_buy += 1
        reasons_buy.append("ڕاماڵینی سیولەی خوارەوە (Liquidity Sweep)")

    # بۆشایی نرخی دادپەروەرانە (FVG)
    if len(d) >= 3 and d.low.iloc[-1] > d.high.iloc[-3]:
        score_buy += 1
        reasons_buy.append("دروستبوونی FVG سەرەوە")
    if len(d) >= 3 and d.high.iloc[-1] < d.low.iloc[-3]:
        score_sell += 1
        reasons_sell.append("دروستبوونی FVG خوارەوە")

    atr = float(last.atr) if pd.notna(last.atr) else float((d.high - d.low).tail(14).mean())
    price = float(last.close)
    if not np.isfinite(atr) or atr <= 0:
        raise ValueError("ATR unavailable; cannot calculate risk levels.")

    # بۆ کورت مەودا SL و TP کەمێک نزیکتر و خێراتر ڕێک خراون
    sl_mult = 1.2 if timeframe in ("5m", "15m") else 1.5

    if score_buy >= min_score and score_buy > score_sell:
        side, score, reasons = "BUY", score_buy, reasons_buy
        sl = price - sl_mult * atr
        risk = price - sl
        tps = [price + risk, price + 1.8 * risk, price + 2.5 * risk]
    elif score_sell >= min_score and score_sell > score_buy:
        side, score, reasons = "SELL", score_sell, reasons_sell
        sl = price + sl_mult * atr
        risk = sl - price
        tps = [price - risk, price - 1.8 * risk, price - 2.5 * risk]
    else:
        side, score, reasons, sl, tps = "WAIT", max(score_buy, score_sell), [], None, []

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "price": price,
        "score": score,
        "buy_score": score_buy,
        "sell_score": score_sell,
        "rsi": float(last.rsi),
        "atr": atr,
        "stop_loss": sl,
        "take_profits": tps,
        "reasons": reasons,
        "candle_time": str(d.index[-1]),
    }


def format_signal(s: dict) -> str:
    if s["side"] == "WAIT":
        return (
            f"⏳ {s['symbol']} | {s['timeframe']} — چاوەڕوانی (WAIT)\n"
            f"نرخ: {s['price']:.5f}\n"
            f"خاڵ: کڕین {s['buy_score']} / فرۆشتن {s['sell_score']}\n"
            f"هیچ دەرفەتێکی گونجاو نییە."
        )

    side_label = "کڕین (BUY)" if s["side"] == "BUY" else "فرۆشتن (SELL)"
    icon = "🟢" if s["side"] == "BUY" else "🔴"

    lines = [
        f"{icon} {s['symbol']} — {side_label}",
        f"تایمفرێم: {s['timeframe']} | خاڵ: {s['score']}",
        f"نرخی چوونەژوورەوە: {s['price']:.5f}",
        f"ستۆپ لۆس (SL): {s['stop_loss']:.5f}",
    ]
    for i, tp in enumerate(s["take_profits"], 1):
        lines.append(f"ئامانجی {i} (TP{i}): {tp:.5f}")
    lines.append(f"RSI: {s['rsi']:.1f}")
    if s["reasons"]:
        lines.append("هۆکارەکان: " + "، ".join(s["reasons"]))
    lines.append("تێبینی: ئەمە سیگناڵی تەکنیکییە؛ پێش چوونەناوەوە سپرێد و مەترسی بپشکنە.")
    return "\n".join(lines)