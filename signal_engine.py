import os
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


def calculate_position_sizing(symbol: str, entry: float, sl: float) -> dict | None:
    balance_raw = os.getenv("ACCOUNT_BALANCE", "").strip()
    if not balance_raw:
        return None

    try:
        balance = float(balance_raw)
        risk_pct = float(os.getenv("RISK_PERCENT", "1.0"))
    except ValueError:
        return None

    stop_dist = abs(float(entry) - float(sl))
    if balance <= 0 or risk_pct <= 0 or stop_dist <= 0:
        return None

    risk_amount = balance * (risk_pct / 100.0)
    sym = symbol.upper()

    if sym.endswith("/USDT"):
        units = risk_amount / stop_dist
        contract_size = float(os.getenv("CRYPTO_LOT_SIZE", "1.0"))
        lots = units / contract_size if contract_size > 0 else units
        unit_label = (
            f"Lot (1 Lot = {contract_size:g} {sym.split('/')[0]})"
            if contract_size != 1.0
            else f"{sym.split('/')[0]} Units"
        )
        return {
            "risk_amount": risk_amount,
            "risk_pct": risk_pct,
            "lots": lots,
            "unit_label": unit_label,
        }

    if sym.startswith("XAU"):
        default_contract = 100.0
    elif sym.startswith("XAG"):
        default_contract = 5000.0
    else:
        default_contract = 100000.0

    contract_size = float(os.getenv("CONTRACT_SIZE", str(default_contract)))
    lots = risk_amount / (stop_dist * contract_size) if contract_size > 0 else 0.0

    return {
        "risk_amount": risk_amount,
        "risk_pct": risk_pct,
        "lots": lots,
        "unit_label": "Lot",
    }


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

    if last.close > recent.high.max():
        score_buy += 2
        reasons_buy.append("شکاندنی بەرزایی پێشوو (BOS سەرەوە)")
    if last.close < recent.low.min():
        score_sell += 2
        reasons_sell.append("شکاندنی نزمترین نرخی پێشوو (BOS خوارەوە)")

    prior_high, prior_low = recent.high.max(), recent.low.min()
    if last.high > prior_high and last.close < prior_high:
        score_sell += 1
        reasons_sell.append("ڕاماڵینی سیولەی سەرەوە (Liquidity Sweep)")
    if last.low < prior_low and last.close > prior_low:
        score_buy += 1
        reasons_buy.append("ڕاماڵینی سیولەی خوارەوە (Liquidity Sweep)")

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

    sizing = calculate_position_sizing(s["symbol"], s["price"], s["stop_loss"])
    if sizing:
        lines.append(
            f"قەبارەی پێشنیارکراو: {sizing['lots']:.2f} {sizing['unit_label']} "
            f"(مەترسی: {sizing['risk_amount']:.2f}$ / {sizing['risk_pct']}%)"
        )

    if s["reasons"]:
        lines.append("هۆکارەکان: " + "، ".join(s["reasons"]))
    lines.append("تێبینی: ئەمە سیگناڵی تەکنیکییە؛ پێش چوونەناوەوە سپرێد و مەترسی بپشکنە.")
    return "\n".join(lines)