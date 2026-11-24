"""Paper-portfolio screener. Turns saved evidence assessments plus cutoff-safe technicals into a
ranked shortlist using the reviewed rules in configs/screener_rules.json. Only runs decided at or
before the cutoff are used; a missing or stale value fails its rule. Research only, not advice.
"""

import json
import math
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from .schemas import AnalysisRun, ScreenResult, ScreenRow, TechnicalSnapshot, utc
from .technicals import REQUIRED_HISTORY

ASSESSMENT_NUMERIC = {"evidence_score", "coverage"}
TEXT_FIELDS = {"direction"}
NUMERIC_FIELDS = ASSESSMENT_NUMERIC | set(REQUIRED_HISTORY)
ORDER_OPS = {">=", "<=", ">", "<"}
OPS = ORDER_OPS | {"==", "!=", "in"}
CONFIG_KEYS = {"version", "use_latest_run_per_company", "rules", "rank_by", "max_shortlist"}


def _finite(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def validate_screener_rules(rules: dict) -> dict:
    """Return a private copy of valid screener rules; raise ValueError otherwise."""
    if not isinstance(rules, dict):
        raise ValueError("Screener rules must be a JSON object")
    rules = deepcopy(rules)
    unknown = set(rules) - CONFIG_KEYS
    if unknown:
        raise ValueError(f"Unknown screener rule keys: {sorted(unknown)}")
    version = rules.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Screener rules require a nonempty version")
    if not isinstance(rules.get("use_latest_run_per_company", True), bool):
        raise ValueError("use_latest_run_per_company must be true or false")
    items = rules.get("rules")
    if not isinstance(items, list) or not items:
        raise ValueError("Screener rules require a nonempty 'rules' list")
    for item in items:
        if not isinstance(item, dict) or set(item) != {"field", "op", "value"}:
            raise ValueError(f"Each rule needs exactly field, op and value: {item!r}")
        field, op, value = item["field"], item["op"], item["value"]
        if field not in NUMERIC_FIELDS | TEXT_FIELDS:
            raise ValueError(f"Unknown screener field: {field!r}")
        if op not in OPS:
            raise ValueError(f"Unknown screener op: {op!r}")
        numeric = field in NUMERIC_FIELDS
        if op == "in":
            ok = (
                isinstance(value, list)
                and value
                and all(_finite(v) if numeric else isinstance(v, str) for v in value)
            )
        elif op in ORDER_OPS:
            ok = numeric and _finite(value)
        else:
            ok = _finite(value) if numeric else isinstance(value, str)
        if not ok:
            raise ValueError(f"Invalid value for rule {field} {op}: {value!r}")
    if rules.get("rank_by") not in NUMERIC_FIELDS:
        raise ValueError("rank_by must be a known numeric field")
    shortlist = rules.get("max_shortlist")
    if type(shortlist) is not int or shortlist < 1:
        raise ValueError("max_shortlist must be a positive integer")
    rules.setdefault("use_latest_run_per_company", True)
    return rules


def load_screener_rules(root: Path = Path(".")) -> dict:
    """Read and validate configs/screener_rules.json."""
    path = Path(root) / "configs" / "screener_rules.json"
    return validate_screener_rules(json.loads(path.read_text(encoding="utf-8")))


def _technical_values(snapshot) -> dict:
    """Usable technical values; stale, missing and non-finite values are left out."""
    if snapshot is None:
        return {}
    if isinstance(snapshot, TechnicalSnapshot):
        skip = set(snapshot.stale) | set(snapshot.missing)
        values = {k: v for k, v in snapshot.values.items() if k not in skip}
    elif isinstance(snapshot, Mapping):
        values = dict(snapshot)
    else:
        raise ValueError("Technicals must be a TechnicalSnapshot or a mapping of values")
    return {k: v for k, v in values.items() if _finite(v)}


def _check(item: dict, value) -> dict:
    field, op, limit = item["field"], item["op"], item["value"]
    label = f"{field} {op} {json.dumps(limit) if isinstance(limit, list) else limit}"
    if value is None:
        return {
            "rule": label,
            "value": None,
            "limit": limit,
            "passed": False,
            "margin": None,
            "reason": "missing or stale value",
        }
    passed = {
        ">=": lambda: value >= limit,
        "<=": lambda: value <= limit,
        ">": lambda: value > limit,
        "<": lambda: value < limit,
        "==": lambda: value == limit,
        "!=": lambda: value != limit,
        "in": lambda: value in limit,
    }[op]()
    margin = None
    if _finite(value) and _finite(limit):
        margin = {
            ">=": value - limit,
            ">": value - limit,
            "<=": limit - value,
            "<": limit - value,
            "==": -abs(value - limit),
            "!=": abs(value - limit),
        }[op]
    return {"rule": label, "value": value, "limit": limit, "passed": passed, "margin": margin}


def screen(
    assessment_rows: list[AnalysisRun],
    technicals: Mapping[str, TechnicalSnapshot | Mapping[str, float | None]],
    rules: dict,
    as_of: datetime,
) -> ScreenResult:
    """Screen the latest cutoff-safe run per company and rank the passing ones."""
    rules = validate_screener_rules(rules)
    cutoff = utc(as_of)
    eligible = [
        run
        for run in assessment_rows
        if run.assessment is not None
        and run.extraction is not None
        and run.extraction.company_id
        and run.decision_time <= cutoff
    ]
    eligible.sort(key=lambda run: (run.decision_time, run.created_at, run.run_id))
    if rules["use_latest_run_per_company"]:
        eligible = list({run.extraction.company_id: run for run in eligible}.values())
    rows = []
    for run in eligible:
        company = run.extraction.company_id
        assessment = run.assessment
        values = {
            "evidence_score": assessment.evidence_score
            if _finite(assessment.evidence_score)
            else None,
            "coverage": assessment.coverage,
            "direction": assessment.direction,
            **{
                k: v
                for k, v in _technical_values(technicals.get(company)).items()
                if k in REQUIRED_HISTORY
            },
        }
        checks = []
        if assessment.direction == "abstain":
            reasons = "; ".join(assessment.abstention_reasons) or "no reason given"
            checks.append(
                {
                    "rule": f"abstained: {reasons}",
                    "value": None,
                    "limit": None,
                    "passed": False,
                    "margin": None,
                }
            )
        checks += [_check(item, values.get(item["field"])) for item in rules["rules"]]
        rows.append(
            ScreenRow(
                company_id=company,
                instrument_id=company,
                passed=all(check["passed"] for check in checks),
                checks=checks,
                score=values.get(rules["rank_by"]),
                run_id=run.run_id,
            )
        )
    passed = sorted(
        (row for row in rows if row.passed and row.score is not None),
        key=lambda row: (-row.score, row.company_id, row.run_id or ""),
    )
    for rank, row in enumerate(passed, start=1):
        row.rank = rank
    for row in rows:
        if row.passed and row.score is None:
            row.passed = False  # Cannot rank on missing data.
    failed = sorted(
        (row for row in rows if row.rank is None), key=lambda r: (r.company_id, r.run_id or "")
    )
    shortlist = []
    for row in passed:
        if row.instrument_id not in shortlist and len(shortlist) < rules["max_shortlist"]:
            shortlist.append(row.instrument_id)
    return ScreenResult(
        as_of=cutoff, rules_version=rules["version"], rows=passed + failed, shortlist=shortlist
    )
