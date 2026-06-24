
# UK Policy Sandbox

An interactive Streamlit app for modelling simplified UK fiscal reform scenarios.

## What it models

- Baseline UK receipts and public spending
- Tax reform levers
- Social investment levers
- Dynamic feedback assumptions:
  - revenue feedback from improved earnings/spending/productivity
  - cost reduction from lower welfare/NHS/social crisis demand
  - implementation quality
  - optimism penalty
  - delayed policy effects

## How the feedback model works (honest description)

The dynamic feedback is deliberately simple and you should read it as such:

- Feedback is modelled as an **annual** effect proportional to the **current
  annual investment level** — not as a cumulative capital stock.
- It is **linearly ramped in** after the configured lag (no effect during the
  lag period, then a straight-line ramp to full effect).
- It is therefore **not** cumulative capital-stock / lifecycle modelling.

> **TODO:** replace the flat annual-investment feedback with cumulative
> capital-stock / lifecycle modelling — depreciation and compounding returns on
> the accumulated stock rather than on the current-year flow.

## Important caveat

This is not an official macroeconomic model. It is a transparent scenario sandbox for exploring assumptions.

## Baseline source of truth

`baseline.csv` is the **canonical source** for baseline fiscal values. It is
loaded and validated at app startup; the required metrics are **Total
receipts**, **Total spending**, and **Implied GDP**. If the file is missing or
invalid, the app fails clearly in the UI rather than falling back to hidden
constants.

## Baseline sources

- OBR public finances guide: 2025/26 public spending around £1,368bn, 44.8% of national income.
- House of Commons Library tax statistics overview, June 2026: 2025/26 receipts around £1,232bn.

## Run locally

```bash
# Create a virtual environment (use whichever Python launcher you have):
python3 -m venv .venv      # macOS / Linux
python -m venv .venv       # Windows, or where `python` is Python 3

source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Suggested next improvements

- Replace coarse defaults with full OBR / HMRC line-item imports.
- Add household distribution modelling by income decile.
- Add age cohorts and lifetime earnings effects.
- Add uncertainty bands / Monte Carlo simulation.
- Add named scenarios: Baseline, Progressive Redistribution, Social Investment, UBI, Deficit Repair.
