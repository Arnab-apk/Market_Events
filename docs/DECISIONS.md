# Decisions

## 2026-10-24 · Small local workbench

Use Streamlit's native forms, controls, tables and bar chart, with a slate background, blue hierarchy and amber controls. Visible labels, keyboard focus outlines and textual status supplement colour. No external fonts, animation or chart dependency is required. The UI/UX skill's initial marketing-style pattern was unsuitable; its high-contrast palette/accessibility guidance informs the research layout instead.

## Explicit writes and execution

Opening the page does not instantiate storage or load fixtures. **Open workspace** initializes the local database; demo loading and analysis are distinct explicit actions. This makes Streamlit reruns safe from accidental model calls. Local import is deliberate and shows validation results; temporary uploaded files are removed after parsing.

## Interface authority

`BUILD_CONTRACT.md` controls shared signatures and CLI spellings. The user guide was extended concurrently through sections 8–18; these sections have been reread, particularly dashboard behaviour and durable idempotency. User guides are not edited by the UI work. Where the guide leaves numerical choices open, use the frozen contract defaults and saved domain configuration; do not invent rules in presentation code.

## Comparisons preserve uncertainty

Use saved calls/runs, retain replay/live separation and unknown usage. Deterministic ablations use frozen rules and preserve original assessments. Cohort inspection is provided rather than implying every aggregate is a fair experiment. Statistical quality comparisons remain future work until reviewed labels and real-data studies exist.

Optional explanation children inherit source/assessment evidence but represent a different request. Keep their traces and persisted text visible while excluding them from latest-analysis inbox status, policy analysis counts, matched cohorts and ablations. Report their usage separately. Resolve and export the observations referenced by each saved run, with missing IDs explicit; this makes case evidence portable without changing numerical calculations. Root and database both identify a workspace, so changing either requires an explicit open.

## Scope

No trading, brokerage integration, derivative analytics, autonomous worker, vector search or generic chatbot. The demonstration universe consists of conceptual synthetic examples, not a current listing/investability assertion. Live provider support and real-data validation are separate acceptance criteria; a successful replay cannot satisfy them.

## 2026-10-24 · Beginner workflow and independent price context

Keep the native Streamlit controls and existing slate/blue/amber theme. The main area starts with a skippable quick start and explicit recorded demo. Task-based sidebar navigation, source excerpts and readable status/policy labels guide the work; IDs and raw schemas remain available for audit. Results start with the assessment, percentage coverage and limitations. Advanced controls and JSON are progressively disclosed in labelled expanders. This applies the UI/UX skill's empty-state, visible-label and keyboard-control guidance without adding a framework or redesigning the product.

Price-indicator computation is a separate explicit local form with a current aware default cutoff, history coverage and supporting price chart. It does not require news, tokens or language models and does not alter event scores. The provider workflow separates offline token/configuration presence, explicit read-only data refresh and an optional separate bounded live-model news batch. `LIVE:` namespaces and universe-scoped temporary state prevent demo/provider context from silently mixing. Browser, viewport and assistive-technology verification remain unperformed; AppTest protects behaviour only.
