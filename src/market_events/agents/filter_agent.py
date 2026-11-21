"""SLM filtering and validation of delegated source passages."""

from ..schemas import Article, FilterDecision


def filter_article(article: Article, client, role="slm", context=None) -> FilterDecision:
    decision = client.ask("filter", article, FilterDecision, role=role, context=context)
    if any(not span.strip() or span not in article.text for span in decision.source_spans):
        decision.relevance = "uncertain"
        decision.source_spans = []
        decision.candidate_entities = []
        decision.reason = "Unsupported SLM passages: escalate using the complete source"
    if decision.relevance == "irrelevant" and not decision.source_spans:
        decision.relevance = "uncertain"
        decision.reason = "Unsupported rejection: escalate for review"
    return decision
