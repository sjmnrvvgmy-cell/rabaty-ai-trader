import streamlit as st
import pandas as pd
from scanner import scan_all
from signal_engine import format_signal

st.set_page_config(page_title="RABATY AI TRADER", page_icon="📈", layout="wide")
st.title("📈 RABATY AI TRADER")
st.caption("Signal-only market monitor • Forex Gold + Bybit XAUT + Crypto")
st.warning("Prototype: signals are rule-based research aids, not financial advice or guaranteed predictions.")
if st.button("Run market scan", type="primary"):
    with st.spinner("Loading public market candles and calculating setups…"):
        results = scan_all()
    st.session_state["results"] = results

if "results" in st.session_state:
    results = st.session_state["results"]
    rows = []
    for s in results:
        rows.append({
            "Market": s["symbol"], "Timeframe": s["timeframe"],
            "Signal": s["side"], "Price": s.get("price"),
            "Score": s.get("score"), "RSI": s.get("rsi"),
            "Error": s.get("error", "")
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    for s in results:
        with st.expander(f"{s['symbol']} • {s['timeframe']} • {s['side']}"):
            if s["side"] == "ERROR":
                st.error(s["error"])
            else:
                st.code(format_signal(s))
else:
    st.info("Press **Run market scan** to fetch the latest available candles.")
