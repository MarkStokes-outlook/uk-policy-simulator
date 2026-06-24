
from pathlib import Path

import streamlit as st
import pandas as pd
import altair as alt

from model import (
    AssumptionError,
    BaselineError,
    FeedbackAssumptions,
    compute_fiscal,
    load_baseline,
)

st.set_page_config(
    page_title="UK Policy Sandbox",
    page_icon="🇬🇧",
    layout="wide",
)

BASELINE_PATH = Path(__file__).parent / "baseline.csv"

st.title("🇬🇧 UK Policy Sandbox")
st.caption(
    "A simplified fiscal and socio-economic simulator. All numbers are approximate £bn/year. "
    "It is designed for scenario exploration, not official forecasting."
)

# baseline.csv is the canonical source of truth for baseline fiscal values.
# Fail clearly in the UI if it is missing or invalid rather than falling back
# to silent hardcoded constants.
try:
    baseline = load_baseline(BASELINE_PATH)
except BaselineError as exc:
    st.error(
        f"Could not load baseline data from `{BASELINE_PATH.name}`.\n\n"
        f"**{exc}**\n\n"
        "The baseline file is the canonical source for receipts, spending and "
        "implied GDP. Fix the file and reload."
    )
    st.stop()

with st.expander("Model notes", expanded=False):
    st.markdown(
        f"""
**Baseline defaults** (loaded from `baseline.csv`, the canonical source)

- Total receipts: £{baseline.receipts:,.0f}bn.
- Total public spending: £{baseline.spending:,.0f}bn.
- Baseline deficit: £{baseline.deficit:,.0f}bn.
- Implied GDP: £{baseline.gdp:,.0f}bn.

**How the feedback model works (be honest)**

- Feedback is modelled as an **annual** effect proportional to the **current
  annual investment level** — not as a cumulative capital stock.
- It is **linearly ramped in** after the configured lag (no effect during the
  lag period, then a straight-line ramp to full effect).
- It is therefore **not** cumulative capital-stock / lifecycle modelling.
- _TODO:_ replace the flat annual-investment feedback with cumulative
  capital-stock / lifecycle modelling (depreciation and compounding returns on
  the accumulated stock rather than the current-year flow).

**Important limitations**

- This is a transparent model, not an OBR-grade macroeconomic model.
- Feedback effects are user-defined assumptions.
- Behavioural responses, inflation, migration, global shocks, interest-rate
  effects and distributional detail are not yet fully modelled.
"""
    )

st.sidebar.header("Scenario controls")

st.sidebar.subheader("Revenue reforms")
income_tax_ni_reform = st.sidebar.slider("Income tax / NI reform net yield", -50.0, 80.0, 0.0, 1.0)
wealth_tax_reform = st.sidebar.slider("Wealth / land / property tax reform", -20.0, 100.0, 35.0, 1.0)
passive_income_reform = st.sidebar.slider("CGT / dividends / rent equalisation", -10.0, 60.0, 20.0, 1.0)
corporate_tax_reform = st.sidebar.slider("Corporate / rent-seeking tax tightening", -20.0, 60.0, 10.0, 1.0)
carbon_resource_tax = st.sidebar.slider("Carbon / resource / windfall taxes", -20.0, 60.0, 15.0, 1.0)
anti_avoidance = st.sidebar.slider("Compliance / anti-avoidance yield", 0.0, 40.0, 8.0, 1.0)

st.sidebar.subheader("Investment / spending reforms")
childcare = st.sidebar.slider("Childcare expansion", 0.0, 60.0, 20.0, 1.0)
social_care = st.sidebar.slider("Social care settlement", 0.0, 60.0, 20.0, 1.0)
housing = st.sidebar.slider("Housing / social build programme", 0.0, 100.0, 35.0, 1.0)
nhs_prevention = st.sidebar.slider("NHS prevention + capacity", 0.0, 60.0, 15.0, 1.0)
education_training = st.sidebar.slider("Higher education / adult training", 0.0, 60.0, 15.0, 1.0)
welfare_floor = st.sidebar.slider("Welfare floor / taper smoothing", 0.0, 60.0, 15.0, 1.0)
transport_energy = st.sidebar.slider("Transport / energy infrastructure", 0.0, 100.0, 25.0, 1.0)

st.sidebar.subheader("Dynamic feedback assumptions")
years = st.sidebar.slider("Projection years", 5, 30, 15, 1)
growth_baseline = st.sidebar.slider("Baseline nominal GDP growth", 0.0, 6.0, 3.5, 0.1) / 100
revenue_feedback_rate = st.sidebar.slider("Revenue feedback from investment", 0.0, 100.0, 35.0, 1.0) / 100
cost_reduction_rate = st.sidebar.slider("Public cost reduction from social investment", 0.0, 100.0, 20.0, 1.0) / 100
lag_years = st.sidebar.slider("Feedback lag years", 0, 10, 3, 1)
implementation_quality = st.sidebar.slider("Implementation quality", 0.0, 100.0, 70.0, 1.0) / 100
optimism_penalty = st.sidebar.slider("Optimism penalty", 0.0, 50.0, 15.0, 1.0) / 100

