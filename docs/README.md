# Documentation index

Documentation for *A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market
Signal Fusion in Indian Financial Markets*, implemented as **Market Events**. New here? Read the
[project README](../README.md), then the first two rows below.

## Start here

| Document | What it is for |
| --- | --- |
| [USER_GUIDE.md](USER_GUIDE.md) | Step-by-step website guide: starting it, every page, reading results, own data, troubleshooting; Streamlit and CLI in the appendix |
| [CODEBASE_GUIDE.md](CODEBASE_GUIDE.md) | Code map: which module to read first and where each calculation lives |
| [LIVE_SETUP.md](LIVE_SETUP.md) | Optional setup for real Upstox market data, news and live language models |

## Design

| Document | What it is for |
| --- | --- |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Components, analysis flow, model routing, fusion, time rules and persistence (Streamlit-era snapshot, 26 Oct 2026) |
| [DECISIONS.md](DECISIONS.md) | Why key design choices were made (explicit writes, comparisons that keep uncertainty, scope) |
| [BUILD_CONTRACT.md](BUILD_CONTRACT.md) | Shared interfaces, signatures and CLI spellings that the code must keep |
| [TRADING_EXTENSION_CONTRACT.md](TRADING_EXTENSION_CONTRACT.md) | Contract for the strategy lab (charts, backtests, Monte Carlo; studies end 2020-12-31) |
| [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md) | Path from research prototype to a full Next.js product, and what that would need |

## Data and models

| Document | What it is for |
| --- | --- |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Meaning, units and time conventions of every stored record |
| [MODEL_AND_PROMPT_NOTES.md](MODEL_AND_PROMPT_NOTES.md) | The three execution policies, prompt versions and recorded model pilots |
| [EXPERIMENTS.md](EXPERIMENTS.md) | What the comparison tools measure, the saved results, and what they do **not** show |
| [research/RESEARCH_BRIEF.md](research/RESEARCH_BRIEF.md) | Related work (with verification marks), novelty statement, gap analysis and future work |

## Presentation

| Document | What it is for |
| --- | --- |
| [presentation/SLIDES.md](presentation/SLIDES.md) | 14 slides with speaker notes for the 1 December 2026 presentation |
| [presentation/DEMO_SCRIPT.md](presentation/DEMO_SCRIPT.md) | Timed live demo with exact clicks and an offline fallback for each step |
| [presentation/VIVA_QA.md](presentation/VIVA_QA.md) | Likely examiner questions with answers grounded in the code |
| [presentation/ARCHITECTURE_DIAGRAM.md](presentation/ARCHITECTURE_DIAGRAM.md) | Current architecture diagram (mermaid plus plain-text fallback) |
| [DEMO_AND_VIVA.md](DEMO_AND_VIVA.md) | Outcome definition, the look-ahead answer and the Streamlit demo walkthrough |

## Process and history

| Document | What it is for |
| --- | --- |
| [PRESENTATION_PLAN.md](PRESENTATION_PLAN.md) | Presentation-readiness plan, agent ownership, acceptance gates and cross-agent requests |
| [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) | How the development agents (Herdr tabs) divided the work |
| [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) | Dated record of what was built and how it was verified |
| [WEBSITE_VERIFICATION.md](WEBSITE_VERIFICATION.md) | Browser and build checks for the Next.js dashboard |
| [archive/planning/](archive/planning/) | Early planning documents: MVP guide, project comparison, prototype workflow (may not match current code) |
