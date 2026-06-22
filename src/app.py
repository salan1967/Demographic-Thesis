"""
app.py — interactive dashboard, lets a reviewer adjust thresholds live.
Run: streamlit run src/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import data_engine as de

st.set_page_config(page_title="Demographic Dividend Reversed", layout="wide")

st.title("Demographic Dividend Reversed")
st.markdown("**Investing Around a Shrinking Workforce** — interactive checkpoint dashboard")

st.markdown(
    "> Demographic contraction is creating real, measurable labor scarcity in aging "
    "economies (US, Japan, South Korea). The investment response — AI-driven "
    "automation substituting for labor — is still in its early innings. The market "
    "has not yet fully priced this in. **The opportunity is forward-looking, not "
    "backward-confirming.**"
)

st.sidebar.header("Adjust Parameters")
dependency_threshold = st.sidebar.slider(
    "Aging threshold (dependency ratio)", min_value=40.0, max_value=70.0,
    value=de.DEFAULT_DEPENDENCY_THRESHOLD, step=1.0,
    help="Dependency ratio above this value classifies a country-year as 'Aging'."
)
ai_split_year = st.sidebar.slider(
    "AI-wave split year", min_value=2018, max_value=2024,
    value=int(de.AI_WAVE_SPLIT[:4]), step=1,
    help="Year used to split 'pre' vs 'post' AI-wave automation performance."
)
ai_split = f"{ai_split_year}-01-01"


@st.cache_data(show_spinner="Pulling live data...")
def load_data(dependency_threshold, start, end):
    return de.build_combined_dataset(start=start, end=end,
                                      dependency_threshold=dependency_threshold)


try:
    data = load_data(dependency_threshold, de.DEFAULT_START, de.DEFAULT_END)
except Exception as e:
    st.error(f"Data pull failed: {e}\n\nCheck your internet connection — this dashboard "
             f"requires live access to the World Bank, FRED, and Yahoo Finance APIs.")
    st.stop()

verdict = de.compute_verdict(data, ai_wave_split=ai_split)

col1, col2, col3 = st.columns(3)
col1.metric("Pre-AI-wave spread", f"{verdict['pre_ai_wave_spread_pct']:.1f} pp")
col2.metric("Post-AI-wave spread", f"{verdict['post_ai_wave_spread_pct']:.1f} pp",
            delta=f"{verdict['post_ai_wave_spread_pct'] - verdict['pre_ai_wave_spread_pct']:.1f} pp")
col3.metric("Verdict", "SUPPORTED" if verdict["supported_early_innings"] else "NOT YET SUPPORTED")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["Demographics", "Basket Performance", "US Labor Scarcity"])

with tab1:
    st.subheader("Age Dependency Ratio by Country")
    demo = de.classify_demographic_regime(data["demographics"], threshold=dependency_threshold)
    fig, ax = plt.subplots(figsize=(10, 5))
    for code, name in de.COUNTRIES.items():
        sub = demo[demo["Country"] == code].sort_values("Year")
        ax.plot(sub["Year"], sub["Dependency_Ratio"], marker="o", markersize=3, label=name)
    ax.axhline(dependency_threshold, color="gray", linestyle="--", label="Aging threshold")
    ax.set_xlabel("Year"); ax.set_ylabel("Dependency Ratio (%)")
    ax.legend(); ax.spines[["top", "right"]].set_visible(False)
    st.pyplot(fig)
    st.dataframe(demo, use_container_width=True)

with tab2:
    st.subheader("Automation vs Labor-Intensive Basket")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(data["automation_index"].index, data["automation_index"].values, label="Automation (ROBO, BOTZ)")
    ax.plot(data["labor_index"].index, data["labor_index"].values, label="Labor-intensive (XRT, ITB)")
    ax.axvline(pd.Timestamp(ai_split), color="gray", linestyle="--", label=f"AI-wave split ({ai_split_year})")
    ax.set_xlabel("Date"); ax.set_ylabel("Indexed value (start = 100)")
    ax.legend(); ax.spines[["top", "right"]].set_visible(False)
    st.pyplot(fig)

with tab3:
    st.subheader("US Labor Force Participation vs. Wage Growth")
    fred = data.get("fred_indicators")
    if fred is not None and not fred.empty:
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax1.plot(fred.index, fred["Labor_Force_Participation"], label="Labor Force Participation (%)")
        ax1.set_xlabel("Date"); ax1.set_ylabel("Labor Force Participation (%)")
        if "Wage_Growth_Index" in fred.columns:
            ax2 = ax1.twinx()
            ax2.plot(fred.index, fred["Wage_Growth_Index"], color="darkred", linestyle="--",
                     label="Wage Growth (ECI)")
            ax2.set_ylabel("Employment Cost Index — Wages (% chg)")
        st.pyplot(fig)
    else:
        st.info("FRED data not available.")

st.markdown("---")
st.subheader("Sensitivity Table")
st.caption("How the verdict changes across a range of dependency-ratio thresholds, holding the AI-wave split fixed.")
sens_rows = []
for thr in [45, 50, 55, 60, 65]:
    v = de.compute_verdict(data, ai_wave_split=ai_split)  # spread doesn't depend on threshold directly
    sens_rows.append({
        "Dependency Threshold": thr,
        "Pre-AI-wave spread (pp)": round(v["pre_ai_wave_spread_pct"], 1),
        "Post-AI-wave spread (pp)": round(v["post_ai_wave_spread_pct"], 1),
        "Supported": v["supported_early_innings"],
    })
st.dataframe(pd.DataFrame(sens_rows), use_container_width=True)
st.caption("Note: the automation-vs-labor spread itself is threshold-independent in this "
           "checkpoint's design (the threshold affects demographic regime classification, "
           "not basket performance). A future iteration will weight basket performance by "
           "which countries are in the Aging regime at each point in time.")
