# UK Policy Simulator

## Product Vision & Long-Term Roadmap

Version: 1.0  
Status: Living Document  
Last Updated: June 2026

---

## Vision

The UK Policy Simulator aims to become the world's most transparent, educational, and collaborative public policy experimentation platform.

The goal is not to tell people what to think.

The goal is to allow anyone to:

- Build policy proposals
- Explore trade-offs
- Understand consequences
- Compare approaches
- Challenge assumptions
- Learn how government actually works

Over time, the platform should evolve from a simple fiscal simulator into a comprehensive societal modelling environment.

---

## Core Principles

### Transparency

All scoring, assumptions, and calculations should be visible and explainable.

No black-box scoring.

No hidden algorithms.

---

### Education First

Users should leave understanding more about economics, government, taxation, welfare, and public services than when they arrived.

---

### Multiple Perspectives

The platform should support competing views and schools of thought.

The objective is not ideological correctness.

The objective is informed exploration.

---

### Evidence Before AI

AI may explain and critique.

AI must not silently determine outcomes.

Core calculations remain deterministic and auditable.

---

### Community Collaboration

Users should be able to:

- Save models
- Share models
- Fork models
- Improve models
- Debate models

Much like GitHub enables collaborative software development.

---

## Governance, Evidence & Trust Framework

The credibility of the platform is more important than the sophistication of any individual model.

All outputs must be classified according to the evidence framework below.

### Class A — Evidence-Based

Derived directly from published datasets, deterministic calculations, and reproducible methodologies.

Examples:

- Tax receipts
- Government spending
- Debt and deficit calculations
- Distributional analysis
- Regional demographic analysis
- Historical datasets

Requirements:

- Fully auditable
- Versioned
- Reproducible
- Source-linked
- Deterministic

### Class B — Evidence-Informed Projection

Derived from published research, calibrated assumptions, and transparent modelling.

Examples:

- Labour participation effects
- Productivity impacts
- Housing affordability effects
- NHS demand reduction estimates
- Education outcome projections

Requirements:

- Confidence rating
- Published assumptions
- Evidence references
- Uncertainty ranges

### Class C — Illustrative Simulation

Exploratory and educational modelling intended to stimulate discussion and challenge assumptions.

Examples:

- Stakeholder reactions
- Media simulations
- Public reaction simulations
- AI Cabinet analysis
- Agent-based society models

Requirements:

- Clearly labelled as illustrative
- Must not be presented as prediction
- Must not inherit the authority of Class A outputs
- Must explain assumptions and limitations

### Credibility Boundary

Versions up to and including Distributional Analysis primarily operate within Class A and Class B outputs.

Society Simulation and Advanced Simulation features operate primarily within Class C outputs and must be visually and conceptually separated from evidence-based modelling.

### Data Sources & Licensing

Class A outputs must clearly identify:

- Source dataset
- Source organisation
- Dataset version
- Date retrieved
- Applicable licence

Expected primary sources include:

- ONS
- OBR
- HMRC
- DWP
- NHS England
- Department for Education
- Ministry of Housing, Communities and Local Government

Data provenance must remain visible throughout the platform.

### Sustainability & Operating Model

The platform should remain accessible, transparent, and financially sustainable.

Future platform design should consider:

- Hosting costs
- AI inference costs
- Data storage costs
- Moderation requirements
- Community management
- Long-term maintenance

Bring Your Own AI capabilities should reduce operating costs where practical, while ensuring the platform remains useful to users who do not provide external AI credentials.

## Validation & Calibration Strategy

The simulator must continuously validate itself against real-world outcomes.

Validation is not a future feature. It is an ongoing responsibility.

Key activities include:

- Historical replay and policy backtesting
- Forecast accuracy measurement
- Sensitivity analysis
- Assumption validation
- Model calibration
- Variance tracking between predicted and observed outcomes

The objective is to understand where the model is strong, where it is weak, and where uncertainty is highest.

---

## Product Evolution

---

## Version 0.x — Foundation

### v0.1

#### Core Fiscal Engine

Features:

