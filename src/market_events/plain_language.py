"""Plain-English wording for saved runs, for display only.

It turns a saved run's frozen assessment inputs (components, weights, features and
exposure) into a one-sentence summary, a readable list of reasons and the score
arithmetic. Nothing here is persisted or changes a decision: the saved explanation
stays the audit record, and these strings are rebuilt from it on every API read.
"""

REASONS = {
    "Missing or stale mandatory equity excess return": (
        "The stock's return relative to its benchmark was not available, or was too old, "
        "at the cutoff."
    ),
    "Missing or ambiguous mandatory reviewed exposure": (
        "There is no single reviewed rule for how this company is exposed to the commodity, "
        "so the commodity move cannot be given a direction."
    ),
    "Missing or stale mandatory commodity return": (
        "The commodity's price move for the same session was not yet available, or was too "
        "old, at the cutoff."
    ),
    "Coverage below configured minimum": "Too little of the required evidence was available.",
    "Event extraction is not validated": (
        "The extracted event could not be fully matched to the article text."
    ),
    "Unsupported event family": (
        "The article does not describe a supported event (earnings, an order or a commodity "
        "supply disruption)."
    ),
    "Company unresolved or inconsistent with market features": (
        "The company could not be identified unambiguously from the article."
    ),
    "Unresolved source version history": (
        "The article's version history is unclear, so the assessment is withheld."
    ),
    "Equity and exposure-adjusted commodity evidence disagree": (
        "The stock's own move and the commodity's implied effect point in opposite directions."
    ),
}

STATUS_SUMMARIES = {
    "irrelevant": "The filter found no supported financial event in this article, so nothing was scored.",
    "duplicate": "This article repeats an earlier source; the earlier analysis stands and nothing new was scored.",
    "ineligible": "The article was not yet published or seen at the chosen cutoff, so it cannot be used.",
    "partial": "The analysis stopped at its model-call budget before an assessment was made.",
    "failed": "The analysis failed before an assessment was made; see the error for details.",
    "interrupted": "The analysis was interrupted before an assessment was made.",
    "started": "The analysis did not finish.",
}

EVENT_NAMES = {
    "earnings": "earnings report",
    "order_announcement": "order announcement",
    "commodity_supply_disruption": "commodity supply disruption",
}


def plain_reason(reason: str) -> str:
    """Plain-English version of one saved abstention or conflict reason."""
    if reason in REASONS:
        return REASONS[reason]
    prefix = "Missing or stale mandatory "
    if reason.startswith(prefix):
        return f"A required input ({reason[len(prefix) :]}) was not available at the cutoff."
    return reason


def commodity_name(commodity_id: str | None) -> str:
    """Readable commodity name, e.g. 'crude oil' for any crude contract identifier."""
    if not commodity_id:
        return "the commodity"
    return "crude oil" if "CRUDE" in commodity_id.upper() else commodity_id


def _signed(value: float) -> str:
    """Two-decimal signed number with a typographic minus, e.g. '−0.50'."""
    return f"{value:+.2f}".replace("-", "−")


def _percent(value: float) -> str:
    return f"{abs(value) * 100:.1f}%"


def _company_name(run) -> str:
    company_id = run.extraction.company_id if run.extraction else None
    companies = run.config_snapshot.get("companies.json") or []
    match = next((c for c in companies if c.get("instrument_id") == company_id), None)
    return (match or {}).get("name") or company_id or "the company"


