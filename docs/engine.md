# Fiscal Engine Reference

This document is the auditable specification of the core fiscal engine in
[`model/fiscal_model.py`](../model/fiscal_model.py). Every formula below maps to
code, and the worked examples match the deterministic fixtures in
[`tests/test_fiscal_model.py`](../tests/test_fiscal_model.py).

The engine is **deterministic** (no randomness, no AI) and **Streamlit-free**.
All monetary values are **£bn/year**. All rates are **fractions** (0.35 = 35%),
never percentages.

---

## 1. Inputs

### `Baseline` (£bn/year)

| Field | Meaning | Constraint |
|---|---|---|
| `receipts` | Total government receipts | `>= 0` |
| `spending` | Total public spending | `>= 0` |
| `gdp` | Implied nominal GDP | `> 0` (it is the deficit-%-GDP denominator) |

Derived property: `deficit = spending - receipts`.

Out-of-range or **non-finite** (`nan`/`inf`) values raise `BaselineError` at
construction. The canonical values are loaded from [`baseline.csv`](../baseline.csv)
by `load_baseline()`, which validates that the required metrics — **Total
receipts**, **Total spending**, **Implied GDP** — are all present, numeric and
finite, and otherwise raises a user-facing `BaselineError`.

### `FeedbackAssumptions`

| Field | Meaning | Constraint |
|---|---|---|
| `years` | Projection horizon (years `0..N` inclusive) | `>= 1` |
| `growth_baseline` | Fractional nominal GDP growth per year | `-1.0 < g <= 1.0` |
| `revenue_feedback_rate` | Fraction of annual investment returned as receipts | `0.0..1.0` |
| `cost_reduction_rate` | Fraction of annual investment returned as lower spend | `0.0..1.0` |
| `lag_years` | Years before feedback begins | `>= 0` |
| `implementation_quality` | Delivery effectiveness | `0.0..1.0` |
| `optimism_penalty` | Haircut applied to feedback | `0.0..1.0` |

Out-of-range values raise `AssumptionError` at construction, so the engine can
never run on impossible inputs.

### Levers

`revenue_levers` and `investment_levers` are each a `Mapping[str, float]` of
lever name → £bn change. Only their **sums** affect the calculation; the keys
exist for display/breakdown.

`compute_fiscal()` validates every lever value before use: a non-numeric or
**non-finite** (`nan`/`inf`) lever raises `LeverError`. This validation lives in
the engine, not the UI, so any caller — sliders, scenario presets or a future
API — inherits the guarantee that the engine never runs on impossible inputs.

---

## 2. Static calculations (pre-feedback)

```
revenue_static   = sum(revenue_levers.values())
investment_static = sum(investment_levers.values())

static_receipts  = baseline.receipts + revenue_static
static_spending  = baseline.spending + investment_static
static_deficit   = static_spending - static_receipts
```

**Worked example** (`test_static_revenue_spending_deficit`): baseline
`receipts=1000, spending=1200`; revenue levers sum to `80`; investment levers
sum to `20`.

```
revenue_static   = 80
investment_static = 20
static_receipts  = 1000 + 80  = 1080
static_spending  = 1200 + 20  = 1220
static_deficit   = 1220 - 1080 = 140
```

---

## 3. Dynamic projection (per year `t = 0..years`)

### 3.1 GDP

```
gdp(t) = baseline.gdp * (1 + growth_baseline) ** t
```

### 3.2 Quality-adjusted return (constant across years)

```
quality_adjusted_return = implementation_quality * (1 - optimism_penalty)
```

### 3.3 Lagged, linearly ramped feedback factor

```
if t <= lag_years:
    lag_factor = 0.0
else:
    lag_factor = min(1.0, (t - lag_years) / max(1, years - lag_years))
```

Feedback is **zero during the lag**, then ramps linearly to full effect.

> **Known limitation — ramp coupling.** The ramp denominator is
> `years - lag_years`, so full effect is always reached at the **final**
> projection year. Changing the horizon therefore changes the ramp *speed*:
> with `lag_years=3`, the same policy reaches full effect at year 10, 15 or 30
> depending purely on `years`. This is a documented simplification of the v0.1
> model, not an independent ramp duration. A future `ramp_years` assumption
> would decouple ramp length from the display horizon.

### 3.4 Annual feedback amounts

```
annual_revenue_feedback = investment_static * revenue_feedback_rate
                          * quality_adjusted_return * lag_factor
annual_cost_reduction   = investment_static * cost_reduction_rate
                          * quality_adjusted_return * lag_factor
```

### 3.5 Per-year fiscal position

```
receipts(t)     = static_receipts + annual_revenue_feedback
spending(t)     = static_spending - annual_cost_reduction
deficit(t)      = spending(t) - receipts(t)
deficit_pct(t)  = deficit(t) / gdp(t) * 100
```

Each projection row reports: `Year`, `GDP (£bn)`, `Receipts (£bn)`,
`Spending (£bn)`, `Deficit (£bn)`, `Deficit % GDP`, `Revenue feedback (£bn)`,
`Cost reduction (£bn)`.

**Worked example — feedback lag** (`test_feedback_lag_behaviour`): investment
`100`, `revenue_feedback_rate=0.5`, `lag_years=2`, `years=4`,
`implementation_quality=1.0`, `optimism_penalty=0.0` ⇒
`quality_adjusted_return = 1.0`.

| Year | `lag_factor` | Revenue feedback |
|---|---|---|
| 0 | 0 (in lag) | 0 |
| 1 | 0 (in lag) | 0 |
| 2 | 0 (in lag) | 0 |
| 3 | `(3-2)/max(1,4-2)` = 0.5 | `100*0.5*1.0*0.5` = **25** |
| 4 | `(4-2)/2` = 1.0 | `100*0.5*1.0*1.0` = **50** |

---

## 4. Default-scenario regression fixture

`test_default_scenario_does_not_regress` locks the app's default slider
positions. Baseline `receipts=1232, spending=1368, gdp=3054`; revenue levers sum
to `88`; investment levers sum to `145`; assumptions `years=15`,
`growth_baseline=0.035`, `revenue_feedback_rate=0.35`, `cost_reduction_rate=0.20`,
`lag_years=3`, `implementation_quality=0.70`, `optimism_penalty=0.15`.

```
quality_adjusted_return = 0.70 * (1 - 0.15)            = 0.595
static_receipts         = 1232 + 88                    = 1320
static_spending         = 1368 + 145                   = 1513
static_deficit          = 1513 - 1320                  = 193
projection length       = 16   (years 0..15 inclusive)

Final year (t=15, lag_factor = (15-3)/(15-3) = 1.0):
  revenue feedback = 145 * 0.35 * 0.595 * 1.0          = 30.19625
  cost reduction   = 145 * 0.20 * 0.595 * 1.0          = 17.255
  deficit          = (1513 - 17.255) - (1320 + 30.19625) = 145.54875
  gdp              = 3054 * 1.035 ** 15
```

If any of these change, the regression test fails — by design.

---

## 5. Determinism guarantee

Given identical inputs, `compute_fiscal()` always returns identical outputs
(`test_compute_is_idempotent`). There is no randomness or hidden state, which is
the engine's core integrity property and the foundation for scoring (EPIC-003)
and presets (EPIC-002).
