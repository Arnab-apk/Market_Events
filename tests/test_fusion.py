import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from market_events.fusion import assess_evidence
from market_events.schemas import (
    Assessment,
    EventExtraction,
    EventOutcome,
    ExposureMatch,
    ExposureRule,
    MarketFeatures,
)

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    rules = json.loads((ROOT / "configs/fusion_rules.json").read_text())
    rule = ExposureRule.model_validate(
        json.loads((ROOT / "configs/exposure_rules.json").read_text())[0]
    )
    event = EventExtraction(
        event_id="e",
        event_type="commodity_supply_disruption",
        company_id=rule.company_id,
        commodity_id=rule.commodity_id,
        validation_status="validated",
    )
    features = MarketFeatures(
        decision_time=datetime(2026, 1, 12, 12, tzinfo=timezone.utc),
        company_id=rule.company_id,
        values={"excess_return": 0.02, "commodity_return": 0.03},
    )
    return event, ExposureMatch(status="matched", rule=rule), features, rules


def test_clipped_conflict_determinism_and_ablation():
    event, exposure, features, rules = inputs()
    assessment = assess_evidence(event, exposure, features, rules)
    assert assessment.evidence_score == pytest.approx(0.2)
    assert assessment.direction == "positive"
    assert assessment.coverage == 1
    assert assessment.conflicts
    assert assessment == assess_evidence(event, exposure, features, rules)
    assert assess_evidence(event, exposure, features, rules, False).evidence_score == 1
    event.direction = "negative"
    assert assess_evidence(event, exposure, features, rules) == assessment


@pytest.mark.parametrize("failure", ["commodity", "equity", "mapping", "stale", "unvalidated"])
def test_mandatory_gates(failure):
    event, exposure, features, rules = inputs()
    if failure == "commodity":
        features.values["commodity_return"] = None
    elif failure == "equity":
        features.values["excess_return"] = None
    elif failure == "mapping":
        exposure = ExposureMatch(status="missing")
    elif failure == "stale":
        features.stale = ["excess_return"]
    else:
        event.validation_status = "unsupported"
    assert assess_evidence(event, exposure, features, rules).direction == "abstain"


def test_earnings_only_and_version_requirement():
    event, exposure, features, rules = inputs()
    event.event_type = "earnings"
    features.values["commodity_return"] = None
    assert assess_evidence(event, exposure, features, rules).coverage == 1
    with pytest.raises(ValueError):
        assess_evidence(event, exposure, features, {})


@pytest.mark.parametrize(
    "missing_key, expected_score, expected_coverage",
    [("commodity_return", 1.0, 0.6), ("excess_return", -1.0, 0.4)],
)
def test_score_uses_valid_weights_but_coverage_uses_expected_weights(
    missing_key, expected_score, expected_coverage
):
    event, exposure, features, rules = inputs()
    features.values[missing_key] = None
    result = assess_evidence(event, exposure, features, rules)
    assert result.evidence_score == pytest.approx(expected_score)
    assert result.coverage == pytest.approx(expected_coverage)
    assert result.direction == "abstain"


def test_no_valid_components_has_no_score():
    event, exposure, features, rules = inputs()
    features.values = {}
    result = assess_evidence(event, exposure, features, rules)
    assert result.evidence_score is None
    assert result.coverage == 0
    assert result.direction == "abstain"


def test_reviewed_demo_expected_scores():
    expected = json.loads((ROOT / "tests/fixtures/expected_demo_outputs.json").read_text())
    assert expected["syn-001"]["assessment"]["evidence_score"] == pytest.approx(0.4)
    assert expected["syn-002"]["assessment"]["evidence_score"] == pytest.approx(0.04)
    assert expected["syn-002"]["assessment"]["direction"] == "neutral"
    assert expected["syn-002"]["assessment"]["conflicts"]
    assert expected["syn-003"]["assessment"]["direction"] == "positive"
    replay = json.loads((ROOT / "tests/fixtures/recorded_model_outputs.json").read_text())
    for article_id, case in expected.items():
        feature = MarketFeatures.model_validate(case["features"])
        assessment = Assessment.model_validate(case["assessment"])
        assert (
            assess_evidence(
                EventExtraction.model_validate(replay[article_id]["extraction"]),
                ExposureMatch.model_validate(assessment.inputs["exposure"]),
                feature,
                assessment.inputs["rules"],
            )
            == assessment
        )
        assert EventOutcome.model_validate(case["outcome"]).status == "completed"


