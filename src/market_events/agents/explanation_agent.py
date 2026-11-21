"""Optional constrained explanation, with deterministic values remaining authoritative."""

from pydantic import BaseModel, ConfigDict


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation: str
    citations: list[str]


def explain_assessment(article, run, client):
    context = {
        "assessment": run.assessment.model_dump(mode="json"),
        "source_spans": run.extraction.source_spans,
    }
    result = client.ask("explanation", article, Explanation, context=context)
    if (
        result.explanation != run.assessment.explanation
        or result.citations != run.extraction.source_spans
    ):
        raise ValueError("Optional explanation changed the saved assessment or its citations")
    return result.explanation
