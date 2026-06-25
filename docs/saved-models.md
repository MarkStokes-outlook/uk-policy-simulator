# Saved Models

From v1.0, the UK Policy Sandbox can **save the current scenario as a named
model** that persists across sessions, with a full **version history**. This is
the first step towards persistent, shareable policy proposals.

> **Saved models are local user data.** They live in a JSON file
> (`saved_models.json`) on the machine running the app and are **gitignored** —
> they are not part of the source tree. Multi-user accounts, sharing and
> collaboration come later in the roadmap (v1.1+).

## What you can do

| Action | Effect |
| --- | --- |
| **Save current as new model** | Captures every lever and assumption as a new model at **version 1** |
| **Load** | Replaces the live controls with the selected model's current version |
| **Update** | Appends a **new version** to the selected model (history is kept) |
| **Clone** | Copies the selected model's current version into a brand-new model |
| **Delete** | Removes the selected model |
| **History** | Shows every version of the selected model, newest first |

A model bundles exactly the same inputs as a scenario preset: all six revenue
levers, all seven investment levers and the seven feedback assumptions.

## Version history

Saving over an existing model never overwrites it — **Update** appends a new
version. Each version records its number, an ISO-8601 timestamp and an optional
note, so a proposal's evolution stays auditable. **Load** always restores a
model's latest version; **Clone** copies the latest version into a fresh model
that starts its own history at version 1.

## Where models are stored

- Default path: `saved_models.json` in the app directory.
- Versioned schema (`SAVED_MODELS_SCHEMA_VERSION` in
  [`model/saved_models.py`](../model/saved_models.py)); the store refuses files
  whose schema version it does not understand and validates every model on read.
- Writes are atomic (temp file + replace) so an interrupted save cannot truncate
  an existing store.
- Model ids are human-readable slugs of the name (`My Plan` → `my-plan`), with a
  numeric suffix on collision (`my-plan-2`). No random ids — a given sequence of
  operations is reproducible.

## Using the store directly

`ModelStore` is Streamlit-free and can be driven from any Python code or future
API. A `now` callable can be injected for deterministic timestamps in tests.

```python
from model import ModelStore, FeedbackAssumptions

store = ModelStore("saved_models.json")
rev = {"income_tax_ni": 0.0, "wealth_property": 20.0, "passive_income": 0.0,
       "corporate": 0.0, "carbon_windfall": 0.0, "anti_avoidance": 0.0}
inv = {"childcare": 0.0, "social_care": 0.0, "housing": 30.0,
       "nhs_prevention": 0.0, "education_training": 0.0,
       "welfare_floor": 0.0, "transport_energy": 0.0}
assumptions = FeedbackAssumptions(
    years=10, growth_baseline=0.035, revenue_feedback_rate=0.3,
    cost_reduction_rate=0.2, lag_years=2,
    implementation_quality=0.7, optimism_penalty=0.2,
)

model = store.create("My Plan", rev, inv, assumptions, note="first cut")
store.update(model.id, rev, {**inv, "housing": 45.0}, assumptions, note="more housing")
print([(v.version, v.note) for v in store.get(model.id).versions])
clone = store.clone(model.id, "My Plan (variant)")
store.delete(clone.id)
```
