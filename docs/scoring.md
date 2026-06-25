# Deterministic Scoring

The UK Policy Sandbox scores every scenario against **seven policy categories**
on a 0–100 scale, then combines them into a single **overall** score using a
**weighting profile**.

> **These scores are transparent heuristics for exploration — not forecasts,
> costings or recommendations.** There is no AI and no randomness in the scoring
> path: identical inputs always produce identical scores. The category scores
> are *objective and directional*; the *priorities* (which categories matter,
> and how much) live entirely in configurable weighting profiles.

## The seven categories

| Category | What "100" means | How it's computed |
| --- | --- | --- |
| **Fiscal Sustainability** | Lower deficit as a share of GDP | Engine's final-year deficit/GDP, scored on a band from −3% (= 100) to +9% (= 0) |
| **Economic Growth** | Stronger modelled growth/capacity effect | Contribution matrix |
| **Poverty Reduction** | Larger modelled reduction in poverty | Contribution matrix |
| **Housing Affordability** | Larger modelled improvement in affordability | Contribution matrix |
| **NHS Demand Impact** | Larger modelled reduction in avoidable NHS demand | Contribution matrix |
| **Income Equality** | More progressive net effect on income distribution | Contribution matrix |
| **Implementation Complexity** | **Easy to deliver (low complexity)**; 0 = very complex | Size and breadth of the change |

Every category is defined so that **100 is the more favourable end of that
axis**. For Implementation Complexity that means a high score is *good* (simple
to deliver), so the overall weighted score combines all seven uniformly.

## How the scores are calculated

Scoring lives in [`model/scoring.py`](../model/scoring.py); it is Streamlit-free
and independently unit-tested.

### Fiscal Sustainability — straight from the engine

This is the one category taken directly from the deterministic fiscal engine:
the projection's **final-year deficit as a percentage of GDP**, mapped linearly
onto 0–100 (clamped) between `FISCAL_SUSTAINABLE_PCT` (−3%) and
`FISCAL_UNSUSTAINABLE_PCT` (+9%). It therefore already reflects all levers and
the dynamic feedback.

### The five outcome categories — a published contribution matrix

Economic Growth, Poverty Reduction, Housing Affordability, NHS Demand Impact and
Income Equality are scored from a **published, signed contribution matrix**
(`CONTRIBUTIONS` in `model/scoring.py`): a coefficient in **score points per
£bn/year** for each lever, per category.

- A do-nothing scenario sits at the neutral midpoint of **50** on each axis.
- Each active lever moves the score by `coefficient × £bn`, summed and then
  clamped to 0–100.
- Because every coefficient is published, any score can be explained lever by
  lever — there is **no black box**. The app's *"How each score was calculated"*
  panel shows the top drivers for each category.

These coefficients are **illustrative, human-curated directional links** (e.g.
welfare-floor spending advances poverty reduction; a land/property tax improves
housing affordability). They are deliberately simple and open to challenge, not
calibrated econometric estimates.

### Implementation Complexity — size and breadth of change

Starts at **100** (doing nothing is trivial) and subtracts:

- `COMPLEXITY_PER_BN` (0.25) points per £bn of **gross** absolute change, and
- `COMPLEXITY_PER_ACTIVE_LEVER` (2.0) points per lever moved off zero,

clamped to 0–100. A large programme spread across many levers therefore scores
low (more complex to deliver).

## Weighting profiles — where priorities live

The overall score is a **weighted average** of the seven category scores. The
weights come from a **weighting profile**, and this is the only place subjective
priorities enter scoring.

Profiles live in [`weighting_profiles.yaml`](../weighting_profiles.yaml), a
versioned, validated schema (`WEIGHTING_SCHEMA_VERSION`). Weights may be any
non-negative numbers (here, 0–5 importance ratings); they are normalised to sum
to 1 when applied.

The app ships five deliberately diverse profiles:

| Profile | Emphasis |
| --- | --- |
| **Balanced** (default) | All categories equal — the neutral reference |
| **Fiscal Conservative** | Fiscal sustainability, growth, low complexity |
| **Social Democratic** | Poverty reduction, income equality, NHS demand |
| **Green Investment** | Growth-enabling investment, housing, NHS prevention |
| **Libertarian** | Fiscal sustainability, growth, minimal/simple intervention |

> **No profile is "objectively correct".** They exist so you can see how the
> overall score shifts with priorities — and build your own. The platform
> deliberately refuses to present any single profile as the right one.

## Trust classification

Under the project's evidence framework (see
[`vision-and-roadmap.md`](vision-and-roadmap.md)):

- **Fiscal Sustainability** derives from the deterministic engine and the
  canonical baseline (Class A inputs), though the 0–100 banding is a presentation
  choice.
- The **five outcome categories** and **Implementation Complexity** are
  **illustrative (Class C-leaning) heuristics**: transparent and deterministic,
  but not evidence-calibrated. They must not be read as predictions.

## Reproducing a score

```python
from model import (
    Baseline, FeedbackAssumptions, compute_fiscal,
    score_categories, build_scorecard, load_weighting_profiles,
)

baseline = Baseline(receipts=1100.0, spending=1230.0, gdp=2700.0)
assumptions = FeedbackAssumptions(
    years=10, growth_baseline=0.035, revenue_feedback_rate=0.3,
    cost_reduction_rate=0.2, lag_years=2,
    implementation_quality=0.7, optimism_penalty=0.2,
)
revenue = {"income_tax_ni": 0.0, "wealth_property": 0.0, "passive_income": 0.0,
           "corporate": 0.0, "carbon_windfall": 0.0, "anti_avoidance": 0.0}
investment = {"childcare": 0.0, "social_care": 0.0, "housing": 40.0,
              "nhs_prevention": 0.0, "education_training": 0.0,
              "welfare_floor": 25.0, "transport_energy": 0.0}

result = compute_fiscal(baseline, revenue, investment, assumptions)
scores = score_categories(baseline, result, revenue, investment)
profiles = load_weighting_profiles("weighting_profiles.yaml")
card = build_scorecard(scores, profiles["balanced"])
print(card.overall, {k: round(v.score, 1) for k, v in scores.items()})
```