def test_rules_and_weights_are_independent_assessment_snapshots():
    event, exposure, features, rules = inputs()
    result = assess_evidence(event, exposure, features, rules)
    before = result.model_dump_json()
    rules["weights"]["equity"] = 0.1
    rules["required_features"]["earnings"].append("relative_volume")
    features.values["excess_return"] = -0.02
    exposure.rule.source = "Changed after assessment"
    assert result.model_dump_json() == before


@pytest.mark.parametrize("field", ["relationship", "source", "version", "rule_id"])
def test_direct_fusion_cannot_use_incomplete_reviewed_mapping(field):
    event, exposure, features, rules = inputs()
    setattr(exposure.rule, field, " ")
    result = assess_evidence(event, exposure, features, rules)
    assert result.direction == "abstain"
    assert "commodity" not in result.inputs["components"]


@pytest.mark.parametrize("value", [None, 0.0])
def test_configured_additional_mandatory_feature_is_gated(value):
    event, exposure, features, rules = inputs()
    rules["required_features"][event.event_type].append("relative_volume")
    features.values["relative_volume"] = value
    result = assess_evidence(event, exposure, features, rules)
    assert result.direction == ("abstain" if value is None else "positive")
    if value is None:
        assert any("relative_volume" in reason for reason in result.abstention_reasons)


@pytest.mark.parametrize(
    "key, value",
    [
        ("scales", {}),
        ("scales", {"equity": 0.02}),
        ("weights", {"equity": "0.6", "commodity": 0.4}),
        ("weights", {"equity": 1e308, "commodity": 1e308}),
        ("threshold", None),
        ("minimum_coverage", float("nan")),
        ("required_features", {"earnings": ["unknown_feature"]}),
    ],
)
def test_bad_numerical_configuration_raises_readable_value_error(key, value):
    event, exposure, features, rules = inputs()
    rules[key] = value
    with pytest.raises(ValueError):
        assess_evidence(event, exposure, features, rules)


@pytest.mark.parametrize("field", ["company_id", "commodity_id", "known_at", "effective_at"])
def test_direct_mapping_identity_and_temporal_eligibility(field):
    event, exposure, features, rules = inputs()
    value = (
        features.decision_time.replace(day=13) if field.endswith("_at") else "different identity"
    )
    setattr(exposure.rule, field, value)
    assert assess_evidence(event, exposure, features, rules).direction == "abstain"


def test_config_cannot_remove_frozen_mandatory_evidence_and_ablation_is_explicit():
    event, exposure, features, rules = inputs()
    rules["required_features"][event.event_type] = []
    features.values["commodity_return"] = None
    assert assess_evidence(event, exposure, features, rules).direction == "abstain"
    assert assess_evidence(event, exposure, features, rules, False).direction == "positive"


@pytest.mark.parametrize("key", ["excess_return", "commodity_return", "relative_volume"])
def test_declared_stale_or_missing_feature_cannot_score_as_present(key):
    event, exposure, features, rules = inputs()
    rules["required_features"][event.event_type].append("relative_volume")
    features.values["relative_volume"] = 1.0
    for field in ("stale", "missing"):
        setattr(features, field, [key])
        assert assess_evidence(event, exposure, features, rules).direction == "abstain"
        setattr(features, field, [])


def test_zero_returns_are_valid_neutral_evidence():
    event, exposure, features, rules = inputs()
    features.values = {"excess_return": 0, "commodity_return": 0}
    result = assess_evidence(event, exposure, features, rules)
    assert result.coverage == 1
    assert result.evidence_score == 0
    assert result.direction == "neutral"
