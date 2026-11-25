"""Prioritize saved cases. Case facts and links always come from the ledger."""

from pydantic import BaseModel, ConfigDict, Field

from ..model_client import ModelError


class CaseSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_ids: list[str] = Field(max_length=3)


def prioritize_cases(client, topic, runs):
    evidence = []
    for run in runs:
        assessment = run.assessment
        features = run.features
        evidence.append(
            {
                "run_id": run.run_id,
                "decision_time": run.decision_time.isoformat(),
                "direction": assessment.direction,
                "coverage": assessment.coverage,
                "conflicts": len(assessment.conflicts),
                "abstention_reasons": len(assessment.abstention_reasons),
                "missing_inputs": len(features.missing) if features else 0,
                "stale_inputs": len(features.stale) if features else 0,
            }
        )
    selection = client.ask(
        "portfolio_review", None, CaseSelection, context={"topic": topic, "cases": evidence}
    )
    ids = selection.run_ids
    if len(set(ids)) != len(ids) or not set(ids) <= {run.run_id for run in runs}:
        raise ModelError("The model selected a case outside the supplied evidence")
    return selection
