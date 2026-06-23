
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

## Important caveat

This is not an official macroeconomic model. It is a transparent scenario sandbox for exploring assumptions.

## Baseline sources

- OBR public finances guide: 2025/26 public spending around £1,368bn, 44.8% of national income.
- House of Commons Library tax statistics overview, June 2026: 2025/26 receipts around £1,232bn.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Suggested next improvements

- Replace coarse defaults with full OBR / HMRC line-item imports.
- Add household distribution modelling by income decile.
- Add age cohorts and lifetime earnings effects.
- Add uncertainty bands / Monte Carlo simulation.
- Add named scenarios: Baseline, Fairness Swap, Social Investment, UBI, Deficit Repair.