- Baseline fiscal dataset
- Tax and spending levers
- Fiscal projections
- Scenario comparison
- Projection charts
- CSV export

Goal:

Create a trustworthy simulation foundation.

---

### v0.2

#### Scenario Presets

Features:

- Baseline
- Fairness Swap
- Social Investment
- Deficit Repair
- Universal Basic Services
- UBI Experiment
- Austerity Trap

Goal:

Provide reusable policy templates.

---

### v0.3

#### Deterministic Scoring

Categories:

- Fiscal Sustainability
- Economic Growth
- Poverty Reduction
- Housing Affordability
- NHS Demand Impact
- Income Equality
- Implementation Complexity

Note:

The platform should avoid embedding ideological assumptions into scoring.

Subjective concepts such as fairness, desirability, or political acceptability should be represented through configurable weighting profiles rather than fixed scores.

Goal:

Provide objective scoring without AI dependency.

Status:

Shipped in v0.3. Deterministic 0–100 scores across all seven categories, a
published per-lever contribution matrix, and five configurable weighting
profiles (no profile treated as correct). See [`scoring.md`](scoring.md).

---

## Version 1.x — Community Platform

### v1.0

#### Saved Models

Features:

- Save model
- Load model
- Clone model
- Delete model
- Version history

Goal:

Create persistent policy proposals.

Status:

Shipped in v1.0. File-backed `ModelStore` with save / load / clone / delete and
append-only version history; models persist locally as gitignored user data.
See [`saved-models.md`](saved-models.md).

---

### v1.1

#### Identity Platform

Features:

- Registration
- Login
- Password reset
- Profile management

Architecture:

Provider abstraction.

Future support:

- Authentik
- Google
- Microsoft
- GitHub

Goal:

Establish ownership and identity.

Architecture Note:

This milestone represents the transition from a standalone simulation tool to a multi-user platform.

Platform architecture should be reviewed before implementation to ensure future support for persistence, sharing, collaboration, and scale.

---

### v1.2

#### Model Sharing

Features:

- Public models
- Private models
- Unlisted models
- Share links

Goal:

Enable public discussion and collaboration.

---

### v1.3

#### Leaderboards

Categories:

- Best Balanced
- Best Fiscal Sustainability
- Best Economic Growth
- Best Poverty Reduction
- Best Housing Affordability
- Best NHS Demand Reduction
- Best Income Equality

Goal:

Encourage experimentation and comparison.

Leaderboards should be generated within the context of a selected weighting profile.

Examples:

- Fiscal Conservative Profile
- Social Democratic Profile
- Green Investment Profile
- Libertarian Profile
- Custom User Profile

The platform should avoid presenting any single weighting profile as objectively correct.

---

## Version 2.x — Intelligence Layer

### v2.0

#### AI Provider Framework

Supported Providers:

- Ollama
- OpenAI
- Anthropic
- Gemini

Architecture:

Provider abstraction.

Goal:

Support AI-powered interpretation.

---

### v2.1

#### Bring Your Own AI

Features:

- Personal API keys
- Provider selection
- Usage tracking

Goal:

Reduce platform operating costs.

---

### v2.2

#### AI Policy Analysis

Outputs:

- Executive summary
- Strengths
- Weaknesses
- Trade-offs
- Risks
- Recommendations

Rule:

AI explains outcomes.

AI does not determine outcomes.

---

### v2.3

#### Policy Slider Intelligence

Each policy lever includes:

- Explanation
- Intended outcomes
- Side effects
- Real-world examples
- Affected metrics
- Uncertainty level

Goal:

Turn the simulator into an educational platform.

---

## Version 3.x — Socio-Economic Modelling

### v3.0

#### Advanced Socio-Economic Engine

Features:

- Labour participation effects
- Productivity effects
- Welfare impacts
- Housing impacts
- NHS impacts
- Education impacts

Forecast Modes:

- Conservative
- Moderate
- Optimistic

Goal:

Move beyond simple fiscal modelling.

---

### v3.1

#### Distributional Analysis

Features:

- Income deciles
- Household types
- Age groups
- Regional breakdowns
- Validation against real-world household datasets

Outputs:

