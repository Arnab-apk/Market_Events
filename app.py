"""Streamlit presentation layer. All market decisions belong to the domain modules."""

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import streamlit as st

IST = ZoneInfo("Asia/Kolkata")
TASKS = {
    "Start": "Start here",
    "Research": "Analyse an article",
    "Saved runs": "Review saved results",
    "Technicals": "Explore price indicators",
    "Strategy lab": "Charts, backtests and Monte Carlo",
    "Connections": "Connect and refresh data",
    "Comparisons": "Compare research runs",
    "Import": "Import local evidence",
}
POLICIES = {
    "llm_only": "Large model only",
    "slm_filter": "Small model filter → large model extraction",
    "slm_delegate": "Small model filter + hints → large model extraction",
}
LABELS = {
    "completed": "Analysis saved",
    "abstained": "Insufficient evidence",
    "duplicate": "Duplicate source",
    "irrelevant": "No relevant event",
    "ineligible": "Outside the decision cutoff",
    "failed": "Analysis failed",
    "partial": "Incomplete analysis",
    "interrupted": "Analysis interrupted",
    "explanation_completed": "Optional explanation saved",
    "explanation_failed": "Optional explanation failed",
    "positive_evidence": "Positive evidence",
    "negative_evidence": "Negative evidence",
    "mixed_evidence": "Mixed evidence",
    "insufficient_evidence": "Insufficient evidence",
    "replay": "Recorded replay · offline",
    "live": "Configured model inference",
}

WORKFLOW_STEPS = (
    ("Start", "Set up a workspace"),
    ("Import", "Bring in evidence"),
    ("Research", "Analyse an event"),
    ("Saved runs", "Review the audit trail"),
    ("Comparisons", "Measure later outcomes"),
)


def compact_count(value):
    """Keep overview metrics readable without changing the underlying counts."""
    return f"{value:,}"


