# Scenario Presets

The UK Policy Sandbox ships with a small set of **scenario presets**: named,
reusable bundles of engine inputs that let you start from a coherent policy
position rather than blank sliders.

> **These presets are illustrative and human-curated.** They are reference
> points for exploration and discussion — **not** endorsements, costed policy
> proposals, forecasts or recommendations. Selecting a preset and then moving
> any slider puts the app into a **Custom** state.

## How presets work

- Each preset sets a value for **all six revenue levers**, **all seven
  investment levers** and **all seven feedback assumptions**.
- Selecting a preset populates every control deterministically. Editing any
  control switches the app to **Custom**; the **Reset to preset values** button
  returns every control to the selected preset.
- Presets live in [`scenarios.yaml`](../scenarios.yaml) and are validated on
  load (`model/scenarios.py`). The schema is versioned
  (`SCENARIO_SCHEMA_VERSION`) so presets and code cannot drift silently.

### Units

| Field | Units |
| --- | --- |
| Revenue / investment levers | £bn/year change (positive = more receipts / more spend) |
| `growth_baseline`, `*_rate`, `implementation_quality`, `optimism_penalty` | fractions (e.g. `0.035` = 3.5%) |
| `years`, `lag_years` | whole years |

The UI shows the fractional assumptions as percentages; the values stored in
`scenarios.yaml` are the engine-native fractions.

## The presets

### Baseline

No reforms — every lever is zero. The projection carries the canonical baseline
forward under the default growth assumption. This is the neutral reference point
that every other scenario is implicitly compared against. It is **not** a
"do-nothing is best" judgement; it simply isolates the baseline trajectory.

*Assumptions:* default growth (3.5%), **no** feedback (rates at 0) — with no new
investment there is nothing for feedback to act on.

### Fairness Swap

Shifts the tax base **away from earned income** (a cut to income tax / NI) and
**towards wealth, property and passive income**, with modest social investment
on top. Net revenue is positive. It explores the trade-offs of a "swap" rather
than asserting it is fairer in any objective sense.

*Assumptions:* moderate feedback (revenue 30%, cost 15%), 3-year lag, quality
0.70, optimism penalty 0.15.

### Social Investment

A broad public-investment programme — childcare, housing, NHS capacity,
education and infrastructure — part-funded by tax reform. Run on the assumption
that investment generates meaningful revenue feedback and cost reduction over a
longer (20-year) horizon. The feedback assumptions are deliberately optimistic
so the trade-offs can be examined honestly.

*Assumptions:* higher feedback (revenue 40%, cost 25%), 4-year lag, quality
0.70, optimism penalty 0.15.

### Deficit Repair

A revenue-led consolidation: broad-based tax rises with **no** new spending,
aimed at narrowing the static deficit. Feedback is assumed to be weak,
reflecting the view that tax-led consolidation does little to stimulate
activity.

*Assumptions:* weak feedback (revenue 20%, cost 10%), short 2-year lag, quality
0.75, optimism penalty 0.10.

### Universal Basic Services

A large expansion of universal public services across childcare, social care,
housing, health, education and transport, funded by substantial tax reform. A
high-tax, high-spend frontier scenario for exploring how far the service-led
model can be pushed before the deficit dominates.

*Assumptions:* strong feedback (revenue 45%, cost 30%) but a long 5-year lag and
a lower quality (0.65) / higher optimism penalty (0.20) reflecting delivery risk
at scale.

### UBI Experiment

A stylised Universal Basic Income: the welfare floor is raised to its maximum
and funded by large, broad-based tax rises. Feedback is modest and uncertain.
This is a thought experiment for examining the **fiscal scale** of UBI, not a
costed UBI design.

*Assumptions:* modest feedback (revenue 25%, cost 20%), 4-year lag, lower
quality (0.60) and a high optimism penalty (0.25).

### Austerity Trap

Tax cuts with **no** new investment, combined with weak growth and weak feedback
— a scenario for exploring the "trap" where cuts fail to pay for themselves and
the deficit widens. The pessimistic settings are deliberate, to contrast with
the investment-led presets.

*Assumptions:* lower growth (2.5%), weak feedback (revenue 10%, cost 5%), low
quality (0.50) and a high optimism penalty (0.30).

## Adding or editing a preset

1. Edit [`scenarios.yaml`](../scenarios.yaml). Keep `schema_version` in step with
   `SCENARIO_SCHEMA_VERSION` in `model/scenarios.py`.
2. Set **every** revenue lever, investment lever and assumption — missing or
   unknown keys are rejected with an actionable error.
3. Keep summaries neutral and caveated.
4. Run `pytest` — `tests/test_scenarios.py` loads every preset and asserts it
   runs to finite, expected-shape output.