def score_formula(assessment) -> str | None:
    """The score arithmetic, e.g. '0.6 × (+0.40 equity) + 0.4 × (−0.50 crude oil) = +0.04'."""
    inputs = assessment.inputs or {}
    components = inputs.get("components") or {}
    weights = inputs.get("weights") or {}
    if not components or assessment.evidence_score is None:
        return None
    commodity = (inputs.get("exposure") or {}).get("rule") or {}
    labels = {
        "equity": "equity vs benchmark",
        "commodity": f"{commodity_name(commodity.get('commodity_id'))}, exposure-adjusted",
    }
    terms = [
        f"{weights.get(key, 0):.1f} × ({_signed(value)} {labels.get(key, key)})"
        for key, value in sorted(components.items(), key=lambda item: item[0] != "equity")
    ]
    expression = " + ".join(terms)
    valid = sum(weights.get(key, 0) for key in components)
    if abs(valid - 1) > 1e-9:
        expression = f"({expression}) ÷ {valid:.1f}"
    threshold = (inputs.get("rules") or {}).get("threshold", 0.15)
    outcome = (
        "withheld (abstain)"
        if assessment.direction == "abstain"
        else f"{assessment.direction} (threshold ±{threshold:.2f})"
    )
    return f"{expression} = {_signed(assessment.evidence_score)} → {outcome}"


def describe_run(run) -> dict:
    """API-only plain-language fields for one saved run.

    Returns ``plain_summary`` (one sentence or None), ``plain_reasons`` (abstention
    and conflict reasons in plain English) and ``score_formula`` (or None).
    """
    assessment = run.assessment
    if run.status.startswith("explanation_"):
        return {
            "plain_summary": "Optional model explanation of an earlier saved run; its evidence is unchanged.",
            "plain_reasons": [],
            "score_formula": None,
        }
    if assessment is None:
        return {
            "plain_summary": STATUS_SUMMARIES.get(run.status),
            "plain_reasons": [],
            "score_formula": None,
        }
    reasons = [plain_reason(r) for r in assessment.abstention_reasons + assessment.conflicts]
    company = _company_name(run)
    if assessment.direction == "abstain":
        first = reasons[0] if reasons else "Mandatory evidence was missing."
        summary = f"No assessment for {company}: {first[0].lower() + first[1:]}"
        return {
            "plain_summary": summary,
            "plain_reasons": reasons,
            "score_formula": score_formula(assessment),
        }
    inputs = assessment.inputs or {}
    values = (inputs.get("features") or {}).get("values") or {}
    components = inputs.get("components") or {}
    excess = values.get("excess_return")
    if excess is None:
        equity = f"{company} had no usable benchmark-relative return"
    elif excess > 0:
        equity = f"{company} beat its benchmark by {_percent(excess)}"
    elif excess < 0:
        equity = f"{company} trailed its benchmark by {_percent(excess)}"
    else:
        equity = f"{company} moved in line with its benchmark"
    sentence = equity
    if "commodity" in components and values.get("commodity_return") is not None:
        rule = (inputs.get("exposure") or {}).get("rule") or {}
        move = values["commodity_return"]
        name = commodity_name(rule.get("commodity_id"))
        verb = "rose" if move > 0 else "fell" if move < 0 else "was flat"
        amount = f" {_percent(move)}" if move else ""
        effect = "counts against" if components["commodity"] < 0 else "supports"
        if components["commodity"] == 0:
            effect = "is neutral for"
        assumption = (
            "reviewed synthetic exposure assumption"
            if "synthetic" in str(rule.get("source", "")).lower()
            else "reviewed exposure rule"
        )
        connector = "but" if assessment.conflicts else "and"
        sentence += f", {connector} {name} {verb}{amount}, which {effect} it under its {assumption}"
    endings = {
        "positive": "so the evidence leans positive",
        "negative": "so the evidence leans negative",
        "neutral": "so the evidence is mixed (neutral)"
        if assessment.conflicts
        else "so the evidence is too weak to call (neutral)",
    }
    event_type = run.extraction.event_type if run.extraction else ""
    event = EVENT_NAMES.get(event_type, "event")
    if event_type == "commodity_supply_disruption":
        rule = (inputs.get("exposure") or {}).get("rule") or {}
        event = f"{commodity_name(rule.get('commodity_id') or run.extraction.commodity_id)} supply disruption"
    summary = f"After this {event}, {sentence}, {endings[assessment.direction]}."
    return {
        "plain_summary": summary,
        "plain_reasons": reasons,
        "score_formula": score_formula(assessment),
    }
