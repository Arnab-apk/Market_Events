"""Optional plain-language explanation of a saved assessment. The model may only restate the
deterministic explanation and cite the saved source passages; any change is rejected. It never
alters the original decision.
"""

from pydantic import BaseModel, ConfigDict


# Structured answer for the explanation task. Keep this class without a
# docstring: its JSON schema is sent in the live prompt and hashed into
# request_hash, so a docstring would silently change model requests.
class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation: str
    citations: list[str]


def explain_assessment(article, run, client):
    """Return the model's explanation, or raise if it rewrites the saved values."""
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
