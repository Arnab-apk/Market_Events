"""Step 1 of an analysis: relevance filtering, usually by the small model (SLM). The filter decides
whether an article describes a supported event. Any passage it quotes must appear in the article;
unsupported quotes or rejections are escalated as ``uncertain`` instead of being trusted.
"""

from ..schemas import Article, FilterDecision


def filter_article(article: Article, client, role="slm", context=None) -> FilterDecision:
    """Ask for a relevance decision and downgrade unsupported answers."""
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