def app_header():
    """Render the product header shared by the landing page and workspace."""
    st.markdown(
        """
        <div class="product-header">
            <div class="brand-lockup">
                <div class="brand-mark">ME</div>
                <div>
                    <div class="brand-name">Market Events</div>
                    <div class="brand-subtitle">Evidence-first research workbench</div>
                </div>
            </div>
            <div class="product-badge">RESEARCH PROTOTYPE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_intro(eyebrow, title, description):
    """Render a compact, consistent heading for a major interaction area."""
    st.markdown(
        f"""
        <div class="section-intro">
            <div class="eyebrow">{eyebrow}</div>
            <h2>{title}</h2>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def workflow_strip(active):
    """Make the current place in the workflow visible without adding another control."""
    items = []
    for key, title in WORKFLOW_STEPS:
        state = "active" if key == active else ""
        items.append(
            f'<span class="workflow-step {state}"><b>{key}</b><small>{title}</small></span>'
        )
    st.markdown(f'<div class="workflow-strip">{"".join(items)}</div>', unsafe_allow_html=True)


def label(value):
    return LABELS.get(value, str(value).replace("_", " ").capitalize())


def article_label(article):
    text = " ".join(article.text.split())
    synthetic = text.startswith("EXPLICITLY SYNTHETIC FIXTURE.")
    if synthetic:
        text = text.removeprefix("EXPLICITLY SYNTHETIC FIXTURE.").strip()
    return f"{'Synthetic · ' if synthetic else ''}{text[:100]}{'…' if len(text) > 100 else ''} · {article.article_id}"


def navigate(section, run_id=None):
    """Navigation only: all writes and provider calls stay in explicit actions."""
    st.session_state["workbench_view"] = section
    if run_id is not None:
        st.session_state["selected_run"] = run_id
        st.session_state["saved_run_choice"] = run_id


def prepare_demo():
    st.session_state["universe_selection"] = "demo"


def result_summary(run):
    st.subheader("What this result means")
    if run.assessment:
        result = run.assessment
        cols = st.columns(3)
        cols[0].metric("Evidence", label(result.evidence_label))
        cols[1].metric(
            "Evidence score",
            f"{result.evidence_score:+.2f}" if result.evidence_score is not None else "Unavailable",
        )
        cols[2].metric("Evidence coverage", f"{result.coverage:.0%}")
        st.caption(
            "The score ranges from −1 to +1 and summarizes available numerical evidence. "
            "It is not a probability, forecast or recommendation. Coverage is the share of configured evidence weights available; it is not confidence."
        )
        st.write(result.explanation)
        for reason in result.abstention_reasons + result.conflicts:
            st.warning(reason)
    else:
        st.info(label(run.status))
        next_steps = {
            "duplicate": "This source repeats earlier eligible content. Inspect its related article IDs in Source & event; no new catalyst or model call is needed.",
            "irrelevant": "The filter found no relevant event. Review the retained routing reason and source, or select another article.",
            "ineligible": "Choose a decision time at or after publication and first-seen time, then submit again.",
        }
        st.write(
            next_steps.get(
                run.status,
                "Review the source, routing and error details below. Correct the inputs or configuration before explicitly submitting another analysis.",
            )
        )


def start_panel(active=False):
    section_intro(
        "START HERE",
        "Turn a market event into an auditable research case",
        "Move from a dated source article to structured event evidence, a deterministic assessment and a separate later-outcome check. Every model action is explicit and every saved result keeps its supporting context.",
    )
    workflow_strip("Start")
    st.markdown(
        """
        <div class="hero-panel">
            <div>
                <div class="hero-kicker">A guided workflow, not a black box</div>
                <h3>Start with the offline demo, then bring your own evidence.</h3>
                <p>Explore the complete flow with recorded responses first. When you are ready, import local JSONL/CSV evidence or connect a configured provider without changing the research record.</p>
            </div>
            <div class="hero-note"><strong>Safe by default</strong><br>Opening the page does not write to disk, call a model or fetch market data.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    cols[0].markdown(
        "**01 · Explore**\n\nLoad three synthetic event families in replay mode. No API key or network connection is needed."
    )
    cols[1].markdown(
        "**02 · Understand**\n\nRead the evidence score, coverage, source passages, price inputs and limitations behind each result."
    )
    cols[2].markdown(
        "**03 · Extend**\n\nImport your own evidence, compute local price indicators or opt into configured model inference."
    )
    demo = st.button(
        "Load synthetic demo (replay)",
        type="primary",
        key="quick_start_demo",
        on_click=prepare_demo,
    )
    st.caption(
        "Synthetic articles, prices and recorded model outputs demonstrate the workflow. They do not establish real-market validity."
    )
    if active:
        action_cols = st.columns(2)
        action_cols[0].button(
            "Review saved results", on_click=navigate, args=("Saved runs",), key="start_results"
        )
        action_cols[1].button(
            "Import local evidence", on_click=navigate, args=("Import",), key="start_import"
        )
    with st.expander("How to read this workbench"):
        st.write(
            "Recorded replay uses fixture responses offline. Configured inference calls your selected models only after an explicit action; it does not fetch market data. A new model reading an old article is not a historically available forecast."
        )
        st.write(
            "A saved decision keeps its cutoff and evidence. Later outcomes are separate hypothetical measurements. Missing or stale mandatory inputs can force an insufficient-evidence result."
        )
    return demo


def workspace_overview(dependencies):
    """Show a friendly, read-only home screen once a workspace is open."""
    articles = dependencies.storage.list_articles()
    runs = list(reversed(dependencies.storage.list_runs()))
    observations = dependencies.storage.list_observations()
    assessed = [run for run in runs if run.assessment is not None]
    completed = [run for run in assessed if run.status == "completed"]

    section_intro(
        "WORKSPACE OVERVIEW",
        "Your research workspace at a glance",
        "Use the navigation on the left to move from evidence intake to analysis, review and comparison. Read-only views never start inference or change saved decisions.",
    )
    workflow_strip("Start")

    metrics = st.columns(4)
    metrics[0].metric(
        "Articles", compact_count(len(articles)), help="Imported articles in the active universe."
    )
    metrics[1].metric(
        "Saved runs",
        compact_count(len(runs)),
        help="Analysis and explanation traces saved in this workspace.",
    )
    metrics[2].metric(
        "Assessed",
        compact_count(len(assessed)),
        help="Runs with a deterministic assessment available.",
    )
    metrics[3].metric(
        "Price observations",
        compact_count(len(observations)),
        help="Imported observations available for cutoff-safe analysis.",
    )

    if not articles:
        title = "Bring in your first evidence"
        message = "Import article JSONL or market CSV, or use the bundled replay demo to see the full workflow before adding your own data."
        target = "Import"
        label_text = "Import local evidence"
    elif not runs:
        title = "Your evidence is ready to analyse"
        message = "Choose an article in Research, set an offset-aware decision cutoff and submit one explicit analysis."
        target = "Research"
        label_text = "Analyse an article"
    else:
        title = "Continue where you left off"
        message = f"You have {len(assessed)} assessed run{'' if len(assessed) == 1 else 's'}. Review the latest result or compare runs after evaluating later outcomes."
        target = "Saved runs"
        label_text = "Review saved results"

    st.markdown(
        f"""
        <div class="next-step-panel">
            <div class="eyebrow">RECOMMENDED NEXT STEP</div>
            <h3>{title}</h3>
            <p>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    action_cols = st.columns([1, 1, 2])
    action_cols[0].button(
        label_text, type="primary", on_click=navigate, args=(target,), key="overview_next"
    )
    action_cols[1].button(
        "Explore technicals", on_click=navigate, args=("Technicals",), key="overview_technicals"
    )
    action_cols[2].caption(
        "Tip: the synthetic replay is the fastest way to understand the audit trail. Technical indicators are computed locally and do not require a model."
    )

    st.markdown("#### Recent activity")
    if not runs:
        st.info("No saved activity yet. Your first explicit analysis will appear here.")
    else:
        article_lookup = {article.article_id: article for article in articles}
        recent_rows = []
        for run in runs[:5]:
            article = article_lookup.get(run.article_id)
            recent_rows.append(
                {
                    "Article": article_label(article) if article else run.article_id,
                    "Status": label(run.status),
                    "Mode": label(run.mode),
                    "Cutoff (IST)": run.decision_time.astimezone(IST).strftime("%d %b %Y · %H:%M"),
                    "Run": run.run_id[:8],
                }
            )
        st.dataframe(recent_rows, use_container_width=True, hide_index=True)
        if completed:
            st.caption(
                f"{len(completed)} completed assessment{'' if len(completed) == 1 else 's'} ready for evidence review. Outcome evaluation remains a separate explicit action."
            )


def parse_cutoff(value):
    """Require an explicit offset so a cutoff can never silently become local time."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Include a timezone offset, for example +05:30 for IST.")
    return parsed.astimezone(timezone.utc)


def dump(records):
    return [record.model_dump(mode="json") for record in records]


def watchlist_panel(dependencies):
    from market_events.config import read_companies

    st.markdown("#### Imported watchlist")
    companies = read_companies(dependencies.settings)
    names = {company["instrument_id"]: company["name"] for company in companies}
    selected = st.multiselect(
        "Watchlist companies",
        list(names),
        default=list(names),
        format_func=lambda key: f"{names[key]} · {key}",
    )
    observations = dependencies.storage.list_observations()
    rows = []
    for company in selected:
        bars = [bar for bar in observations if bar.instrument_id == company]
        if not bars:
            rows.append({"company": company, "status": "No imported observations"})
            continue
        latest = max(bars, key=lambda bar: bar.timestamp)
        rows.append(
            {
                "company": company,
                "status": "Imported; not a live quote",
                "observations": len(bars),
                "coverage_start_IST": min(bar.timestamp for bar in bars)
                .astimezone(IST)
                .isoformat(),
                "latest_session_IST": latest.timestamp.astimezone(IST).isoformat(),
                "available_at_IST": latest.available_at.astimezone(IST).isoformat(),
                "close": latest.close,
                "volume": latest.volume,
                "currency": latest.currency,
                "unit": latest.unit,
            }
        )
    st.caption(
        "Latest imported session, including later outcome data. This table is not cutoff-filtered decision evidence. Demo rows are synthetic; LIVE identifiers belong to separate provider imports."
    )
    st.dataframe(rows, use_container_width=True)


def import_panel(dependencies):
    from market_events.ingestion import import_articles, import_market_prices
    from market_events.schemas import Article

    storage = dependencies.storage
    section_intro(
        "IMPORT",
        "Bring evidence into your workspace",
        "Validate source articles and market observations before they enter the research ledger. Uploads and manual entry are explicit; invalid rows stay visible instead of being silently discarded.",
    )
    workflow_strip("Import")
    watchlist_panel(dependencies)
    st.markdown("#### Import evidence")
    st.caption(
        "Article JSONL and market CSV. Timestamps must include offsets; first-seen and availability are required."
    )
    with st.form("import"):
        kind = st.selectbox("Dataset", ["Articles (JSONL)", "Market observations (CSV)"])
        upload = st.file_uploader("Local evidence file", type=["jsonl", "csv"])
        with st.expander("Advanced · import from a local path"):
            local = st.text_input(
                "Or local file path", help="Use a permitted local file. Upload takes precedence."
            )
        submitted = st.form_submit_button("Validate and import")
    if submitted:
        try:
            with TemporaryDirectory() as directory:
                path = Path(local).expanduser()
                if upload is not None:
                    path = Path(directory) / (
                        "input.jsonl" if kind.startswith("Articles") else "input.csv"
                    )
                    path.write_bytes(upload.getvalue())
                elif not local.strip():
                    raise ValueError("Choose a file or enter a path.")
                articles = kind.startswith("Articles")
                result = (import_articles if articles else import_market_prices)(path)
                count = (storage.add_articles if articles else storage.add_observations)(
                    result.records
                )
            st.success(f"Stored {count} records. Rejected rows: {len(result.errors)}.")
            if result.errors:
                st.dataframe(result.errors, use_container_width=True)
            for warning in result.warnings:
                st.warning(warning)
        except Exception as exc:
            st.error(f"Import failed: {exc}")
    with st.expander("Manual article entry"):
        with st.form("manual"):
            article_id = st.text_input("Article ID")
            url = st.text_input("Source URL or source identifier")
            text = st.text_area("Permitted source text", height=180)
            published = st.text_input("Published at (ISO timestamp with offset)")
            seen = st.text_input("First seen at (ISO timestamp with offset)")
            version = st.text_input("Source version", value="1")
            predecessor = st.text_input("Predecessor article ID (optional)")
            st.caption(
                "For provider/live news, Article ID must start with LIVE:. Demo/local IDs use a separate namespace. Saving text never starts model inference."
            )
            save = st.form_submit_button("Validate and save article")
        if save:
            try:
                if article_id.startswith("LIVE:") != (dependencies.settings.universe == "live"):
                    raise ValueError(
                        "Article ID must match the selected universe: use LIVE: for live/provider news and a separate ID for demo/local evidence."
                    )
                article = Article(
                    article_id=article_id,
                    source_url=url,
                    text=text,
                    published_at=parse_cutoff(published),
                    first_seen_at=parse_cutoff(seen),
                    source_version=version,
                    predecessor_id=predecessor or None,
                )
                count = storage.add_articles([article])
                st.success(f"Stored {count} article records.")
            except Exception as exc:
                st.error(f"Article was not saved: {exc}")


def research_panel(dependencies, mode):
    from market_events.config import read_companies
    from market_events.experiments import is_explanation_run
    from market_events.pipeline import analyse_article
    from market_events.schemas import ExecutionPolicy

    names = {
        company["instrument_id"]: company["name"]
        for company in read_companies(dependencies.settings)
    }
    articles = dependencies.storage.list_articles()
    articles = [
        article
        for article in articles
        if article.article_id.startswith("LIVE:") == (dependencies.settings.universe == "live")
    ]
    section_intro(
        "RESEARCH INBOX",
        "Analyse a dated article",
        "Select one source, choose the decision cutoff that was actually available at that moment and submit an explicit, reproducible analysis.",
    )
    workflow_strip("Research")
    if not articles:
        st.info("Import articles or explicitly load the synthetic demo to begin.")
        st.button(
            "Import evidence", on_click=navigate, args=("Import",), key="empty_research_import"
        )
        return
    latest_runs = {}
    for run in sorted(dependencies.storage.list_runs(), key=lambda item: item.created_at):
        if not is_explanation_run(run):
            latest_runs[run.article_id] = run
    rows = []
    for article in articles:
        latest = latest_runs.get(article.article_id)
        extraction = latest.extraction if latest else None
        rows.append(
            {
                "article_id": article.article_id,
                "article": article_label(article),
                "company": extraction.company_id
                if extraction and extraction.company_id
                else "Unresolved / not analysed",
                "event_type": extraction.event_type if extraction else "Not extracted",
                "status": latest.status if latest else "Not analysed",
                "memory": latest.memory.get("status", "Not classified")
                if latest
                else "Not classified",
                "published_IST": article.published_at.astimezone(IST).isoformat(),
                "first_seen_IST": article.first_seen_at.astimezone(IST).isoformat(),
                "source": article.source_url,
            }
        )
    st.write("Event inbox")
    st.caption(
        "Company, type, status and memory come from the latest saved run; unanalysed articles remain explicit. Filters do not start inference."
    )
    columns = st.columns(3)
    company = columns[0].selectbox(
        "Inbox company",
        ["All"] + sorted({row["company"] for row in rows}),
        format_func=lambda key: names.get(key, key),
    )
    event_type = columns[1].selectbox(
        "Inbox event type", ["All"] + sorted({row["event_type"] for row in rows}), format_func=label
    )
    status = columns[2].selectbox(
        "Inbox status", ["All"] + sorted({row["status"] for row in rows}), format_func=label
    )
    rows = [
        row
        for row in rows
        if (company == "All" or row["company"] == company)
        and (event_type == "All" or row["event_type"] == event_type)
        and (status == "All" or row["status"] == status)
    ]
    st.dataframe(
        [
            {
                **row,
                "status": label(row["status"]),
                "event_type": label(row["event_type"]),
                "memory": label(row["memory"]),
                "company": names.get(row["company"], row["company"]),
            }
            for row in rows
        ],
        use_container_width=True,
        column_order=["article", "company", "event_type", "status", "memory"],
        hide_index=True,
    )
    if not rows:
        st.info("No articles match these inbox filters.")
        return
    visible = {row["article_id"] for row in rows}
    by_id = {a.article_id: a for a in articles if a.article_id in visible}
    article_id = st.selectbox(
        "Article", list(by_id), format_func=lambda key: article_label(by_id[key])
    )
    article = by_id[article_id]
    st.caption(
        f"Source excerpt · {article.source_url} · published {article.published_at.astimezone(IST):%d %b %Y, %H:%M IST}"
    )
    with st.expander("Read the original article and source times"):
        st.text(article.text)
        st.caption(
            f"Published {article.published_at.astimezone(IST).isoformat()} · First seen {article.first_seen_at.astimezone(IST).isoformat()}"
        )
    with st.form("analyse"):
        cutoff = st.text_input(
            "Decision cutoff · IST (UTC+05:30)",
            value="2026-01-12T17:30:00+05:30"
            if article.article_id.startswith("syn-")
            else datetime.now(IST).replace(microsecond=0).isoformat(),
            help="The January 2026 default is for the bundled synthetic demo. For imported articles choose an eligible cutoff. Include +05:30 for IST; stored internally in UTC.",
        )
        with st.expander("Advanced · model policy and repeat experiments"):
            policy = st.selectbox(
                "Execution policy",
                [p.value for p in ExecutionPolicy],
                format_func=lambda value: POLICIES[value],
            )
            st.caption(
                "All policies use code for numerical evidence. The small model can filter and supply verified extraction hints; the large model extracts the event."
            )
            repeat = st.checkbox(
                "Explicit repeat experiment",
                value=False,
                help="Create a separate linked run instead of reusing an identical completed request. May make new model calls in live mode.",
            )
        st.caption(
            f"{label(mode)}. No analysis starts until you submit. Live refers to model inference, not market data."
        )
        submit = st.form_submit_button("Analyse and save run", type="primary")
    if submit:
        try:
            decision = parse_cutoff(cutoff)
            with st.spinner("Analysing evidence and saving the trace…"):
                options = {"repeat_run": True} if repeat else {}
                run = analyse_article(
                    article_id, decision, ExecutionPolicy(policy), dependencies, **options
                )
            st.session_state["selected_run"] = run.run_id
            st.success(f"{label(run.status)} · {label(run.mode)}")
            if run.error:
                st.error(run.error)
            result_summary(run)
            st.button(
                "Open saved result",
                on_click=navigate,
                args=("Saved runs", run.run_id),
                type="primary",
            )
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")


def saved_panel(dependencies):
    from market_events.experiments import is_explanation_run
    from market_events.exporting import case_payload
    from market_events.pipeline import explain_run

    storage = dependencies.storage
    section_intro(
        "SAVED RESEARCH",
        "Review a saved result",
        "Start with the headline assessment, then open the tabs to inspect source support, price evidence, model traces and separate later outcomes.",
    )
    workflow_strip("Saved runs")
    runs = list(reversed(storage.list_runs()))
    if not runs:
        st.info("No saved runs. Analysis is an explicit action.")
        st.button(
            "Choose an article", on_click=navigate, args=("Research",), key="empty_saved_research"
        )
        return
    articles = {a.article_id: a for a in storage.list_articles()}
    lookup = {r.run_id: r for r in runs}
    ids = list(lookup)
    selected = st.session_state.get("selected_run")
    if st.session_state.get("saved_run_choice") not in ids:
        st.session_state["saved_run_choice"] = selected if selected in ids else ids[0]
    run_id = st.selectbox(
        "Saved run",
        ids,
        key="saved_run_choice",
        format_func=lambda key: (
            f"{article_label(articles[lookup[key].article_id]) if lookup[key].article_id in articles else lookup[key].article_id} · {label(lookup[key].status)} · {key[:8]}"
        ),
    )
    run = lookup[run_id]
    payload = case_payload(storage, run)
    st.caption(
        f"{label(run.mode)} · {POLICIES[run.policy.value]} · cutoff {run.decision_time.astimezone(IST):%d %b %Y, %H:%M IST}"
    )
    if run.error:
        st.error(run.error)
    if run.parent_run_id:
        st.caption(f"Parent run: {run.parent_run_id}")
    if is_explanation_run(run):
        st.info(
            "Optional explanation trace. Source and deterministic assessment are inherited from the parent analysis; the mode above describes this explanation request."
        )
        stored_explanation = run.config_snapshot.get("explanation_result")
        if isinstance(stored_explanation, dict) and stored_explanation.get("text"):
            st.write("Saved optional model explanation")
            st.write(stored_explanation["text"])
            with st.expander("Explanation support passages"):
                for span in stored_explanation.get("source_spans", []):
                    st.text(span)
        elif run.status == "explanation_completed":
            st.info("This older explanation trace has no stored explanation text.")
    result_summary(run)
    evidence, fusion, trace, outcome = st.tabs(
        ["Source & event", "Price evidence", "Audit trail", "Later outcome"]
    )
    with evidence:
        article = storage.get_article(run.article_id)
        if article:
            st.write("Source identifier:", article.source_url)
            with st.expander("Read the original article"):
                st.text(article.text)
            st.caption(
                f"Published {article.published_at.astimezone(IST).isoformat()} · First seen {article.first_seen_at.astimezone(IST).isoformat()}"
            )
        st.write("Dataset event memory")
        st.write(
            f"{label(run.memory.get('status', 'Not classified'))} · {run.memory.get('reason', '')}"
        )
        if run.memory.get("related_article_ids"):
            st.write("Related article IDs:", ", ".join(run.memory["related_article_ids"]))
        if run.filter_decision:
            st.write("Routing reason:", run.filter_decision.reason)
        if run.extraction:
            st.write(
                f"{label(run.extraction.event_type)} · Source support: {label(run.extraction.validation_status)}"
            )
            for span in run.extraction.source_spans:
                st.text(span)
        with st.expander("Advanced · source identity and structured event records"):
            if article:
                st.caption(
                    f"Article {article.article_id} · Version {article.source_version} · SHA256 {article.content_hash}"
                )
            st.json(run.memory)
            if run.filter_decision:
                st.json(run.filter_decision.model_dump(mode="json"))
            if run.extraction:
                st.json(run.extraction.model_dump(mode="json"))
    with fusion:
        if run.assessment:
            result = run.assessment
            with st.expander("Optional · request a model explanation"):
                st.caption(
                    f"Uses current {label(dependencies.settings.mode)} settings and creates a separate trace. The saved assessment stays unchanged."
                )
                if st.button("Request optional explanation", key=f"explain-{run_id}"):
                    try:
                        with st.spinner("Requesting grounded explanation…"):
                            explanation = explain_run(run_id, dependencies)
                        st.write(explanation)
                        st.caption(
                            "Select the linked explanation child to revisit its saved text and trace."
                        )
                    except Exception as exc:
                        st.warning(
                            f"Optional explanation failed: {exc}. Showing the saved deterministic explanation."
                        )
                        st.write(result.explanation)
            with st.expander("Advanced · exact assessment and fusion rules"):
                st.json(result.model_dump(mode="json"))
        else:
            st.info("No assessment was produced; inspect routing and errors.")
        if run.features:
            st.dataframe(
                [
                    {
                        "Evidence input": label(key),
                        "Value": "Unavailable"
                        if value is None
                        else f"{value:.2%}"
                        if "return" in key
                        else f"{value:.2f}",
                    }
                    for key, value in run.features.values.items()
                ],
                use_container_width=True,
            )
            st.caption(
                "Returns above are percentages; relative volume is a ratio. Missing is not zero. Exported numerical returns remain fractions."
            )
            with st.expander("Referenced market observations and feature diagnostics"):
                st.write("Referenced market observations")
                st.caption(
                    "Only IDs saved in this run's feature or technical snapshots. UTC timestamps retain offsets; later sessions are excluded."
                )
                st.dataframe(payload["observations"], use_container_width=True)
                st.json(run.features.model_dump(mode="json"))
            if payload["missing_observation_ids"]:
                st.warning(
                    "Referenced observations unavailable in this workspace: "
                    + ", ".join(payload["missing_observation_ids"])
                )
        if run.exposure:
            st.write("Reviewed exposure assumption")
            st.write(run.exposure.reason or label(run.exposure.status))
            if run.exposure.rule:
                st.write(run.exposure.rule.relationship)
            with st.expander("Advanced · exact exposure mapping"):
                st.json(run.exposure.model_dump(mode="json"))
        if getattr(run, "technicals", None):
            st.write("Price indicators saved at this cutoff")
            technical_summary(run.technicals)
        else:
            st.caption(
                "No technical snapshot was recorded in this saved run. Use Explore price indicators for a separate local computation; it will not change this decision."
            )
    with trace:
        st.caption(
            "Replay timings and recorded tokens are not live inference performance measurements."
        )
        st.dataframe(dump(run.calls), use_container_width=True)
        with st.expander("Advanced · run identity, timings and frozen configuration"):
            st.json(
                {
                    "run_id": run.run_id,
                    "status": run.status,
                    "created_at": run.created_at.isoformat(),
                    "request_key": run.request_key,
                    "parent_run_id": run.parent_run_id,
                    "stage_durations_ms": run.stage_durations_ms,
                }
            )
            st.json(run.config_snapshot)
    with outcome:
        st.caption(
            "Separate hypothetical five-session outcome; does not revise the saved decision."
        )
        result = storage.get_outcome(run_id)
        if result:
            st.write(f"Outcome: {result.status.capitalize()}")
            cols = st.columns(2)
            cols[0].metric(
                "Hypothetical net return",
                f"{result.net_return:.2%}" if result.net_return is not None else "Unavailable",
            )
            cols[1].metric(
                "Benchmark return",
                f"{result.benchmark_return:.2%}"
                if result.benchmark_return is not None
                else "Unavailable",
            )
            st.write(result.reason)
            with st.expander("Advanced · outcome dates, prices and gross/net fields"):
                st.json(result.model_dump(mode="json"))
        else:
            st.info(
                "Not evaluated. Open Compare research runs and choose Evaluate later outcomes. Incomplete horizons remain pending."
            )
    st.download_button(
        "Export this case · JSON",
        json.dumps(payload, indent=2),
        file_name=f"case-{run_id}.json",
        mime="application/json",
    )


INDICATORS = {
    "rsi14": "RSI · 14 sessions",
    "sma20": "Simple moving average · 20 sessions",
    "sma50": "Simple moving average · 50 sessions",
    "ema20": "Exponential moving average · 20 sessions",
    "macd_line": "MACD · 12/26 line",
    "macd_signal": "MACD · 9-session signal",
    "macd_histogram": "MACD · line minus signal",
    "bollinger20_middle": "Bollinger bands · middle",
    "bollinger20_upper": "Bollinger bands · upper",
    "bollinger20_lower": "Bollinger bands · lower",
    "atr14": "Average true range · 14 sessions",
    "adx14": "Average directional index · 14 sessions",
}


def technical_summary(snapshot):
    st.caption(
        f"Computed at cutoff {snapshot.decision_time.astimezone(IST):%d %b %Y, %H:%M IST} · {snapshot.history_bars} eligible daily bars · {snapshot.definition_version}"
    )
    if snapshot.stale:
        st.warning(
            "This history is stale at the selected cutoff. Values remain visible for audit; they do not describe current conditions. Import or explicitly refresh newer completed sessions."
        )
    if snapshot.missing:
        st.info(
            "Some indicators are unavailable because history is insufficient, conflicting or inconsistent. Indicator warm-ups need 15 to 50 daily bars, but enough bars alone do not guarantee a valid series. Missing values are never replaced with zero; review each exact explanation below."
        )
    cols = st.columns(3)
    for col, key in zip(cols, ("rsi14", "sma20", "macd_histogram")):
        value = snapshot.values.get(key)
        col.metric(INDICATORS[key], f"{value:.2f}" if value is not None else "Unavailable")
    st.dataframe(
        [
            {
                "Indicator": INDICATORS.get(key, label(key)),
                "Value": f"{value:.4f}" if value is not None else "Unavailable",
                "Status": "Stale history"
                if key in snapshot.stale
                else "Unavailable"
                if value is None
                else "Available",
                "Minimum daily bars": snapshot.required_history.get(key),
                "Interpretation / limitation": snapshot.interpretation.get(key, ""),
            }
            for key, value in snapshot.values.items()
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "RSI and ADX use a 0–100 scale; ADX describes strength, not direction. Moving averages, bands, MACD and ATR use the instrument's price units. These are descriptive indicators, not advice or forecasts. Warm-up and corporate-action conventions can differ across charting services."
    )
    with st.expander("Advanced · exact technical snapshot and observation references"):
        st.json(snapshot.model_dump(mode="json"))


def technicals_panel(dependencies):
    from market_events.config import read_companies
    from market_events.technicals import compute_technicals

    section_intro(
        "LOCAL QUANT TOOLS",
        "Explore price indicators",
        "Calculate trend, momentum and volatility context from imported daily prices. No article, API token or language model is required; calculations stay local and cutoff-safe.",
    )
    workflow_strip("Research")
    observations = dependencies.storage.list_observations()
    observations = [
        row
        for row in observations
        if row.market_family == "equity"
        and row.instrument_id.startswith("LIVE:") == (dependencies.settings.universe == "live")
    ]
    ids = sorted({row.instrument_id for row in observations})
    if not ids:
        st.info(
            "No equity history in this universe yet. Import a market CSV, or configure and explicitly refresh provider data. The demo has short synthetic history and will show honest warm-up gaps."
        )
        st.button(
            "Import price history", on_click=navigate, args=("Import",), key="technical_import"
        )
        st.button(
            "Set up a data connection",
            on_click=navigate,
            args=("Connections",),
            key="technical_connect",
        )
        return
    names = {
        company["instrument_id"]: company["name"]
        for company in read_companies(dependencies.settings)
    }
    company_id = st.selectbox(
        "Price history company", ids, format_func=lambda key: f"{names.get(key, key)} · {key}"
    )
    bars = [row for row in observations if row.instrument_id == company_id]
    now = datetime.now(timezone.utc)
    completed = [row for row in bars if row.timestamp <= now and row.available_at <= now]
    cols = st.columns(3)
    cols[0].metric("Imported daily bars", len(bars))
    cols[1].metric(
        "Latest completed imported session",
        max(row.timestamp for row in completed).astimezone(IST).strftime("%d %b %Y")
        if completed
        else "Unavailable",
    )
    cols[2].metric(
        "Latest recorded availability",
        max(row.available_at for row in bars).astimezone(IST).strftime("%d %b %Y, %H:%M"),
    )
    report = st.session_state.get("sync_report")
    st.caption(
        f"Last explicit fetch in this session: {report['fetched_at']}"
        if report
        else "No provider fetch recorded in this session. Availability timestamps come from imported records and are not proof of a connection check."
    )
    with st.form("technical_compute"):
        cutoff = st.text_input(
            "Indicator cutoff · ISO timestamp with offset",
            value=datetime.now(IST).replace(microsecond=0).isoformat(),
            key="technical_cutoff",
            help="Only sessions and availability times at or before this cutoff are eligible. Current aware time is the default; historical provider rows first fetched today are unavailable at earlier cutoffs.",
        )
        submitted = st.form_submit_button("Compute price indicators", type="primary")
    if submitted:
        try:
            st.session_state["technical_result"] = compute_technicals(
                observations, parse_cutoff(cutoff), company_id
            )
        except Exception as exc:
            st.session_state.pop("technical_result", None)
            st.error(
                f"Indicators could not be computed: {exc}. Check the timestamp offset and imported history, then submit again."
            )
    snapshot = st.session_state.get("technical_result")
    if snapshot is not None and snapshot.company_id == company_id:
        technical_summary(snapshot)
        selected = set(snapshot.observation_ids)
        prices = [
            {"Session": row.timestamp.astimezone(IST), "Close": row.close}
            for row in sorted(bars, key=lambda row: row.timestamp)
            if row.observation_id in selected
        ]
        if prices:
            st.write("Price history used by this computation")
            st.line_chart(prices, x="Session", y="Close")
            st.caption(
                f"{bars[0].currency} per {bars[0].unit}. Only saved supporting observation IDs are charted; no future rows are added."
            )
    else:
        st.info(
            "Choose a cutoff and compute to view the eligible price chart and indicator summary. Changing controls does not fetch data or run a model."
        )


def connections_panel(dependencies):
    from market_events.pipeline import analyse_synced_news, readiness

    section_intro(
        "DATA CONNECTIONS",
        "Connect and refresh data",
        "Check configuration first, then explicitly refresh selected provider data. A configured token is never presented as proof of a successful connection.",
    )
    workflow_strip("Import")
    try:
        from market_events.live_data import get_live_universe, sync_live
    except ModuleNotFoundError as exc:
        if exc.name != "market_events.live_data":
            raise
        st.info(
            "The provider adapter is being integrated. You can still import local price history and compute indicators without a connection."
        )
        st.button("Import local prices", on_click=navigate, args=("Import",), key="adapter_import")
        return
    st.write(
        "Set credentials in your local environment using docs/LIVE_SETUP.md. Tokens are never entered or displayed here. Price indicators work with local imports even without a connection."
    )
    states = readiness(dependencies)
    st.dataframe(
        [
            {
                "Capability": row["name"],
                "Configuration": "Configured" if row["configured"] else "Not configured",
                "Can request now": "Yes" if row["ready"] else "Setup or data needed",
                "Next step": row["reason"],
            }
            for row in states
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Configuration checks only. Token configured does not mean connection verified. No network verification or model request occurs while viewing this page."
    )
    live = dependencies.settings.universe == "live"
    if not live:
        st.info(
            "Select Real provider companies in Advanced workspace settings before refreshing. Provider LIVE IDs remain separate from synthetic demo IDs."
        )
    companies = [
        row
        for row in get_live_universe(dependencies.settings)
        if row.get("market_family") == "equity"
    ]
    lookup = {row["instrument_id"]: row for row in companies}
    can_sync = live and any(
        row["capability"] == "market_history" and row["ready"] for row in states
    )
    with st.form("sync_live_data"):
        ids = st.multiselect(
            "Provider companies",
            list(lookup),
            default=list(lookup),
            format_func=lambda key: f"{lookup[key]['name']} · {key}",
        )
        include_news = st.checkbox("Also import company news", value=True)
        st.caption(
            "Requests 550 calendar days of completed daily history. This action contacts the provider and saves returned evidence; it does not run language models."
        )
        submitted = st.form_submit_button(
            "Refresh selected data", type="primary", disabled=not can_sync
        )
    if submitted:
        if not ids:
            st.error("Select at least one company before refreshing.")
        else:
            try:
                with st.spinner("Fetching and importing provider evidence…"):
                    st.session_state["sync_report"] = sync_live(
                        dependencies, ids, lookback_days=550, include_news=include_news
                    )
                st.session_state.pop("batch_report", None)
            except Exception:
                st.session_state.pop("sync_report", None)
                st.error(
                    "Refresh failed before a report was returned. Check local connection settings and retry explicitly. No model analysis was started."
                )
    report = st.session_state.get("sync_report")
    if not report:
        st.info(
            "Connection verification: not checked in this session. An explicit refresh is required to test access and retain a result."
        )
        return
    st.caption(
        f"Last explicit refresh: {report.get('fetched_at', 'Unavailable')} · {report.get('provider', '')} · {report.get('data_source', '')}"
    )
    cols = st.columns(2)
    cols[0].metric("New price observations", report.get("observations_added", 0))
    cols[1].metric("New articles", report.get("articles_added", 0))
    if report.get("errors"):
        st.warning(
            "The last refresh had errors. Successfully imported evidence remains available; review per-company failures before using it."
        )
        st.dataframe(report["errors"], use_container_width=True, hide_index=True)
    elif report.get("network_requests", 0):
        st.success(
            "The last explicit refresh completed without reported errors. This result applies to that request, not future connection availability."
        )
    for warning in report.get("warnings", []):
        st.warning(warning)
    with st.expander("Advanced · latest provider report, universe and coverage"):
        st.json(report)
    st.button(
        "Explore imported price indicators",
        on_click=navigate,
        args=("Technicals",),
        key="sync_technicals",
    )
    article_ids = report.get("article_ids", [])
    if article_ids:
        with st.expander("Optional · analyse news from this refresh"):
            st.caption(
                "This is a separate bounded model action. Only article IDs returned by this refresh are eligible. Configure both models, select live execution, then explicitly submit."
            )
            with st.form("analyse_synced"):
                policy = st.selectbox(
                    "Synced-news policy",
                    list(POLICIES),
                    index=2,
                    format_func=lambda value: POLICIES[value],
                )
                ready = (
                    live
                    and dependencies.settings.mode == "live"
                    and any(row["capability"] == "event_models" and row["ready"] for row in states)
                )
                analyse = st.form_submit_button(
                    "Analyse synced news · up to 10 articles", disabled=not ready
                )
            if analyse:
                try:
                    with st.spinner("Analysing the explicitly synced articles…"):
                        st.session_state["batch_report"] = analyse_synced_news(
                            dependencies,
                            article_ids,
                            parse_cutoff(report["decision_time"]),
                            policy=policy,
                            limit=10,
                        )
                except Exception:
                    st.error(
                        "News analysis could not start. Check live mode, model IDs and the refresh cutoff, then submit explicitly again."
                    )
            if st.session_state.get("batch_report"):
                st.dataframe(
                    st.session_state["batch_report"], use_container_width=True, hide_index=True
                )
                st.button(
                    "Review batch results",
                    on_click=navigate,
                    args=("Saved runs",),
                    key="batch_saved",
                )


def comparisons_panel(dependencies):
    from market_events.experiments import run_experiments
    from market_events.pipeline import compute_outcomes

    section_intro(
        "COMPARISONS",
        "Compare saved research runs",
        "Review descriptive policy summaries, matched-input cohorts, commodity ablations and later outcomes without changing the original saved decisions.",
    )
    workflow_strip("Comparisons")
    if st.button("Evaluate later outcomes"):
        try:
            with st.spinner("Evaluating eligible future sessions…"):
                results = compute_outcomes(dependencies)
            st.success(f"Evaluated {len(results)} outcomes; incomplete horizons remain pending.")
        except Exception as exc:
            st.error(f"Outcome evaluation failed: {exc}")
    report = run_experiments(dependencies)
    if not report["policy_summary"]:
        st.info(
            "No analyses to compare yet. Analyse an article or load the recorded demo first. Comparison views do not start inference."
        )
        st.button(
            "Choose an article", on_click=navigate, args=("Research",), key="compare_research"
        )
        return
    st.write("Execution policy · replay/live separated")
    display_summary = [
        {**row, "policy": POLICIES.get(row["policy"], row["policy"]), "mode": label(row["mode"])}
        for row in report["policy_summary"]
    ]
    st.dataframe(display_summary, use_container_width=True, hide_index=True)
    if report["policy_summary"]:
        st.bar_chart(display_summary, x="policy", y="calls", color="mode")
    with st.expander("Common article / cutoff cohorts"):
        st.caption(
            "All three policies means present, including failed runs. Configuration fingerprints compare saved snapshots except local root/database paths; missing snapshots are not a match. Review statuses, actual model identities and source versions before interpreting a cohort."
        )
        st.dataframe(report["matched_inputs"], use_container_width=True)
    st.write("Commodity ablation · same saved inputs")
    st.caption(
        "Sensitivity analysis reruns deterministic fusion only. Requires saved fusion rules; missing inputs remain explicit."
    )
    st.dataframe(report["ablations"], use_container_width=True)
    with st.expander("Optional explanation usage · separate from analyses"):
        st.dataframe(report["explanation_summary"], use_container_width=True)
    with st.expander("Saved run manifest"):
        st.dataframe(report["run_manifest"], use_container_width=True)
    st.write("Later outcomes")
    st.dataframe(report["outcomes"], use_container_width=True)
    st.download_button(
        "Export comparisons · JSON",
        json.dumps(report, indent=2),
        file_name="research-comparisons.json",
        mime="application/json",
    )


def main():
    st.set_page_config(page_title="Market Events | Research workbench", layout="wide")
    st.markdown(
        """<style>
    .stApp {--workbench-blue:#60a5fa;--workbench-blue-dark:#2563eb;--workbench-amber:#fbbf24;--workbench-ink:#0f172a;--workbench-muted:#94a3b8;}
    .block-container {padding-top:2.2rem;padding-bottom:3rem;max-width:1440px;}
    .product-header {display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:1.4rem;padding-bottom:1rem;border-bottom:1px solid rgba(148,163,184,.18);}
    .brand-lockup {display:flex;align-items:center;gap:.8rem;}
    .brand-mark {display:grid;place-items:center;width:2.35rem;height:2.35rem;border-radius:.75rem;background:linear-gradient(135deg,#60a5fa,#2563eb);color:#eff6ff;font-weight:800;letter-spacing:-.06em;box-shadow:0 10px 24px rgba(37,99,235,.28);}
    .brand-name {font-size:1.1rem;font-weight:750;letter-spacing:-.02em;}
    .brand-subtitle {color:var(--workbench-muted);font-size:.8rem;margin-top:.15rem;}
    .product-badge,.eyebrow {color:#fbbf24;font-size:.7rem;font-weight:750;letter-spacing:.12em;text-transform:uppercase;}
    .product-badge {padding:.42rem .7rem;border:1px solid rgba(251,191,36,.28);border-radius:999px;background:rgba(251,191,36,.08);white-space:nowrap;}
    .section-intro {margin:.4rem 0 1.1rem;max-width:900px;}
    .section-intro h2 {margin:.25rem 0 .35rem;font-size:2rem;letter-spacing:-.04em;}
    .section-intro p {color:#cbd5e1;max-width:780px;line-height:1.6;margin:0;}
    .hero-panel,.next-step-panel {border:1px solid rgba(96,165,250,.25);border-radius:1rem;padding:1.25rem 1.4rem;background:linear-gradient(135deg,rgba(37,99,235,.2),rgba(15,23,42,.55));box-shadow:0 14px 34px rgba(2,6,23,.18);}
    .hero-panel {display:flex;justify-content:space-between;gap:2rem;align-items:flex-start;margin:1rem 0 1.3rem;}
    .hero-panel h3,.next-step-panel h3 {margin:.3rem 0 .45rem;font-size:1.2rem;letter-spacing:-.02em;}
    .hero-panel p,.next-step-panel p {color:#cbd5e1;line-height:1.55;margin:0;max-width:760px;}
    .hero-kicker {color:#93c5fd;font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;}
    .hero-note {min-width:220px;padding:.85rem 1rem;border-radius:.75rem;background:rgba(15,23,42,.58);border:1px solid rgba(148,163,184,.16);color:#cbd5e1;font-size:.82rem;line-height:1.45;}
    .hero-note strong {color:#f8fafc;}
    .workflow-strip {display:flex;gap:.55rem;flex-wrap:wrap;margin:0 0 1.2rem;}
    .workflow-step {display:flex;align-items:center;gap:.45rem;padding:.42rem .65rem;border:1px solid rgba(148,163,184,.16);border-radius:999px;background:rgba(30,41,59,.55);color:#94a3b8;font-size:.74rem;}
    .workflow-step b {color:#cbd5e1;font-weight:700;}
    .workflow-step small {font-size:.72rem;}
    .workflow-step.active {border-color:rgba(96,165,250,.55);background:rgba(37,99,235,.18);color:#dbeafe;}
    .workflow-step.active b {color:#bfdbfe;}
    .workspace-context {display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;margin:.8rem 0 1rem;padding:.55rem .75rem;border:1px solid rgba(148,163,184,.14);border-radius:.6rem;background:rgba(15,23,42,.32);color:#94a3b8;font-size:.78rem;overflow-wrap:anywhere;}
    .next-step-panel {margin:1.25rem 0 .8rem;padding:1.15rem 1.35rem;}
    div[data-testid="stMetric"] {background:linear-gradient(145deg,rgba(30,41,59,.96),rgba(15,23,42,.96));padding:1rem;border:1px solid rgba(148,163,184,.14);border-radius:.8rem;box-shadow:0 8px 24px rgba(2,6,23,.12);}
    div[data-testid="stMetricLabel"] {color:#94a3b8;}
    div[data-testid="stMetricValue"] {letter-spacing:-.04em;}
    div[data-testid="stExpander"] {border-color:rgba(148,163,184,.18);}
    .stButton > button {border-radius:.65rem;font-weight:650;min-height:2.55rem;transition:transform .15s ease,box-shadow .15s ease;}
    .stButton > button:hover {transform:translateY(-1px);box-shadow:0 8px 18px rgba(2,6,23,.2);}
    button:focus-visible, input:focus-visible, textarea:focus-visible {outline:3px solid #fbbf24!important;outline-offset:3px;}
    @media (max-width: 800px) {.hero-panel {flex-direction:column;}.hero-note {min-width:0;width:100%;}.product-badge {display:none;}.section-intro h2 {font-size:1.65rem;}}
    </style>""",
        unsafe_allow_html=True,
    )
    app_header()
    st.caption(
        "Research prototype · synthetic demo and provider imports are separate · no trading advice or predictive validation"
    )
    with st.sidebar:
        st.header("Your workspace")
        with st.expander("Advanced · workspace and execution settings"):
            root = Path(
                st.text_input("Project root", value=str(Path(__file__).resolve().parent))
            ).expanduser()
            database = Path(
                st.text_input("SQLite database path", value="data/market_events.sqlite")
            ).expanduser()
            mode = st.radio(
                "Model execution mode",
                ["replay", "live"],
                format_func=label,
                help="Replay uses recorded fixture responses. Live calls configured providers only after explicit submission.",
            )
            universe = st.radio(
                "Company universe",
                ["demo", "live"],
                key="universe_selection",
                format_func=lambda value: (
                    "Synthetic demo / local imports"
                    if value == "demo"
                    else "Real provider companies · LIVE identifiers"
                ),
                help="Provider IDs are separate from demo IDs. Selecting a universe does not fetch data.",
            )
        st.caption("Changing controls never starts model inference.")
        open_workspace = st.button("Open workspace")
        st.caption(
            "Use the main-area demo to start without keys. Configure credentials in your local environment, never in this dashboard."
        )
        st.markdown("---")
        st.markdown("**Workflow**")
        st.caption("Start → Import → Research → Review → Compare")
    try:
        from market_events.config import load_settings
        from market_events.pipeline import Dependencies, run_demo
        from market_events.storage import Storage

        root = root.resolve()
        path = (database if database.is_absolute() else root / database).resolve()
        workspace = (str(root), str(path))
        active = st.session_state.get("workspace") == workspace
        current_view = st.session_state.get("workbench_view", "Start")
        demo = (
            start_panel(active=active)
            if not active and current_view == "Start" and not open_workspace
            else False
        )
        if demo:
            with st.spinner("Loading explicitly synthetic replay…"):
                demo_runs = run_demo(root=root, database_path=path)
            navigate("Saved runs", next((run.run_id for run in demo_runs if run.assessment), None))
            st.success(
                "Three synthetic event families are ready. Start with the summary; open the evidence tabs when you want details."
            )
        if not (demo or open_workspace) and st.session_state.get("workspace") != workspace:
            st.info(
                "Open a workspace to import or inspect local data, or explicitly load the synthetic demo. Opening this page does not create a database."
            )
            return
        settings = load_settings(root=root).model_copy(
            update={"database_path": path, "mode": mode, "universe": universe}
        )
        with Storage(path) as storage:
            dependencies = Dependencies(storage=storage, settings=settings)
            scope = (*workspace, universe)
            if st.session_state.get("evidence_scope") != scope:
                for key in list(st.session_state):
                    if key in {
                        "technical_result",
                        "sync_report",
                        "batch_report",
                        "technical_cutoff",
                    }:
                        del st.session_state[key]
                st.session_state["evidence_scope"] = scope
            if st.session_state.get("workspace") != workspace:
                st.session_state["workspace"] = workspace
            cols = st.columns(3)
            cols[0].metric("Imported articles", len(storage.list_articles()))
            cols[1].metric("Saved runs", len(storage.list_runs()))
            cols[2].metric("Price observations", len(storage.list_observations()))
            st.caption(
                f"Active company universe: {'synthetic demo / local imports' if universe == 'demo' else 'real provider companies (LIVE IDs)'}. Model execution: {label(mode)}."
            )
            st.markdown(
                f'<div class="workspace-context"><span class="eyebrow">ACTIVE WORKSPACE</span><span>{escape(str(path))}</span></div>',
                unsafe_allow_html=True,
            )
            section = st.sidebar.radio(
                "Workbench view",
                list(TASKS),
                format_func=lambda value: TASKS[value],
                key="workbench_view",
            )
            if section == "Start":
                workspace_overview(dependencies)
            elif section == "Import":
                import_panel(dependencies)
            elif section == "Research":
                research_panel(dependencies, mode)
            elif section == "Saved runs":
                saved_panel(dependencies)
            elif section == "Comparisons":
                comparisons_panel(dependencies)
            elif section == "Technicals":
                technicals_panel(dependencies)
            elif section == "Strategy lab":
                from market_events.lab_ui import render_strategy_lab

                render_strategy_lab(dependencies)
            elif section == "Connections":
                connections_panel(dependencies)
    except Exception as exc:
        st.error(f"Workspace unavailable: {exc}")
        st.caption(
            "Check local paths, installed dependencies and provider configuration. No replay fallback is substituted for failed live inference."
        )


if __name__ == "__main__":
    main()
