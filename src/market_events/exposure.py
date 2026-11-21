"""Exact reviewed alias resolution and historically available exposure selection."""

from datetime import datetime

from .schemas import EventExtraction, ExposureMatch, ExposureRule, utc


def has_review_evidence(rule: ExposureRule) -> bool:
    """Required review metadata must contain text, not merely exist in the schema."""
    return all(
        value.strip()
        for value in (
            rule.company_id,
            rule.commodity_id,
            rule.relationship,
            rule.source,
            rule.version,
            rule.rule_id,
        )
    )


def resolve_company(candidates: list[str], companies: list[dict]) -> str | None:
    """Return one canonical match; conflicting or shared aliases remain unresolved."""
    names = {name.strip().casefold() for name in candidates if name.strip()}
    matches = {
        company["instrument_id"]
        for company in companies
        if names
        & {
            str(x).strip().casefold()
            for x in [company["instrument_id"], company["name"], *company.get("aliases", [])]
        }
    }
    return next(iter(matches)) if len(matches) == 1 else None


def find_exposure(
    event: EventExtraction, rules: list[ExposureRule], decision_time: datetime
) -> ExposureMatch:
    """Select the latest effective vintage known at cutoff, never a future revision."""
    cutoff = utc(decision_time)
    if event.event_type != "commodity_supply_disruption" and not event.commodity_id:
        return ExposureMatch(status="not_required", reason="No commodity relationship requested")
    eligible = [
        r
        for r in rules
        if r.company_id == event.company_id
        and r.commodity_id == event.commodity_id
        and r.effective_at <= cutoff
        and r.known_at <= cutoff
    ]
    if not eligible:
        return ExposureMatch(status="missing", reason="No eligible reviewed exposure at cutoff")
    vintage = max((r.effective_at, r.known_at) for r in eligible)
    latest = {r.model_dump_json(): r for r in eligible if (r.effective_at, r.known_at) == vintage}
    if len(latest) != 1:
        return ExposureMatch(status="ambiguous", reason="Multiple rules at latest eligible vintage")
    selected = next(iter(latest.values()))
    if not has_review_evidence(selected):
        return ExposureMatch(
            status="missing", reason="Latest eligible exposure lacks review evidence"
        )
    return ExposureMatch(status="matched", rule=selected.model_copy(deep=True))
