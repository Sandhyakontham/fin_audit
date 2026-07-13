"""
dashboard.py
Streamlit dashboard: generate or load transactions, run the fraud agent,
and view flagged transactions with their AI-generated risk score + narrative.

Run:
    streamlit run dashboard.py
"""

import pandas as pd
import streamlit as st

import config
import generate_data
import fraud_agent

st.set_page_config(page_title="FinAudit AI", page_icon="🔍", layout="wide")
st.title("🔍 FinAudit AI — Transaction Forensic Dashboard")

badge = "☁️ Gemini API" if config.LLM_BACKEND == "gemini" else "💻 Local (Ollama)"
st.caption(f"Backend: {badge}")

if config.LLM_BACKEND == "gemini" and not config.GEMINI_API_KEY:
    st.error(
        "LLM_BACKEND is set to 'gemini' but GEMINI_API_KEY is missing. "
        "Set it as an environment variable and restart the app."
    )
    st.stop()

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Get transaction data")
    if st.button("Generate sample transactions"):
        generate_data.main()
        st.success(f"Generated synthetic data -> {config.TRANSACTIONS_FILE}")

    uploaded = st.file_uploader("...or upload your own CSV", type=["csv"])
    if uploaded:
        with open(config.TRANSACTIONS_FILE, "wb") as f:
            f.write(uploaded.getbuffer())
        st.success(f"Saved upload -> {config.TRANSACTIONS_FILE}")

with col2:
    st.subheader("2. Run the audit")
    st.caption("Expected columns: transaction_id, customer_id, timestamp, "
               "amount, merchant_name, mcc_category, city, country")
    run_clicked = st.button("Run fraud analysis", type="primary")

if run_clicked:
    try:
        df = pd.read_csv(config.TRANSACTIONS_FILE)
    except FileNotFoundError:
        st.error("No transaction file found. Generate or upload one first.")
        st.stop()

    with st.spinner(f"Analyzing {len(df)} transactions... (this calls the LLM once per transaction)"):
        results = fraud_agent.analyze_transactions(df)
        results.to_csv(config.RESULTS_FILE, index=False)
    st.session_state["results"] = results
    st.success(f"Analysis complete -- {len(results)} transactions scored.")

st.divider()
st.subheader("3. Results")

if "results" in st.session_state:
    results = st.session_state["results"]

    flagged = results[results["risk_score"] >= config.RISK_THRESHOLD].sort_values(
        "risk_score", ascending=False
    )
    clean = results[results["risk_score"] < config.RISK_THRESHOLD]

    st.metric("Flagged for review", len(flagged), help=f"Risk score >= {config.RISK_THRESHOLD}")

    if len(flagged) > 0:
        st.markdown(f"#### ⚠️ Flagged transactions (risk score ≥ {config.RISK_THRESHOLD})")
        for _, r in flagged.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                c1.metric("Risk score", int(r["risk_score"]))
                c2.markdown(f"**{r['transaction_id']}** — {r['customer_id']} — "
                            f"${r['amount']} at {r['merchant_name']} "
                            f"({r['city']}, {r['country']})")
                c2.write(r["narrative"])
                if r["flags"]:
                    c2.caption(f"Flags: {r['flags']}")
    else:
        st.info("No transactions crossed the risk threshold.")

    with st.expander(f"View all {len(results)} scored transactions"):
        st.dataframe(results, use_container_width=True)
else:
    st.info("Generate/upload data and run the analysis to see results here.")
