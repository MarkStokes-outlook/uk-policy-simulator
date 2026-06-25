
from pathlib import Path

import streamlit as st
import pandas as pd
import altair as alt

from model import (
    AssumptionError,
    BaselineError,
    FeedbackAssumptions,
    ModelStore,
    ModelStoreError,
    Scenario,
    ScenarioError,
    ScoringError,
    build_scorecard,
    compute_fiscal,
    load_baseline,
    load_scenarios,
    load_weighting_profiles,
    score_categories,
)

st.set_page_config(
    page_title="UK Policy Sandbox",
    page_icon="🇬🇧",
    layout="wide",
)

BASELINE_PATH = Path(__file__).parent / "baseline.csv"
SCENARIOS_PATH = Path(__file__).parent / "scenarios.yaml"
WEIGHTING_PATH = Path(__file__).parent / "weighting_profiles.yaml"
# User-created saved models persist here (gitignored — it is user data).
SAVED_MODELS_PATH = Path(__file__).parent / "saved_models.json"

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


def _inputs_to_state(revenue_levers, investment_levers, assumptions) -> dict:
    """Map engine inputs onto the session-state keys the sidebar widgets use.

    Lever values are engine-native £bn; assumptions are converted to the
    sliders' display units (percentages) so the widgets show them directly.
    Shared by scenario presets and saved models, which have the same shape.
    """
    a = assumptions
    state: dict = {}
    state.update(revenue_levers)
    state.update(investment_levers)
    state["years"] = a.years
    state["lag_years"] = a.lag_years
    state["growth_pct"] = round(a.growth_baseline * 100, 4)
    state["rev_fb_pct"] = round(a.revenue_feedback_rate * 100, 4)
    state["cost_red_pct"] = round(a.cost_reduction_rate * 100, 4)
    state["impl_quality_pct"] = round(a.implementation_quality * 100, 4)
    state["optimism_pct"] = round(a.optimism_penalty * 100, 4)
    return state


def _scenario_to_state(scenario: Scenario) -> dict:
    """Map a scenario preset onto the sidebar widgets' session-state keys."""
    return _inputs_to_state(
        scenario.revenue_levers, scenario.investment_levers, scenario.assumptions
    )

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

# --- Weighting profiles (EPIC-003) ---------------------------------------
# weighting_profiles.yaml is validated on load; fail clearly rather than scoring
# against a broken or missing set of priorities.
try:
    WEIGHTING_PROFILES = load_weighting_profiles(WEIGHTING_PATH)
except ScoringError as exc:
    st.error(
        f"Could not load weighting profiles from `{WEIGHTING_PATH.name}`.\n\n"
        f"**{exc}**\n\n"
        "Fix the weighting file and reload."
    )
    st.stop()

profile_ids = list(WEIGHTING_PROFILES)

# --- Saved models (EPIC-004 / v1.0) --------------------------------------
# A file-backed store of user-created, named models with version history.
store = ModelStore(SAVED_MODELS_PATH)


def _set_models_msg(level: str, text: str) -> None:
    """Stash a message for the saved-models panel (callbacks cannot render)."""
    st.session_state["_models_msg"] = (level, text)


def _current_inputs():
    """Read the live controls as engine-native inputs (canonical lever keys)."""
    rev = {key: st.session_state[key] for key, *_ in REVENUE_LEVER_SPECS}
    inv = {key: st.session_state[key] for key, *_ in INVESTMENT_LEVER_SPECS}
    a = FeedbackAssumptions(
        years=st.session_state["years"],
        growth_baseline=st.session_state["growth_pct"] / 100,
        revenue_feedback_rate=st.session_state["rev_fb_pct"] / 100,
        cost_reduction_rate=st.session_state["cost_red_pct"] / 100,
        lag_years=st.session_state["lag_years"],
        implementation_quality=st.session_state["impl_quality_pct"] / 100,
        optimism_penalty=st.session_state["optimism_pct"] / 100,
    )
    return rev, inv, a