# Lever values keyed by their display label so the same mapping drives both the
# calculation and the lever breakdown table below.
revenue_levers = {
    "Income tax / NI reform": income_tax_ni_reform,
    "Wealth / land / property reform": wealth_tax_reform,
    "Passive income equalisation": passive_income_reform,
    "Corporate / rent-seeking tax": corporate_tax_reform,
    "Carbon / resource / windfall taxes": carbon_resource_tax,
    "Compliance / anti-avoidance": anti_avoidance,
}

investment_levers = {
    "Childcare expansion": childcare,
    "Social care settlement": social_care,
    "Housing / social build": housing,
    "NHS prevention + capacity": nhs_prevention,
    "Higher education / adult training": education_training,
    "Welfare floor / taper smoothing": welfare_floor,
    "Transport / energy infrastructure": transport_energy,
}

# The sidebar sliders are bounded to valid ranges, so this should not normally
# fail; guard anyway so a bad assumption surfaces clearly rather than crashing.
try:
    assumptions = FeedbackAssumptions(
        years=years,
        growth_baseline=growth_baseline,
        revenue_feedback_rate=revenue_feedback_rate,
        cost_reduction_rate=cost_reduction_rate,
        lag_years=lag_years,
        implementation_quality=implementation_quality,
        optimism_penalty=optimism_penalty,
    )
except AssumptionError as exc:
    st.error(f"Invalid feedback assumption: **{exc}**")
    st.stop()

result = compute_fiscal(baseline, revenue_levers, investment_levers, assumptions)
projection = pd.DataFrame(result.projection)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Baseline deficit", f"£{baseline.deficit:,.0f}bn")
c2.metric("Static reform revenue", f"£{result.revenue_static:,.0f}bn")
c3.metric("New investment/spend", f"£{result.investment_static:,.0f}bn")
c4.metric(
    "Static deficit",
    f"£{result.static_deficit:,.0f}bn",
    delta=f"{result.static_deficit - baseline.deficit:+.0f}bn vs baseline",
)

last = projection.iloc[-1]
d1, d2, d3, d4 = st.columns(4)
d1.metric(f"Year {years} deficit", f"£{last['Deficit (£bn)']:,.0f}bn")
d2.metric(f"Year {years} deficit / GDP", f"{last['Deficit % GDP']:.1f}%")
d3.metric(f"Year {years} revenue feedback", f"£{last['Revenue feedback (£bn)']:,.0f}bn")
d4.metric(f"Year {years} cost reduction", f"£{last['Cost reduction (£bn)']:,.0f}bn")

st.divider()

left, right = st.columns([1, 1])

with left:
    st.subheader("Today vs static reform")
    compare = pd.DataFrame([
        {"Metric": "Receipts", "Baseline": baseline.receipts, "Scenario": result.static_receipts},
        {"Metric": "Spending", "Baseline": baseline.spending, "Scenario": result.static_spending},
        {"Metric": "Deficit", "Baseline": baseline.deficit, "Scenario": result.static_deficit},
    ])
    melted = compare.melt("Metric", var_name="Case", value_name="£bn")
    chart = alt.Chart(melted).mark_bar().encode(
        x=alt.X("Metric:N", title=None),
        y=alt.Y("£bn:Q"),
        color="Case:N",
        tooltip=["Metric", "Case", "£bn"]
    ).properties(height=340)
    st.altair_chart(chart, use_container_width=True)

with right:
    st.subheader("Projection with feedback loops")
    line_data = projection.melt(
        id_vars=["Year"],
        value_vars=["Deficit (£bn)", "Revenue feedback (£bn)", "Cost reduction (£bn)"],
        var_name="Series",
        value_name="£bn"
    )
    line = alt.Chart(line_data).mark_line(point=True).encode(
        x="Year:Q",
        y="£bn:Q",
        color="Series:N",
        tooltip=["Year", "Series", "£bn"]
    ).properties(height=340)
    st.altair_chart(line, use_container_width=True)

st.subheader("Fiscal projection table")
st.dataframe(projection, use_container_width=True)

st.subheader("Policy lever breakdown")
lever_rows = [("Revenue", name, value) for name, value in revenue_levers.items()]
lever_rows += [("Investment", name, value) for name, value in investment_levers.items()]
lever_df = pd.DataFrame(lever_rows, columns=["Type", "Lever", "£bn"])
st.dataframe(lever_df, use_container_width=True)

st.download_button(
    "Download projection CSV",
    data=projection.to_csv(index=False).encode("utf-8"),
    file_name="uk_policy_sandbox_projection.csv",
    mime="text/csv",
)
