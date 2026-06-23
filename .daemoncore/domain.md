# Domain Context — uk_policy_simulator

## Purpose

A transparent fiscal scenario sandbox for the UK. It lets a user explore how
combinations of tax/revenue reforms and public investment, together with
user-defined dynamic feedback assumptions, affect the public finances over a
multi-year horizon. It is an assumptions-exploration tool, **not** an official
or OBR-grade macroeconomic forecast.

## Domain Concepts

- **Baseline** — canonical starting fiscal position (receipts, spending, implied
  GDP), sourced from `baseline.csv`. Baseline deficit = spending − receipts.
- **Revenue levers** — £bn/year changes to receipts (e.g. income tax/NI, wealth,
  CGT/dividends, corporate, carbon/windfall, anti-avoidance).
- **Investment levers** — £bn/year changes to spending (e.g. childcare, social
  care, housing, NHS prevention, education, welfare floor, transport/energy).
- **Static figures** — baseline ± summed levers, before any dynamic feedback.
- **Dynamic feedback** — revenue feedback and cost reduction driven by the
  current annual investment level, ramped linearly after a lag and discounted by
  implementation quality and an optimism penalty. Not cumulative capital-stock
  modelling (see TODO in `model/fiscal_model.py`).

## Architectural Boundaries

- `model/fiscal_model.py` holds all calculations and baseline loading; it has no
  Streamlit dependency and is independently unit-tested.
- `app.py` is UI-only: it collects control values, calls the model, and renders.
- `baseline.csv` is the single source of truth for baseline values.

## Integration Points

- None external. Runs locally as a Streamlit app. CSV download is the only
  data export.

## Constraints

- Keep the model deterministic and testable.
- `baseline.csv` must remain the canonical baseline source; required metrics are
  Total receipts, Total spending, Implied GDP.
- Dependencies are pinned (`requirements.txt`, `requirements-dev.txt`).

## Quality Attributes

- **Correctness & reproducibility** — deterministic model, pinned deps, tests.
- **Transparency** — feedback assumptions and limitations stated honestly in UI
  and README.
- **Maintainability** — clear UI/model separation.