def _cb_save_new_model() -> None:
    name = (st.session_state.get("new_model_name") or "").strip()
    if not name:
        _set_models_msg("warning", "Enter a name to save the current scenario.")
        return
    try:
        rev, inv, a = _current_inputs()
        model = store.create(name, rev, inv, a, note=(st.session_state.get("model_note") or "").strip())
    except (ModelStoreError, AssumptionError) as exc:
        _set_models_msg("error", f"Could not save: {exc}")
        return
    st.session_state["saved_model_select"] = model.id
    st.session_state["new_model_name"] = ""
    _set_models_msg("success", f"Saved '{model.name}' (v{model.current.version}).")


def _cb_load_selected_model() -> None:
    mid = st.session_state.get("saved_model_select")
    if not mid:
        return
    try:
        model = store.get(mid)
    except ModelStoreError as exc:
        _set_models_msg("error", f"Could not load: {exc}")
        return
    cur = model.current
    for key, value in _inputs_to_state(
        cur.revenue_levers, cur.investment_levers, cur.assumptions
    ).items():
        st.session_state[key] = value
    _set_models_msg("success", f"Loaded '{model.name}' (v{cur.version}).")


def _cb_update_selected_model() -> None:
    mid = st.session_state.get("saved_model_select")
    if not mid:
        return
    try:
        rev, inv, a = _current_inputs()
        model = store.update(mid, rev, inv, a, note=(st.session_state.get("model_note") or "").strip())
    except (ModelStoreError, AssumptionError) as exc:
        _set_models_msg("error", f"Could not update: {exc}")
        return
    _set_models_msg("success", f"Updated '{model.name}' to v{model.current.version}.")


def _cb_clone_selected_model() -> None:
    mid = st.session_state.get("saved_model_select")
    if not mid:
        return
    try:
        source = store.get(mid)
        clone = store.clone(mid, f"{source.name} copy")
    except ModelStoreError as exc:
        _set_models_msg("error", f"Could not clone: {exc}")
        return
    st.session_state["saved_model_select"] = clone.id
    _set_models_msg("success", f"Cloned to '{clone.name}'.")


def _cb_delete_selected_model() -> None:
    mid = st.session_state.get("saved_model_select")
    if not mid:
        return
    try:
        name = store.get(mid).name
        store.delete(mid)
    except ModelStoreError as exc:
        _set_models_msg("error", f"Could not delete: {exc}")
        return
    st.session_state.pop("saved_model_select", None)
    _set_models_msg("success", f"Deleted '{name}'.")


try:
    saved_models = store.list_models()
except ModelStoreError as exc:
    st.error(
        f"Could not read saved models from `{SAVED_MODELS_PATH.name}`.\n\n"
        f"**{exc}**\n\nFix or remove the file and reload."
    )
    st.stop()
saved_model_ids = [m.id for m in saved_models]
saved_models_by_id = {m.id: m for m in saved_models}


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

st.sidebar.subheader("Scoring")
selected_profile_id = st.sidebar.selectbox(
    "Weighting profile",
    profile_ids,
    format_func=lambda i: WEIGHTING_PROFILES[i].name,
    key="weighting_select",
)
selected_profile = WEIGHTING_PROFILES[selected_profile_id]
st.sidebar.caption(selected_profile.summary)

# --- Saved models panel ---------------------------------------------------
st.sidebar.subheader("Saved models")

_models_msg = st.session_state.pop("_models_msg", None)
if _models_msg:
    getattr(st.sidebar, _models_msg[0], st.sidebar.info)(_models_msg[1])

st.sidebar.text_input("New model name", key="new_model_name", placeholder="e.g. My reform plan")
st.sidebar.text_input("Note (optional)", key="model_note", placeholder="what changed / why")
st.sidebar.button(
    "💾 Save current as new model",
    on_click=_cb_save_new_model,
    use_container_width=True,
)