- Winners and losers
- Distribution charts
- Regional comparisons

Goal:

Understand who is affected.

---

### v3.2

#### UK Regional Impact Maps

Features:

- Interactive heat maps
- Local authority impacts
- Regional comparisons
- Long-term forecasts

Examples:

- Employment impact
- NHS demand impact
- Housing affordability impact
- Income impact

Goal:

Visualise geographical consequences.

---

### v3.3

#### Historical Replay & Backtesting Engine

Examples:

- Alternative 2008 response
- Alternative Brexit paths
- Housing policy counterfactuals
- Tax reform experiments

Goal:

Test alternate histories, validate model assumptions, and improve calibration against known historical outcomes.

Validation Value:

Historical replay is a trust-building capability.

It allows the platform to compare model outputs against known historical outcomes and improve calibration over time.

---

## Version 4.x — Society Simulation

### v4.0

#### Stakeholder Simulation

Simulated stakeholders:

- Trade unions
- Large employers
- SMEs
- Pensioners
- Renters
- Landlords
- Investors
- Public sector workers

Outputs:

- Support scores
- Opposition scores
- Lobbying pressure
- Public sentiment

Goal:

Model political friction.

---

### v4.1

#### Media Simulation

Perspectives:

- Left-leaning media
- Right-leaning media
- Business media
- Regional media
- Social media

Outputs:

- Headline generation
- Narrative analysis
- Public perception impact

Goal:

Model communication effects.

---

### v4.2

#### Public Reaction Simulator

Groups:

- Income bands
- Generational groups
- Geographic regions

Outputs:

- Approval ratings
- Satisfaction
- Electoral effects
- Trust changes

Goal:

Explore societal reactions.

---

## Version 5.x — Advanced Simulation

### v5.0

### Agent-Based Society Engine

Agents:

- Households
- Businesses
- Councils
- NHS Trusts
- Investors
- Universities
- Lobby Groups
- Political Parties

Capabilities:

- Autonomous decision making
- Dynamic reactions
- Emergent outcomes

Goal:

Model second-order effects.

---

### v5.2

#### AI Cabinet

Cabinet Members:

- Treasury AI
- NHS AI
- Housing AI
- Education AI
- Climate AI
- Business AI
- Welfare AI

Purpose:

Provide competing expert perspectives.

Goal:

Encourage critical thinking.

Classification:

Class C — Illustrative Simulation.

AI Cabinet outputs are advisory perspectives and thought experiments.

They are not forecasts, predictions, or evidence-based conclusions.

---

## Version 6.x — Public Policy Laboratory

### v6.0

#### Research Platform

Features:

- Monte Carlo simulations
- Sensitivity analysis
- Scenario benchmarking
- Academic exports
- Dataset versioning

Goal:

Support serious policy research.

---

### v6.1

#### Public Policy Marketplace

Features:

- Community proposals
- Proposal ranking
- Public review
- Expert review
- Collaborative iteration

Goal:

Create an ecosystem of policy innovation.

---

### v6.2

#### Policy GitHub

Features:

- Fork proposals
- Pull requests
- Version comparison
- Policy changelogs
- Attribution

Goal:

Apply open-source principles to governance.

---

## Long-Term Vision

The final platform should answer questions such as:

- What happens if we replace Council Tax?
- What happens if childcare becomes universal?
- What happens if housing construction doubles?
- Which regions benefit?
- Which groups lose?
- How does the media react?
- How do businesses react?
- What does the NHS think?
- What does the Treasury think?
- What are the second-order effects?
- What happens after 5, 10, or 20 years?

The platform should aspire to become a trusted public instrument rather than a political advocacy tool.

Its responsibility is to expose assumptions, evidence, uncertainty, and trade-offs, allowing users to reach their own conclusions.

Throughout the platform, users must always be able to distinguish between:

- Measured reality
- Evidence-informed projection
- Illustrative simulation

Maintaining that distinction is fundamental to the trustworthiness of the platform.

The ambition is to become a transparent public policy laboratory where citizens, researchers, students, journalists, economists, and governments can explore ideas, challenge assumptions, and better understand how complex societies function.
