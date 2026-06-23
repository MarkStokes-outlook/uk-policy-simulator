
import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="UK Policy Sandbox",
    page_icon="🇬🇧",
    layout="wide",
)

BASELINE = {
    "year": "2025/26-ish baseline",
    "receipts": 1232.0,
    "spending": 1368.0,
    "gdp": 3054.0,
}

st.title("🇬🇧 UK Policy Sandbox")
st.caption(
    "A simplified fiscal and socio-economic simulator. All numbers are approximate £bn/year. "
    "It is designed for scenario exploration, not official forecasting."
)

with st.expander("Model notes", expanded=False):
    st.markdown("""
**Baseline defaults**

- Total receipts: £1,232bn.
- Total public spending: £1,368bn.
- Baseline deficit: £136bn.
- GDP is inferred from £1,368bn being 44.8% of national income.

**Important limitations**

- This is a transparent model, not an OBR-grade macroeconomic model.
- Feedback effects are user-defined assumptions.
- Behavioural responses, inflation, migration, global shocks, interest-rate effects and distributional detail are not yet fully modelled.
""")

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

revenue_static = sum([
    income_tax_ni_reform,
    wealth_tax_reform,
    passive_income_reform,
    corporate_tax_reform,
    carbon_resource_tax,
    anti_avoidance,
])

investment_static = sum([
    childcare,
    social_care,
    housing,
    nhs_prevention,
    education_training,
    welfare_floor,
    transport_energy,
])

baseline_deficit = BASELINE["spending"] - BASELINE["receipts"]
static_receipts = BASELINE["receipts"] + revenue_static
static_spending = BASELINE["spending"] + investment_static
static_deficit = static_spending - static_receipts

investment_productive = investment_static
quality_adjusted_return = implementation_quality * (1 - optimism_penalty)

rows = []
for year in range(0, years + 1):
    gdp = BASELINE["gdp"] * ((1 + growth_baseline) ** year)
    lag_factor = 0 if year <= lag_years else min(1, (year - lag_years) / max(1, years - lag_years))

    annual_revenue_feedback = investment_productive * revenue_feedback_rate * quality_adjusted_return * lag_factor
    annual_cost_reduction = investment_productive * cost_reduction_rate * quality_adjusted_return * lag_factor

    receipts = static_receipts + annual_revenue_feedback
    spending = static_spending - annual_cost_reduction
    deficit = spending - receipts

    rows.append({
        "Year": year,
        "GDP (£bn)": gdp,
        "Receipts (£bn)": receipts,
        "Spending (£bn)": spending,
        "Deficit (£bn)": deficit,
        "Deficit % GDP": deficit / gdp * 100,
        "Revenue feedback (£bn)": annual_revenue_feedback,
        "Cost reduction (£bn)": annual_cost_reduction,
    })

projection = pd.DataFrame(rows)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Baseline deficit", f"£{baseline_deficit:,.0f}bn")
c2.metric("Static reform revenue", f"£{revenue_static:,.0f}bn")
c3.metric("New investment/spend", f"£{investment_static:,.0f}bn")
c4.metric("Static deficit", f"£{static_deficit:,.0f}bn", delta=f"{static_deficit - baseline_deficit:+.0f}bn vs baseline")

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
        {"Metric": "Receipts", "Baseline": BASELINE["receipts"], "Scenario": static_receipts},
        {"Metric": "Spending", "Baseline": BASELINE["spending"], "Scenario": static_spending},
        {"Metric": "Deficit", "Baseline": baseline_deficit, "Scenario": static_deficit},
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
lever_rows = [
    ("Revenue", "Income tax / NI reform", income_tax_ni_reform),
    ("Revenue", "Wealth / land / property reform", wealth_tax_reform),
    ("Revenue", "Passive income equalisation", passive_income_reform),
    ("Revenue", "Corporate / rent-seeking tax", corporate_tax_reform),
    ("Revenue", "Carbon / resource / windfall taxes", carbon_resource_tax),
    ("Revenue", "Compliance / anti-avoidance", anti_avoidance),
    ("Investment", "Childcare expansion", childcare),
    ("Investment", "Social care settlement", social_care),
    ("Investment", "Housing / social build", housing),
    ("Investment", "NHS prevention + capacity", nhs_prevention),
    ("Investment", "Higher education / adult training", education_training),
    ("Investment", "Welfare floor / taper smoothing", welfare_floor),
    ("Investment", "Transport / energy infrastructure", transport_energy),
]
lever_df = pd.DataFrame(lever_rows, columns=["Type", "Lever", "£bn"])
st.dataframe(lever_df, use_container_width=True)

st.download_button(
    "Download projection CSV",
    data=projection.to_csv(index=False).encode("utf-8"),
    file_name="uk_policy_sandbox_projection.csv",
    mime="text/csv",
)
