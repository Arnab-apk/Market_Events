"""Descriptive comparisons over saved runs, for the policy-comparison view. It summarises usage per
policy, re-runs equity-only versus equity+commodity ablations on saved inputs, and checks
extraction agreement with authored gold labels. It never calls a model or changes the database,
and makes no claim of predictive validation.
"""

import hashlib
import json
from collections import Counter, defaultdict
from math import isfinite
from pathlib import Path
from statistics import mean

from market_events.fusion import assess_evidence


def is_explanation_run(run):
    """Explanation children inherit evidence but are not new policy analyses."""
    return run.status.startswith("explanation_") or bool(
        run.config_snapshot.get("explanation_parent_run_id")
    )


def configuration_fingerprint(run):
    """Compare saved settings/evidence hashes, ignoring only local filesystem paths."""
    snapshot = {
        key: value
        for key, value in run.config_snapshot.items()
        if key not in {"root", "database_path"}
    }
    if not snapshot:
        return None
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def summarize_policies(runs, prices=None):
    """Keep analysis modes separate; optional explanation usage has its own table."""
    return _summarize_runs([run for run in runs if not is_explanation_run(run)], prices)


def load_model_prices(root):
    """Optional configs/model_prices.json; absent or unreadable means no cost estimate."""
    filename = Path(root) / "configs" / "model_prices.json"
    if not filename.exists():
        return None
    try:
        return json.loads(filename.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _price_lookup(prices):
    table = {}
    for entry in (prices or {}).get("models", []):
        try:
            rates = (float(entry["input_per_1k"]), float(entry["output_per_1k"]))
        except (KeyError, TypeError, ValueError):
            continue
        if all(isfinite(rate) and rate >= 0 for rate in rates):
            table[(entry.get("provider"), entry.get("model"))] = rates
    return table


def estimated_cost(mode, calls, prices):
    """Live calls with complete reported usage and a configured rate only.

    Missing token counts are never filled in, and replay calls never get a cost.
    """
    table = _price_lookup(prices)
    if mode != "live" or not calls or not table:
        return None
    total = 0.0
    for call in calls:
        rates = table.get((call.provider, call.model))
        if call.mode != "live" or rates is None:
            return None
        if call.input_tokens is None or call.output_tokens is None:
            return None
        total += call.input_tokens / 1000 * rates[0] + call.output_tokens / 1000 * rates[1]
    return total


def _summarize_runs(runs, prices=None):
    groups = defaultdict(list)
    for run in runs:
        groups[(run.mode, run.policy.value)].append(run)
    rows = []
    for (mode, policy), members in sorted(groups.items()):
        calls = [call for run in members for call in run.calls]
        mismatches = sum(call.mode != mode for call in calls)
        known = not mismatches and all(
            c.input_tokens is not None and c.output_tokens is not None for c in calls
        )
        cost = estimated_cost(mode, calls, prices) if known else None
        rows.append(
            {
                "mode": mode,
                "policy": policy,
                "runs": len(members),
                "calls": len(calls),
                "failed_calls": sum(c.status not in ("success", "completed", "ok") for c in calls),
                "mismatched_mode_calls": mismatches,
                "input_tokens": sum(c.input_tokens for c in calls) if known and calls else None,
                "output_tokens": sum(c.output_tokens for c in calls) if known and calls else None,
                "usage_complete": bool(calls) and known,
                "estimated_cost": cost,
                "cost_currency": (prices or {}).get("currency") if cost is not None else None,
                "mean_run_latency_ms": mean(r.latency_ms for r in members),
                "assessed_runs": sum(r.assessment is not None for r in members),
                "abstentions": sum(
                    r.assessment is not None and r.assessment.direction == "abstain"
                    for r in members
                ),
            }
        )
    return rows


def compare_ablations(runs, rules=None):
    """Reassess identical saved inputs with the run's frozen rules when present.

    A supplied rules dictionary is an explicit fallback, labelled as such. Saved
    assessments and outcomes are never changed; these are sensitivity results.
    """
    rows = []
    for run in runs:
        if is_explanation_run(run):
            continue
        frozen = run.config_snapshot.get(
            "fusion_rules.json", run.config_snapshot.get("fusion_rules")
        )
        if not isinstance(frozen, dict) and run.assessment:
            frozen = run.assessment.inputs.get("rules")
        selected_rules = frozen if isinstance(frozen, dict) else rules
        if (
            not run.extraction
            or not run.exposure
            or not run.features
            or not selected_rules
            or run.memory.get("status") == "unresolved"
        ):
            rows.append(
                {
                    "run_id": run.run_id,
                    "mode": run.mode,
                    "policy": run.policy.value,
                    "status": "unavailable",
                    "reason": "Source history is unresolved."
                    if run.memory.get("status") == "unresolved"
                    else "Requires extraction, exposure, features and explicit fusion rules.",
                }
            )
            continue
        try:
            variants = [
                assess_evidence(
                    run.extraction,
                    run.exposure,
                    run.features,
                    selected_rules,
                    include_commodity=include,
                )
                for include in (False, True)
            ]
        except (ValueError, TypeError, KeyError) as exc:
            rows.append(
                {
                    "run_id": run.run_id,
                    "mode": run.mode,
                    "policy": run.policy.value,
                    "status": "unavailable",
                    "reason": f"Saved inputs/rules cannot be reassessed: {exc}",
                }
            )
            continue
        for include, result in zip((False, True), variants):
            rows.append(
                {
                    "run_id": run.run_id,
                    "mode": run.mode,
                    "policy": run.policy.value,
                    "variant": "equity + commodity" if include else "equity only",
                    "status": "computed",
                    "rules_source": "saved snapshot"
                    if isinstance(frozen, dict)
                    else "supplied rules",
                    "saved_direction": run.assessment.direction if run.assessment else None,
                    "saved_status": run.status,
                    "direction": result.direction,
                    "evidence_label": result.evidence_label,
                    "evidence_score": result.evidence_score,
                    "coverage": result.coverage,
                    "rules_version": result.rules_version,
                    "abstention_reasons": result.abstention_reasons,
                }
            )
    return rows


AGREEMENT_LABEL = "Synthetic sanity check on authored articles, not a benchmark"


def load_gold_labels(root):
    """Authored gold labels for the bundled synthetic articles, when present."""
    filename = Path(root) / "tests" / "fixtures" / "gold_labels.json"
    if not filename.exists():
        return None
    try:
        return json.loads(filename.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rate(numerator, denominator):
    return numerator / denominator if denominator else None


def extraction_agreement(runs, gold):
    """Read-only agreement of saved filter/extraction outputs with authored labels.

    A filter decision counts as forwarded unless it is ``irrelevant``: ``uncertain``
    continues to extraction in every policy, so it is a positive for recall and
    precision and is also reported as an escalation (uncertain) rate. Field accuracy
    compares saved extractions with gold ``event_type``, ``company_id`` and
    ``commodity_id``. Runs whose article has no gold label are counted, not scored.
    Returns None when no saved analysis run has a gold label.
    """
    labels = (gold or {}).get("labels", {})
    groups = defaultdict(list)
    unlabelled = 0
    for run in runs:
        if is_explanation_run(run):
            continue
        if run.article_id not in labels:
            unlabelled += 1
            continue
        groups[(run.mode, run.policy.value)].append(run)
    if not groups:
        return None
    rows = []
    fields = ("event_type", "company_id", "commodity_id")
    for (mode, policy), members in sorted(groups.items()):
        tp = fp = fn = tn = uncertain = 0
        filtered = [run for run in members if run.filter_decision is not None]
        for run in filtered:
            relevant = labels[run.article_id]["relevance"] == "relevant"
            forwarded = run.filter_decision.relevance != "irrelevant"
            uncertain += run.filter_decision.relevance == "uncertain"
            tp += relevant and forwarded
            fp += forwarded and not relevant
            fn += relevant and not forwarded
            tn += not relevant and not forwarded
        extracted = [run for run in members if run.extraction is not None]
        accuracy = {
            field: _rate(
                sum(
                    getattr(run.extraction, field) == labels[run.article_id].get(field)
                    for run in extracted
                ),
                len(extracted),
            )
            for field in fields
        }
        statuses = Counter(run.extraction.validation_status for run in extracted)
        assessed = [run for run in members if run.assessment is not None]
        reasons = Counter(
            reason
            for run in assessed
            if run.assessment.direction == "abstain"
            for reason in run.assessment.abstention_reasons
        )
        rows.append(
            {
                "mode": mode,
                "policy": policy,
                "runs": len(members),
                "filter_decisions": len(filtered),
                "not_reaching_filter": len(members) - len(filtered),
                "filter_recall": _rate(tp, tp + fn),
                "filter_precision": _rate(tp, tp + fp),
                "filter_confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
                "uncertain_rate": _rate(uncertain, len(filtered)),
                "extractions": len(extracted),
                "field_accuracy": accuracy,
                "validation_status_rates": {
                    status: _rate(statuses[status], len(extracted))
                    for status in ("validated", "unresolved", "unsupported")
                },
                "assessed_runs": len(assessed),
                "abstention_rate": _rate(
                    sum(run.assessment.direction == "abstain" for run in assessed), len(assessed)
                ),
                "abstention_reasons": dict(sorted(reasons.items())),
            }
        )
    return {
        "label": AGREEMENT_LABEL,
        "gold_version": (gold or {}).get("version"),
        "gold_provenance": (gold or {}).get("provenance"),
        "unlabelled_runs": unlabelled,
        "groups": rows,
        "notes": [
            "Gold labels were authored for the bundled synthetic articles; no human agreement "
            "(Cohen's kappa) was measured.",
            "Recorded replay returns the same fixture output for every policy, so replay rows "
            "cannot show policy differences; only live runs can.",
            "Forwarded means the filter did not mark the article irrelevant; uncertain items "
            "continue to extraction.",
        ],
    }


def run_experiments(dependencies):
    """Export descriptive evidence only; no claim of predictive validation."""
    runs = dependencies.storage.list_runs()
    lookup = {run.run_id: run for run in runs}
    outcomes = []
    for outcome in dependencies.storage.list_outcomes():
        run = lookup.get(outcome.run_id)
        outcomes.append(
            {
                **outcome.model_dump(mode="json"),
                "mode": run.mode if run else None,
                "policy": run.policy.value if run else None,
                "article_id": run.article_id if run else None,
                "decision_time": run.decision_time.isoformat() if run else None,
            }
        )
    settings = getattr(dependencies, "settings", None)
    root = getattr(settings, "root", None)
    prices = load_model_prices(root) if root is not None else None
    gold = load_gold_labels(root) if root is not None else None
    return {
        "provenance": "Saved runs; synthetic replay is not real-data validation.",
        "policy_summary": summarize_policies(runs, prices),
        "explanation_summary": _summarize_runs(
            [run for run in runs if is_explanation_run(run)], prices
        ),
        "extraction_agreement": extraction_agreement(runs, gold) if gold else None,
        "run_manifest": [
            {
                "run_id": run.run_id,
                "article_id": run.article_id,
                "mode": run.mode,
                "policy": run.policy.value,
                "status": run.status,
                "decision_time": run.decision_time.isoformat(),
                "parent_run_id": run.parent_run_id,
                "run_kind": "explanation" if is_explanation_run(run) else "analysis",
                "configuration_fingerprint": configuration_fingerprint(run),
            }
            for run in runs
        ],
        "matched_inputs": matched_policy_inputs(runs),
        "ablations": compare_ablations(runs),
        "outcomes": outcomes,
    }


def matched_policy_inputs(runs):
    """Expose cohorts, rather than implying unpaired aggregate fairness."""
    groups = defaultdict(list)
    for run in runs:
        if is_explanation_run(run):
            continue
        groups[(run.mode, run.article_id, run.decision_time.isoformat())].append(run)
    return [
        {
            "mode": key[0],
            "article_id": key[1],
            "decision_time": key[2],
            "policies": sorted({r.policy.value for r in members}),
            "run_ids": [r.run_id for r in members],
            "configuration_variants": len({configuration_fingerprint(run) for run in members}),
            "same_saved_configuration": all(configuration_fingerprint(run) for run in members)
            and len({configuration_fingerprint(run) for run in members}) == 1,
            "statuses": sorted({run.status for run in members}),
            "all_three_policies": len({r.policy.value for r in members}) == 3,
        }
        for key, members in sorted(groups.items())
    ]
