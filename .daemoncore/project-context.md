# Project Context

## Project Name
uk_policy_simulator

## Description
An interactive Streamlit app ("UK Policy Sandbox") for modelling simplified UK
fiscal reform scenarios. Users adjust revenue and investment levers plus dynamic
feedback assumptions, and the app projects receipts, spending, deficit and
deficit-as-percent-of-GDP over a configurable horizon. It is a transparent
scenario sandbox, not an official macroeconomic model.

## Workspace Ownership & Authority
- Owner: Mark Stokes (MarkStokes-outlook)
- This workspace is subordinate to the DaemonCore kernel safety rules.
- Do not assume authority outside this repository without explicit human instruction.

## Tech Stack
- Python 3.13
- Streamlit (UI), pandas (data), altair (charts)
- pytest (tests)

## Key Files
- `app.py` — Streamlit UI: controls and rendering only.
- `model/fiscal_model.py` — pure, testable fiscal calculations and baseline loading.
- `baseline.csv` — canonical baseline fiscal values (loaded at startup).
- `tests/test_fiscal_model.py` — pytest suite for the model.

## Purpose of This Workspace
- Define how agents should treat this codebase.
- Capture architectural intent, boundaries, and domain concepts.
- Anchor planning and backlog work in a single, human-owned source of truth.

## Safety & Boundaries
- Do not modify build/release pipelines without explicit human approval.
- Avoid destructive operations (deletes, migrations, data transforms) unless explicitly requested.
- Treat secrets, credentials, and personal data as off-limits unless clearly provided for a task.
- When unsure, propose a plan in `.daemoncore/outbox/` instead of changing core project files.