if saved_model_ids:
    st.sidebar.selectbox(
        "Saved model",
        saved_model_ids,
        format_func=lambda i: saved_models_by_id[i].name,
        key="saved_model_select",
    )
    mc1, mc2 = st.sidebar.columns(2)
    mc1.button("📂 Load", on_click=_cb_load_selected_model, use_container_width=True)
    mc2.button("⬆️ Update", on_click=_cb_update_selected_model, use_container_width=True)
    mc3, mc4 = st.sidebar.columns(2)
    mc3.button("⧉ Clone", on_click=_cb_clone_selected_model, use_container_width=True)
    mc4.button("🗑 Delete", on_click=_cb_delete_selected_model, use_container_width=True)

    _sel = saved_models_by_id.get(st.session_state.get("saved_model_select"))
    if _sel is not None:
        with st.sidebar.expander(f"History — {_sel.name} ({len(_sel.versions)} version(s))"):
            for v in reversed(_sel.versions):
                note = f" — {v.note}" if v.note else ""
                st.caption(f"**v{v.version}** · {v.saved_at}{note}")
else:
    st.sidebar.caption("No saved models yet. Save the current scenario to start.")

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

# Deterministic scoring (EPIC-003). Scores need lever values keyed by the
# canonical scenario keys, which are exactly the session-state slider keys.
scoring_revenue = {key: st.session_state[key] for key, *_ in REVENUE_LEVER_SPECS}
scoring_investment = {key: st.session_state[key] for key, *_ in INVESTMENT_LEVER_SPECS}
category_scores = score_categories(
    baseline, result, scoring_revenue, scoring_investment
)
try:
    scorecard = build_scorecard(category_scores, selected_profile)
except ScoringError as exc:
    st.error(f"Could not score this scenario: **{exc}**")
    st.stop()

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

st.subheader("Policy scores")
st.caption(
    f"Deterministic 0–100 scores (higher = more favourable on each axis), combined "
    f"into an overall using the **{selected_profile.name}** weighting profile. "
    "Scores are deterministic, transparent heuristics for exploration, not forecasts: "
    "the category formulas are fixed and directionally defined, but the underlying "
    "coefficients and penalties are human-curated model assumptions. The weighting "
    "profile carries the priorities."
)

s_overall, s_chart = st.columns([1, 3])
with s_overall:
    st.metric("Overall (weighted)", f"{scorecard.overall:.0f}/100")
    st.caption(f"Profile: **{selected_profile.name}**")
with s_chart:
    score_df = pd.DataFrame(
        [{"Category": c.label, "Score": c.score} for c in category_scores.values()]
    )
    score_chart = alt.Chart(score_df).mark_bar().encode(
        x=alt.X("Score:Q", scale=alt.Scale(domain=[0, 100]), title="Score (0–100)"),
        y=alt.Y("Category:N", sort=None, title=None),
        tooltip=["Category", alt.Tooltip("Score:Q", format=".0f")],
    ).properties(height=240)
    st.altair_chart(score_chart, use_container_width=True)

with st.expander("How each score was calculated", expanded=False):
    breakdown = pd.DataFrame(
        [
            {
                "Category": c.label,
                "Score": round(c.score, 1),
                "What 100 means": c.direction,
                "Why this score": c.rationale,
            }
            for c in category_scores.values()
        ]
    )
    st.dataframe(breakdown, use_container_width=True, hide_index=True)
    st.caption(
        "Outcome categories use a published per-£bn contribution matrix "
        "(`model/scoring.py`); Fiscal Sustainability comes straight from the "
        "engine's final-year deficit/GDP. No AI is involved."
    )

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

dl1, dl2 = st.columns(2)
dl1.download_button(
    "Download projection CSV",
    data=projection.to_csv(index=False).encode("utf-8"),
    file_name="uk_policy_sandbox_projection.csv",
    mime="text/csv",
)
score_export = pd.DataFrame(
    [
        {
            "Category": c.label,
            "Score": round(c.score, 1),
            "Weight": selected_profile.weights[c.key],
            "Rationale": c.rationale,
        }
        for c in category_scores.values()
    ]
)
dl2.download_button(
    f"Download scores CSV ({selected_profile.name})",
    data=score_export.to_csv(index=False).encode("utf-8"),
    file_name="uk_policy_sandbox_scores.csv",
    mime="text/csv",
)
