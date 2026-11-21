import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from market_events.exposure import find_exposure, resolve_company
from market_events.schemas import Article, EventExtraction, ExposureRule, FilterDecision

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


def test_aliases_and_ambiguity():
    companies = json.loads((ROOT / "configs/companies.json").read_text())
    assert resolve_company([" asian paints "], companies) == "NSE:ASIANPAINT"
    assert resolve_company(["Asian Paints", "Indigo"], companies) is None
    assert resolve_company(["Asian"], companies) is None


def test_exposure_time_vintages_and_ties():
    rule = ExposureRule.model_validate(
        json.loads((ROOT / "configs/exposure_rules.json").read_text())[0]
    )
    event = EventExtraction(
        event_id="e",
        event_type="commodity_supply_disruption",
        company_id=rule.company_id,
        commodity_id=rule.commodity_id,
    )
    future = rule.model_copy(update={"known_at": CUTOFF.replace(day=13), "direction": 1})
    assert find_exposure(event, [future], CUTOFF).status == "missing"
    assert find_exposure(event, [rule, future], CUTOFF).rule == rule
    tied = rule.model_copy(update={"rule_id": "conflict", "direction": 1})
    assert find_exposure(event, [rule, tied], CUTOFF).status == "ambiguous"
    newer = rule.model_copy(update={"effective_at": CUTOFF, "rule_id": "new"})
    assert find_exposure(event, [newer, rule], CUTOFF).rule == newer


def test_fixture_schema_and_source_support():
    articles = [
        Article.model_validate_json(line)
        for line in (ROOT / "tests/fixtures/articles.jsonl").read_text().splitlines()
    ]
    replay = json.loads((ROOT / "tests/fixtures/recorded_model_outputs.json").read_text())
    assert len(articles) >= 30
    assert len({a.article_id for a in articles}) == len(articles)
    for article in articles:
        assert "SYNTHETIC" in article.text
        assert article.first_seen_at <= CUTOFF
        assert article.source_url.startswith("https://example.invalid/")
        output = replay[article.article_id]
        extracted = EventExtraction.model_validate(output["extraction"])
        filtered = FilterDecision.model_validate(output["filter"])
        assert all(span in article.text for span in extracted.source_spans + filtered.source_spans)


@pytest.mark.parametrize("field", ["relationship", "source", "version", "rule_id"])
def test_latest_mapping_requires_review_evidence(field):
    rule = ExposureRule.model_validate(
        json.loads((ROOT / "configs/exposure_rules.json").read_text())[0]
    )
    event = EventExtraction(
        event_id="e",
        event_type="commodity_supply_disruption",
        company_id=rule.company_id,
        commodity_id=rule.commodity_id,
    )
    incomplete = rule.model_copy(update={field: "   ", "effective_at": CUTOFF})
    result = find_exposure(event, [rule, incomplete], CUTOFF)
    assert result.status == "missing"
    assert "review" in result.reason.lower()


def test_selected_exposure_is_an_independent_snapshot_at_cutoff():
    rule = ExposureRule.model_validate(
        json.loads((ROOT / "configs/exposure_rules.json").read_text())[0]
    )
    rule.effective_at = rule.known_at = CUTOFF
    event = EventExtraction(
        event_id="e",
        event_type="commodity_supply_disruption",
        company_id=rule.company_id,
        commodity_id=rule.commodity_id,
    )
    result = find_exposure(event, [rule], CUTOFF)
    assert result.status == "matched"
    before = result.model_dump_json()
    rule.source = "Changed after selection"
    assert result.model_dump_json() == before


def test_future_effective_rule_and_exact_duplicates():
    rule = ExposureRule.model_validate(
        json.loads((ROOT / "configs/exposure_rules.json").read_text())[0]
    )
    event = EventExtraction(
        event_id="e",
        event_type="commodity_supply_disruption",
        company_id=rule.company_id,
        commodity_id=rule.commodity_id,
    )
    future = rule.model_copy(update={"effective_at": CUTOFF.replace(day=13)})
    assert find_exposure(event, [future], CUTOFF).status == "missing"
    assert find_exposure(event, [rule, rule.model_copy(deep=True)], CUTOFF).rule == rule
