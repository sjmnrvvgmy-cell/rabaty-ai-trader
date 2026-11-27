import numpy as np
import pandas as pd


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    prev_close = df["close"].astype(float).shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean().bfill()


def analyze(df: pd.DataFrame, symbol: str, timeframe: str = "15m", min_score: int = 3) -> dict:
    if df is None or len(df) < 60:
        return {"action": "WAIT", "symbol": symbol, "timeframe": timeframe, "score": 0}

    data = df.copy()
    for col in ("open", "high", "low", "close"):
        data[col] = data[col].astype(float)

    close = data["close"]
    high = data["high"]
    low = data["low"]

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    rsi = _compute_rsi(close, 14)
    atr = _compute_atr(data, 14)

    last_close = float(close.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_rsi = float(rsi.iloc[-1])
    last_atr = float(atr.iloc[-1])

    if not np.isfinite(last_atr) or last_atr <= 0:
        last_atr = max(last_close * 0.005, 1e-6)

    prev_high_max = float(high.iloc[-21:-1].max())
    prev_low_min = float(low.iloc[-21:-1].min())

    bull_reasons: list[str] = []
    bear_reasons: list[str] = []
    bull_score = 0
    bear_score = 0

    if last_close > last_ema20 and last_ema20 >= last_ema50:
        bull_score += 2
        bull_reasons.append("مەیلی EMA سەرەوەیە")
    elif last_close < last_ema20 and last_ema20 <= last_ema50:
        bear_score += 2
        bear_reasons.append("مەیلی EMA خوارەوەیە")

    if last_rsi >= 55.0:
        bull_score += 1
        bull_reasons.append("زەبری RSI پاڵپشتی کڕینە")
    elif last_rsi <= 45.0:
        bear_score += 1
        bear_reasons.append("زەبری RSI پاڵپشتی فرۆشتنە")

    if last_close > prev_high_max:
        bull_score += 1
        bull_reasons.append("شکاندنی بەرزایی پێشوو (BOS سەرەوە)")
    elif last_close < prev_low_min:
        bear_score += 1
        bear_reasons.append("شکاندنی نزمترین نرخی پێشوو (BOS خوارەوە)")

    # پشکنینی Fair Value Gap (FVG) لە دوایین 3 مۆمدا
    if len(data) >= 3:
        h_3 = float(high.iloc[-3])
        l_3 = float(low.iloc[-3])
        h_1 = float(high.iloc[-1])
        l_1 = float(low.iloc[-1])
        if l_1 > h_3:
            bull_score += 1
            bull_reasons.append("دروستبوونی FVG سەرەوە")
        elif h_1 < l_3:
            bear_score += 1
            bear_reasons.append("دروستبوونی FVG خوارەوە")

    decimals = 5 if last_close < 10 else 2
    candle_time = str(data.index[-1])

    if bull_score >= min_score and bull_score > bear_score:
        sl = max(last_close - (1.2 * last_atr), 1e-8)
        risk = max(last_close - sl, 1e-8)
        tp1 = last_close + (1.0 * risk)
        tp2 = last_close + (1.7 * risk)
        tp3 = last_close + (2.3 * risk)
        return {
            "action": "BUY",
            "symbol": symbol,
            "timeframe": timeframe,
            "score": bull_score,
            "entry": round(last_close, decimals),
            "sl": round(sl, decimals),
            "tp1": round(tp1, decimals),
            "tp2": round(tp2, decimals),
            "tp3": round(tp3, decimals),
            "rsi": round(last_rsi, 1),
            "reasons": bull_reasons,
            "candle_time": candle_time,
            "decimals": decimals,
        }

    if bear_score >= min_score and bear_score > bull_score:
        sl = last_close + (1.2 * last_atr)
        risk = max(sl - last_close, 1e-8)
        tp1 = max(last_close - (1.0 * risk), 1e-8)
        tp2 = max(last_close - (1.7 * risk), 1e-8)
        tp3 = max(last_close - (2.3 * risk), 1e-8)
        return {
            "action": "SELL",
            "symbol": symbol,
            "timeframe": timeframe,
            "score": bear_score,
            "entry": round(last_close, decimals),
            "sl": round(sl, decimals),
            "tp1": round(tp1, decimals),
            "tp2": round(tp2, decimals),
            "tp3": round(tp3, decimals),
            "rsi": round(last_rsi, 1),
            "reasons": bear_reasons,
            "candle_time": candle_time,
            "decimals": decimals,
        }

    return {"action": "WAIT", "symbol": symbol, "timeframe": timeframe, "score": max(bull_score, bear_score)}


def format_signal(sig: dict) -> str:
    action = str(sig.get("action", "WAIT")).upper()
    symbol = sig.get("symbol", "")
    tf = sig.get("timeframe", "")
    score = sig.get("score", 0)
    decimals = int(sig.get("decimals", 5))
    fmt = f"{{:.{decimals}f}}"

    if action == "BUY":
        badge = "🟢"
        side_text = "کڕین (BUY)"
    else:
        badge = "🔴"
        side_text = "فرۆشتن (SELL)"

    reasons_text = "، ".join(sig.get("reasons", []))
    return (
        f"{badge} {symbol} — {side_text}\n"
        f"تایمفرێم: {tf} | خاڵ: {score}\n"
        f"نرخی چوونەژوورەوە: {fmt.format(float(sig['entry']))}\n"
        f"ستۆپ لۆس (SL): {fmt.format(float(sig['sl']))}\n"
        f"ئامانجی 1 (TP1): {fmt.format(float(sig['tp1']))}\n"
        f"ئامانجی 2 (TP2): {fmt.format(float(sig['tp2']))}\n"
        f"ئامانجی 3 (TP3): {fmt.format(float(sig['tp3']))}\n"
        f"RSI: {float(sig['rsi']):.1f}\n"
        f"هۆکارەکان: {reasons_text}\n"
        f"تێبینی: ئەمە سیگناڵی تەکنیکییە؛ پێش چوونەناوەوە سپرێد و مەترسی بپشکنە."
    )