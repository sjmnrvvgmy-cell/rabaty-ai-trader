import numpy as np
import pandas as pd

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def analyze(df: pd.DataFrame, symbol: str, timeframe: str, min_score: int = 4) -> dict:
    """Rule-based educational signal prototype. Not a prediction or guarantee."""
    if len(df) < 60:
        raise ValueError("At least 60 candles are required for analysis.")
    d = df.copy()
    d["ema20"] = d.close.ewm(span=20, adjust=False).mean()
    d["ema50"] = d.close.ewm(span=50, adjust=False).mean()
    d["rsi"] = _rsi(d.close)
    d["atr"] = _atr(d)
    last = d.iloc[-1]
    prev = d.iloc[-2]
    recent = d.iloc[-21:-1]
    score_buy = 0
    score_sell = 0
    reasons_buy, reasons_sell = [], []

    if last.close > last.ema20 > last.ema50:
        score_buy += 1; reasons_buy.append("EMA trend bullish")
    if last.close < last.ema20 < last.ema50:
        score_sell += 1; reasons_sell.append("EMA trend bearish")

    if 50 <= last.rsi <= 68:
        score_buy += 1; reasons_buy.append("RSI momentum supports buyers")
    if 32 <= last.rsi <= 50:
        score_sell += 1; reasons_sell.append("RSI momentum supports sellers")

    # Simplified structure break (BOS): close beyond recent 20-candle range.
    if last.close > recent.high.max():
        score_buy += 2; reasons_buy.append("Bullish structure break (BOS)")
    if last.close < recent.low.min():
        score_sell += 2; reasons_sell.append("Bearish structure break (BOS)")

    # Liquidity sweep: wick takes prior range extreme, candle closes back inside.
    prior_high, prior_low = recent.high.max(), recent.low.min()
    if last.high > prior_high and last.close < prior_high:
        score_sell += 1; reasons_sell.append("Possible buy-side liquidity sweep")
    if last.low < prior_low and last.close > prior_low:
        score_buy += 1; reasons_buy.append("Possible sell-side liquidity sweep")

    # Fair Value Gap approximation over the last three candles.
    if len(d) >= 3 and d.low.iloc[-1] > d.high.iloc[-3]:
        score_buy += 1; reasons_buy.append("Bullish FVG detected")
    if len(d) >= 3 and d.high.iloc[-1] < d.low.iloc[-3]:
        score_sell += 1; reasons_sell.append("Bearish FVG detected")

    atr = float(last.atr) if pd.notna(last.atr) else float((d.high-d.low).tail(14).mean())
    price = float(last.close)
    if not np.isfinite(atr) or atr <= 0:
        raise ValueError("ATR unavailable; cannot calculate risk levels.")

    if score_buy >= min_score and score_buy > score_sell:
        side, score, reasons = "BUY", score_buy, reasons_buy
        sl = price - 1.5 * atr
        risk = price - sl
        tps = [price + risk, price + 2*risk, price + 3*risk]
    elif score_sell >= min_score and score_sell > score_buy:
        side, score, reasons = "SELL", score_sell, reasons_sell
        sl = price + 1.5 * atr
        risk = sl - price
        tps = [price - risk, price - 2*risk, price - 3*risk]
    else:
        side, score, reasons, sl, tps = "WAIT", max(score_buy, score_sell), [], None, []

    return {
        "symbol": symbol, "timeframe": timeframe, "side": side,
        "price": price, "score": score, "buy_score": score_buy,
        "sell_score": score_sell, "rsi": float(last.rsi),
        "atr": atr, "stop_loss": sl, "take_profits": tps,
        "reasons": reasons, "candle_time": str(d.index[-1]),
    }

def format_signal(s: dict) -> str:
    if s["side"] == "WAIT":
        return (f"⏳ {s['symbol']} | {s['timeframe']} — WAIT\n"
                f"Price: {s['price']:.5f}\n"
                f"Score: BUY {s['buy_score']} / SELL {s['sell_score']}\n"
                "No qualified setup. No trade.")
    lines = [
        f"{'🟢' if s['side']=='BUY' else '🔴'} {s['symbol']} — {s['side']}",
        f"Timeframe: {s['timeframe']} | Score: {s['score']}",
        f"Entry reference: {s['price']:.5f}",
        f"Stop Loss: {s['stop_loss']:.5f}",
    ]
    for i, tp in enumerate(s["take_profits"], 1):
        lines.append(f"TP{i}: {tp:.5f}")
    lines.append(f"RSI: {s['rsi']:.1f}")
    if s["reasons"]:
        lines.append("Reasons: " + "; ".join(s["reasons"]))
    lines.append("Educational signal only. Confirm spread, feed and risk before acting.")
    return "\n".join(lines)
