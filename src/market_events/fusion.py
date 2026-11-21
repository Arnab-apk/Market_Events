"""Deterministic evidence scoring (the 'fusion' step). It combines the equity reaction and, for
commodity events, the exposure-signed commodity move into a score in [-1, 1], with coverage,
conflicts and abstention reasons. Rules come from configs/fusion_rules.json; the score is
evidence, not a probability.
"""

import math
from copy import deepcopy

from .exposure import has_review_evidence
from .schemas import Assessment, EventExtraction, ExposureMatch, MarketFeatures


def assess_evidence(
    event: EventExtraction,
    exposure: ExposureMatch,
    features: MarketFeatures,
    rules: dict,
    include_commodity: bool = True,
) -> Assessment:
    """Weighted clipped fractional returns; mandatory failures always abstain."""
    # Nested dictionaries are mutable; keep the exact policy used by this assessment.
    rules = deepcopy(rules)
    version = rules.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Fusion rules require a nonempty version")
    weights = rules.get("weights", {"equity": 0.6, "commodity": 0.4})
    scales = rules.get("scales", {"equity": 0.02, "commodity": 0.03})
    threshold = rules.get("threshold", 0.15)
    minimum = rules.get("minimum_coverage", 0.6)

    def finite_number(value):
        return type(value) in (int, float) and math.isfinite(value)

    if (
        not isinstance(weights, dict)
        or not isinstance(scales, dict)
        or set(weights) != {"equity", "commodity"}
        or set(scales) != {"equity", "commodity"}
        or any(not finite_number(v) or v <= 0 for v in [*weights.values(), *scales.values()])
        or not math.isfinite(sum(weights.values()))
        or not finite_number(threshold)
        or not finite_number(minimum)
        or not 0 <= threshold <= 1
        or not 0 <= minimum <= 1
    ):
        raise ValueError("Invalid fusion weights, scales or thresholds")
    configured_required = rules.get("required_features", {})
    supported_features = {
        "equity_return",
        "benchmark_return",
        "excess_return",
        "relative_volume",
        "commodity_return",
        "exposure",
    }
    if not isinstance(configured_required, dict) or any(
        family not in {"earnings", "order_announcement", "commodity_supply_disruption"}
        or not isinstance(keys, list)
        or any(not isinstance(key, str) or key not in supported_features for key in keys)
        for family, keys in configured_required.items()
    ):
        raise ValueError("Invalid required_features configuration")
    cross_market = include_commodity and event.event_type == "commodity_supply_disruption"
    required = set(configured_required.get(event.event_type, [])) | {"excess_return"}
    if cross_market:
        required.update({"commodity_return", "exposure"})
    if not include_commodity:
        required.difference_update({"commodity_return", "exposure"})
    components = {}
    reasons = []

    def available(key):
        value = features.values.get(key)
        return (
            value is not None
            and math.isfinite(value)
            and key not in features.missing + features.stale
        )

    if available("excess_return"):
        components["equity"] = max(-1, min(1, features.values["excess_return"] / scales["equity"]))
    else:
        reasons.append("Missing or stale mandatory equity excess return")
    if "exposure" in required:
        rule = exposure.rule
        valid_mapping = (
            exposure.status == "matched"
            and rule is not None
            and has_review_evidence(rule)
            and rule.company_id == event.company_id
            and rule.commodity_id == event.commodity_id
            and rule.effective_at <= features.decision_time
            and rule.known_at <= features.decision_time
        )
        if not valid_mapping:
            reasons.append("Missing or ambiguous mandatory reviewed exposure")
    if "commodity_return" in required:
        if not available("commodity_return"):
            reasons.append("Missing or stale mandatory commodity return")
        elif cross_market and valid_mapping:
            components["commodity"] = max(
                -1,
                min(1, features.values["commodity_return"] * rule.direction / scales["commodity"]),
            )
    for key in sorted(required - {"excess_return", "commodity_return", "exposure"}):
        if not available(key):
            reasons.append(f"Missing or stale mandatory {key}")
    active_weights = weights if cross_market else {"equity": 1.0}
    total = sum(active_weights.values())
    valid_weight = sum(active_weights[k] for k in components)
    coverage = valid_weight / total
    score = (
        sum(active_weights[k] * v for k, v in components.items()) / valid_weight
        if components
        else None
    )
    if coverage < minimum:
        reasons.append("Coverage below configured minimum")
    if event.validation_status != "validated":
        reasons.append("Event extraction is not validated")
    if event.event_type not in {"earnings", "order_announcement", "commodity_supply_disruption"}:
        reasons.append("Unsupported event family")
    if not event.company_id or features.company_id != event.company_id:
        reasons.append("Company unresolved or inconsistent with market features")
    conflicts = (
        ["Equity and exposure-adjusted commodity evidence disagree"]
        if len(components) == 2 and components["equity"] * components["commodity"] < 0
        else []
    )
    direction = (
        "abstain"
        if reasons
        else (
            "positive" if score >= threshold else "negative" if score <= -threshold else "neutral"
        )
    )
    return Assessment(
        direction=direction,
        evidence_score=score,
        coverage=coverage,
        conflicts=conflicts,
        abstention_reasons=reasons,
        rules_version=version,
        inputs={
            "features": features.model_dump(mode="json"),
            "components": components,
            "weights": active_weights,
            "rules": rules,
            "include_commodity": include_commodity,
            "exposure": exposure.model_dump(mode="json"),
        },
        explanation=f"{direction}: evidence score {score}; coverage {coverage:.2f}. "
        + ("; ".join(reasons + conflicts) or "Mandatory evidence available.")
        + " Score is deterministic evidence, not a probability.",
    )
