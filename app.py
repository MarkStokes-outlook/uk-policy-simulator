
from pathlib import Path

import streamlit as st
import pandas as pd
import altair as alt

from model import (
    AssumptionError,
    BaselineError,
    FeedbackAssumptions,
    Scenario,
    ScenarioError,
    compute_fiscal,
    load_baseline,
    load_scenarios,
)

st.set_page_config(
    page_title="UK Policy Sandbox",
    page_icon="🇬🇧",
    layout="wide",
)

BASELINE_PATH = Path(__file__).parent / "baseline.csv"
SCENARIOS_PATH = Path(__file__).parent / "scenarios.yaml"

# Lever display metadata, keyed by the canonical scenario key so presets,
# sliders and the engine all agree. Tuple: (key, label, min, max, step).
REVENUE_LEVER_SPECS = [
    ("income_tax_ni", "Income tax / NI reform net yield", -50.0, 80.0, 1.0),
    ("wealth_property", "Wealth / land / property tax reform", -20.0, 100.0, 1.0),
    ("passive_income", "CGT / dividends / rent equalisation", -10.0, 60.0, 1.0),
    ("corporate", "Corporate / rent-seeking tax tightening", -20.0, 60.0, 1.0),
    ("carbon_windfall", "Carbon / resource / windfall taxes", -20.0, 60.0, 1.0),
    ("anti_avoidance", "Compliance / anti-avoidance yield", 0.0, 40.0, 1.0),
]
INVESTMENT_LEVER_SPECS = [
    ("childcare", "Childcare expansion", 0.0, 60.0, 1.0),
    ("social_care", "Social care settlement", 0.0, 60.0, 1.0),
    ("housing", "Housing / social build programme", 0.0, 100.0, 1.0),
    ("nhs_prevention", "NHS prevention + capacity", 0.0, 60.0, 1.0),
    ("education_training", "Higher education / adult training", 0.0, 60.0, 1.0),
    ("welfare_floor", "Welfare floor / taper smoothing", 0.0, 60.0, 1.0),
    ("transport_energy", "Transport / energy infrastructure", 0.0, 100.0, 1.0),
]


def _scenario_to_state(scenario: Scenario) -> dict:
    """Map a scenario onto the session-state keys the sidebar widgets use.

    Lever values are engine-native £bn; assumptions are converted to the
    sliders' display units (percentages) so the widgets show them directly.
    """
    a = scenario.assumptions
    state: dict = {}
    state.update(scenario.revenue_levers)
    state.update(scenario.investment_levers)
    state["years"] = a.years
    state["lag_years"] = a.lag_years
    state["growth_pct"] = round(a.growth_baseline * 100, 4)
    state["rev_fb_pct"] = round(a.revenue_feedback_rate * 100, 4)
    state["cost_red_pct"] = round(a.cost_reduction_rate * 100, 4)
    state["impl_quality_pct"] = round(a.implementation_quality * 100, 4)
    state["optimism_pct"] = round(a.optimism_penalty * 100, 4)
    return state

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

# --- Scenario presets (EPIC-002) -----------------------------------------
# scenarios.yaml is validated on load; fail clearly in the UI rather than
# silently running with a broken or missing preset set.
try:
    SCENARIOS = load_scenarios(SCENARIOS_PATH)
except ScenarioError as exc:
    st.error(
        f"Could not load scenario presets from `{SCENARIOS_PATH.name}`.\n\n"
        f"**{exc}**\n\n"
        "Fix the scenario file and reload."
    )
    st.stop()

scenario_ids = list(SCENARIOS)


def _apply_selected_scenario() -> None:
    """Populate every slider's session-state from the chosen preset.

    Run as the selectbox ``on_change`` callback (and from the reset button), so
    it executes before the widgets are instantiated on the next rerun — which is
    the only point at which a widget-keyed session-state value may be set.
    """
    chosen = SCENARIOS[st.session_state["scenario_select"]]
    for key, value in _scenario_to_state(chosen).items():
        st.session_state[key] = value


# On the very first run, seed session-state from the first preset before any
# slider widget exists. Selecting a preset later goes through the callback.
if "scenario_select" not in st.session_state:
    st.session_state["scenario_select"] = scenario_ids[0]
    for _k, _v in _scenario_to_state(SCENARIOS[scenario_ids[0]]).items():
        st.session_state[_k] = _v

st.sidebar.header("Scenario controls")

selected_id = st.sidebar.selectbox(
    "Scenario preset",
    scenario_ids,
    format_func=lambda i: SCENARIOS[i].name,
    key="scenario_select",
    on_change=_apply_selected_scenario,
)
selected_scenario = SCENARIOS[selected_id]

st.sidebar.subheader("Revenue reforms")
for key, label, lo, hi, step in REVENUE_LEVER_SPECS:
    st.sidebar.slider(label, lo, hi, step=step, key=key)

st.sidebar.subheader("Investment / spending reforms")
for key, label, lo, hi, step in INVESTMENT_LEVER_SPECS:
    st.sidebar.slider(label, lo, hi, step=step, key=key)

st.sidebar.subheader("Dynamic feedback assumptions")
st.sidebar.slider("Projection years", 5, 30, step=1, key="years")
st.sidebar.slider("Baseline nominal GDP growth (%)", 0.0, 6.0, step=0.1, key="growth_pct")
st.sidebar.slider("Revenue feedback from investment (%)", 0.0, 100.0, step=1.0, key="rev_fb_pct")
st.sidebar.slider("Public cost reduction from social investment (%)", 0.0, 100.0, step=1.0, key="cost_red_pct")
st.sidebar.slider("Feedback lag years", 0, 10, step=1, key="lag_years")
st.sidebar.slider("Implementation quality (%)", 0.0, 100.0, step=1.0, key="impl_quality_pct")
st.sidebar.slider("Optimism penalty (%)", 0.0, 50.0, step=1.0, key="optimism_pct")

# Assumption scalars converted back to engine-native fractions.
years = st.session_state["years"]
lag_years = st.session_state["lag_years"]
growth_baseline = st.session_state["growth_pct"] / 100
revenue_feedback_rate = st.session_state["rev_fb_pct"] / 100
cost_reduction_rate = st.session_state["cost_red_pct"] / 100
implementation_quality = st.session_state["impl_quality_pct"] / 100
optimism_penalty = st.session_state["optimism_pct"] / 100

# Lever values keyed by display label so the same mapping drives both the
# calculation and the lever breakdown table below.
revenue_levers = {label: st.session_state[key] for key, label, *_ in REVENUE_LEVER_SPECS}
investment_levers = {label: st.session_state[key] for key, label, *_ in INVESTMENT_LEVER_SPECS}

# "Custom" state: once the live controls diverge from the selected preset, say
# so explicitly and offer a deterministic reset back to the preset values.
_expected = _scenario_to_state(selected_scenario)
_current = {key: st.session_state[key] for key in _expected}
is_custom = any(abs(_current[k] - _expected[k]) > 1e-9 for k in _expected)

if is_custom:
    st.sidebar.caption(f"⚠️ Custom — modified from **{selected_scenario.name}**")
else:
    st.sidebar.caption(f"Preset: **{selected_scenario.name}** (unmodified)")

st.sidebar.button(
    "Reset to preset values",
    on_click=_apply_selected_scenario,
    disabled=not is_custom,
    use_container_width=True,
)

with st.sidebar.expander("About this scenario", expanded=True):
    st.markdown(selected_scenario.summary)
    st.caption(
        "Presets are illustrative, human-curated starting points — not "
        "endorsements, forecasts or recommendations."
    )

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
