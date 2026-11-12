"""Local, read-only presentation UI. Never calls an external API."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(
    page_title="JPM · Implied Volatility Lab", page_icon="◈", layout="wide"
)
st.markdown(
    """<style>
.stApp {background:#0c1220;color:#e7edf8} [data-testid="stSidebar"] {background:#111b2e}
h1,h2,h3 {letter-spacing:-.03em} [data-testid="stMetric"] {background:#142139;border:1px solid #2b3b55;padding:20px;border-radius:12px}
[data-testid="stMetricValue"] {font-size:clamp(1.05rem,2vw,2rem)}
.block-container {padding-top:2.5rem} .eyebrow {color:#5ce1be;letter-spacing:.18em;font-size:12px;font-weight:700}
</style>""",
    unsafe_allow_html=True,
)
st.sidebar.markdown("## ◈ IV Lab")
st.sidebar.caption("OPTION PRICING / RESEARCH SHOWCASE")
available = [
    name
    for name in ["market", "sample"]
    if (ROOT / "reports" / name / "run.json").exists()
]
if not available:
    st.info("Run `python main.py sample` or `python main.py refresh` first.")
    st.stop()
mode = st.sidebar.selectbox(
    "Dataset",
    available,
    format_func=lambda v: (
        "JPM · real API snapshot" if v == "market" else "Offline · synthetic sample"
    ),
)
folder = ROOT / "reports" / mode


@st.cache_data
def read_csv(path, modified):
    return pd.read_csv(path)


def read(name):
    p = folder / name
    return read_csv(str(p), p.stat().st_mtime_ns)


run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
labels = read("labels_audit.csv")
pred = read("out_of_time_predictions.csv")
metrics = read("metrics.csv")
provenance = run.get("data_provenance", {})
if provenance.get("download_status", "").startswith("incomplete"):
    st.warning(
        f"INCOMPLETE HISTORICAL SAMPLE · {provenance.get('option_sessions', 'unknown')} of {provenance.get('expected_sessions', 'unknown')} expected trading sessions; {provenance.get('missing_sessions', 'unknown')} missing. Requested {provenance.get('start')} through {provenance.get('requested_through')}; latest included option {provenance.get('latest_observations', {}).get('options')}. Cached recent dates do not fill the intervening calendar gaps. These results are not a complete one-year backtest."
    )

st.markdown(
    '<div class="eyebrow">MARKET STRUCTURE · PRICING · MACHINE LEARNING</div>',
    unsafe_allow_html=True,
)
st.title("Implied Volatility Lab")
st.markdown("From market option prices to a learned volatility smile.")
if mode == "sample":
    st.warning(
        "SYNTHETIC SAMPLE · generated for an offline presentation. These are not real market observations."
    )
else:
    st.caption(
        "JPM / American CRR inversion / original four-source API workflow / local snapshot"
    )
cols = st.columns(4)
cols[0].metric("Quotes", f"{run['rows']:,}")
cols[1].metric("IV labels", f"{run['accepted']:,}")
cols[2].metric(
    "Sessions", pd.to_datetime(labels.quote_time, utc=True).dt.date.nunique()
)
cols[3].metric(
    "Latest option quote", str(pd.to_datetime(labels.quote_time, utc=True).max().date())
)
st.markdown(
    "**Market bid / ask → mid price → CRR / BSM inversion → IV labels → regression models → held-out evaluation**"
)
tabs = st.tabs(
    ["Volatility smile", "Model performance", "Market & data", "Method & sources"]
)
colors = {
    "Market IV": "#eef4ff",
    "linear": "#ffbd69",
    "random_forest": "#5ce1be",
    "xgboost": "#b49bff",
}
with tabs[0]:
    st.subheader("Does the model learn the smile?")
    st.caption(
        "Each curve uses one quote day, expiry, option side and exercise style. Predictions come from later-date evaluation folds."
    )
    dates = sorted(pred.quote_time.unique())
    date = st.selectbox("Quote timestamp", dates, index=len(dates) - 1)
    day = pred[pred.quote_time == date]
    c1, c2, c3 = st.columns(3)
    expiry = c1.selectbox("Expiry", sorted(day.expiry.unique()))
    side = c2.selectbox("Option side", sorted(day[day.expiry == expiry].kind.unique()))
    subset = day[(day.expiry == expiry) & (day.kind == side)]
    style = c3.selectbox("Exercise style", sorted(subset["style"].unique()))
    subset = subset[subset["style"] == style]
    actual = subset.drop_duplicates("strike").sort_values("log_moneyness")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=actual.log_moneyness,
            y=actual.implied_volatility,
            mode="lines+markers",
            name="Market IV",
            line=dict(color=colors["Market IV"], width=3),
        )
    )
    for name, g in subset.groupby("model"):
        g = g.sort_values("log_moneyness")
        fig.add_trace(
            go.Scatter(
                x=g.log_moneyness,
                y=g.predicted_iv,
                mode="lines+markers",
                name=name,
                line=dict(color=colors[name]),
            )
        )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0c1220",
        plot_bgcolor="#101b2d",
        height=450,
        xaxis_title="Log moneyness · ln(K/S)",
        yaxis_title="Annualized implied volatility",
        yaxis_tickformat=".0%",
        legend_orientation="h",
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        actual[["strike", "spot", "mid", "implied_volatility", "t"]],
        hide_index=True,
        width="stretch",
    )
with tabs[1]:
    st.subheader("Performance on later quote dates")
    st.caption(
        "IV errors are decimal volatility units: 0.01 equals one volatility percentage point. Price MAE is dollars per share."
    )
    chart = px.bar(
        metrics,
        x="fold",
        y="iv_mae",
        color="model",
        barmode="group",
        color_discrete_map=colors,
        labels={"iv_mae": "IV MAE", "fold": "Expanding-window fold"},
        template="plotly_dark",
    )
    chart.update_layout(paper_bgcolor="#0c1220", plot_bgcolor="#101b2d")
    st.plotly_chart(chart, width="stretch")
    st.dataframe(metrics, hide_index=True, width="stretch")
    model = st.selectbox("Inspect prediction residuals", sorted(pred.model.unique()))
    part = pred[pred.model == model].copy()
    part["iv_error"] = part.predicted_iv - part.implied_volatility
    fig = px.scatter(
        part,
        x="implied_volatility",
        y="predicted_iv",
        color="kind",
        hover_data=["quote_time", "strike", "mid"],
        template="plotly_dark",
    )
    low = min(part.implied_volatility.min(), part.predicted_iv.min())
    high = max(part.implied_volatility.max(), part.predicted_iv.max())
    fig.add_shape(
        type="line",
        x0=low,
        y0=low,
        x1=high,
        y1=high,
        line=dict(color="#5ce1be", dash="dash"),
    )
    fig.update_layout(paper_bgcolor="#0c1220", plot_bgcolor="#101b2d")
    st.plotly_chart(fig, width="stretch")
    st.download_button(
        "Download held-out predictions",
        pred.to_csv(index=False),
        file_name=f"{mode}_predictions.csv",
        mime="text/csv",
    )
with tabs[2]:
    st.subheader("What is in this snapshot?")
    st.json(provenance)
    valid = labels[labels.label_status == "ok"]
    st.write("Label audit")
    st.dataframe(
        labels.label_status.value_counts()
        .rename_axis("Status")
        .reset_index(name="Rows"),
        hide_index=True,
    )
    history = valid.groupby("quote_time", as_index=False).agg(
        spot=("spot", "median"),
        vix=("vix", "median"),
        r=("r", "median"),
        q=("q", "median"),
    )
    field = st.selectbox("Market context", ["spot", "vix", "r", "q"])
    fig = px.line(history, x="quote_time", y=field, template="plotly_dark")
    fig.update_layout(paper_bgcolor="#0c1220", plot_bgcolor="#101b2d")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(labels.head(100), hide_index=True, width="stretch")
with tabs[3]:
    st.subheader("A transparent two-stage model")
    st.markdown("""
1. **Invert market prices.** American JPM quotes use a CRR tree with early exercise; European sample quotes use BSM. Market IV is the target.
2. **Build time-aligned features.** Trailing stock returns and realized volatility, option moneyness/maturity/liquidity, VIX, Treasury rates and paid dividends.
3. **Train on earlier dates.** Linear Regression, Random Forest and XGBoost use expanding windows, complete date groups and a one-day calendar gap.
4. **Evaluate later dates.** Compare IV MAE/RMSE, repricing errors and smile/skew/curvature within the same contract slice.

**Original data providers**
- **yfinance / Yahoo Finance:** JPM OHLCV, adjusted close and paid dividends.
- **Alpha Vantage:** daily Treasury yields at 3 months and 2, 5, 7, 10, 30 years.
- **FRED:** VIXCLS observations.
- **MarketData:** historical JPM option chains; original DTE/monthly/strike filters retained.

**Interpretation limits:** macro publication times are conservative assumptions, not verified historical vintages. This is contemporaneous IV estimation, not next-day forecasting. One short data window does not establish investment performance. The cash-dividend pricer is an approximation; the default pipeline uses a trailing continuous yield. No chooser payoff is priced in this phase.
""")
    with st.expander("Model feature allowlist"):
        st.write(run["features"])
    st.caption(
        "The app reads local files only. Refreshing data and training are explicit Python commands; API keys never enter the browser."
    )
