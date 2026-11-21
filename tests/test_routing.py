"""Meaningful grounding checks: unsupported extraction never becomes valid."""

from datetime import datetime, timezone

from market_events.agents.event_agent import extract_event
from market_events.agents.filter_agent import filter_article
from market_events.schemas import Article, EventExtraction, FilterDecision


def article(text="Asian Paints announced earnings of INR 100 crore."):
    now = datetime(2026, 1, 12, 8, tzinfo=timezone.utc)
    return Article(
        article_id="a",
        source_url="https://example.invalid/a",
        text=text,
        published_at=now,
        first_seen_at=now,
    )


class Client:
    def __init__(self, output):
        self.output = output

    def ask(self, *args, **kwargs):
        return self.output


COMPANIES = [
    {
        "instrument_id": "NSE:ASIANPAINT",
        "name": "Asian Paints",
        "aliases": ["Asian Paints"],
        "sector": "materials",
        "benchmark_id": "b",
    }
]


def test_unsupported_filter_rejection_escalates():
    result = filter_article(
        article(),
        Client(FilterDecision(relevance="irrelevant", reason="x", source_spans=["invented"])),
    )
    assert result.relevance == "uncertain"
    assert result.source_spans == []


def test_extraction_requires_actual_quote_and_units():
    output = EventExtraction(
        event_id="x",
        event_type="earnings",
        company_id="NSE:ASIANPAINT",
        source_spans=["invented"],
        validation_status="validated",
    )
    assert extract_event(article(), Client(output), COMPANIES).validation_status == "unsupported"
    output = EventExtraction(
        event_id="x",
        event_type="earnings",
        company_id="NSE:ASIANPAINT",
        source_spans=[article().text],
        amounts=[{"value": 100, "unit": "USD", "source_span": article().text}],
    )
    assert extract_event(article(), Client(output), COMPANIES).validation_status == "unsupported"


def test_entity_cannot_be_hallucinated_and_alias_needs_boundary():
    source = article("Asian Paints announced earnings.")
    output = EventExtraction(
        event_id="x", event_type="earnings", company_id="NSE:OTHER", source_spans=[source.text]
    )
    result = extract_event(source, Client(output), COMPANIES)
    assert result.company_id is None
    assert result.validation_status == "unresolved"


def test_valid_source_resolves_canonical_company():
    source = article()
    output = EventExtraction(event_id="x", event_type="earnings", source_spans=[source.text])
    result = extract_event(source, Client(output), COMPANIES)
    assert result.company_id == "NSE:ASIANPAINT"
    assert result.validation_status == "validated"
