"""Structured extraction with source grounding and canonical entity checks."""

import hashlib
import re

from ..exposure import resolve_company
from ..schemas import Article, EventExtraction


def _present(alias: str, text: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.IGNORECASE))


def extract_event(article: Article, client, companies=None, delegated=None) -> EventExtraction:
    companies = companies or []
    context = {"companies": companies}
    if delegated:
        # Reuse only verified hints. The full source remains available to preserve negation/units.
        context["delegated"] = delegated.model_dump(exclude={"trace_id"})
    event = client.ask("extraction", article, EventExtraction, context=context)
    event.event_id = (
        "evt-"
        + hashlib.sha256(f"{article.article_id}:{article.source_version}".encode()).hexdigest()[:20]
    )
    event.source_version = article.source_version
    unsupported = not event.source_spans or any(
        not span.strip() or span not in article.text for span in event.source_spans
    )
    for amount in event.amounts:
        span = amount.source_span
        value, unit = str(amount.value), amount.unit
        # Numerals may serialize as 100.0 while source says 100; match numeric tokens exactly.
        if isinstance(amount.value, float) and amount.value.is_integer():
            value = str(int(amount.value))
        has_value = bool(re.search(r"(?<![\w.])" + re.escape(value) + r"(?![\w.])", span))
        scale_supported = not amount.scale or _present(amount.scale, span)
        if (
            not span
            or span not in article.text
            or not has_value
            or not _present(unit, span)
            or not scale_supported
        ):
            unsupported = True
    if unsupported:
        event.validation_status = "unsupported"
        event.reason = "Extraction has missing or unsupported passages/amount units"
        return event
    candidates = []
    for company in companies:
        aliases = [company["instrument_id"], company["name"], *company.get("aliases", [])]
        if any(_present(alias, article.text) for alias in aliases):
            candidates.append(company["instrument_id"])
    resolved = resolve_company(candidates, companies)
    if event.company_id and event.company_id != resolved:
        event.company_id = None
    else:
        event.company_id = resolved
    event.validation_status = "validated" if event.company_id else "unresolved"
    if not event.company_id:
        event.reason = "Company is absent or ambiguous in the original source; review required"
    return event
