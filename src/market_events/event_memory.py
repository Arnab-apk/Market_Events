"""Conservative, deterministic source memory within the collected dataset."""

from datetime import datetime

from market_events.schemas import Article, utc


def classify_article(article: Article, articles: list[Article], decision_time: datetime) -> dict:
    """Classify using only sources published AND first seen by the UTC cutoff.

    Exact normalized content takes precedence over an explicit predecessor. Only
    an explicit eligible predecessor proves an update; textual similarity alone
    never merges distinct events. 'New' refers solely to the supplied dataset.
    History is ordered by first seen and publication. At equal times, explicit
    ancestry precedes the article-ID tie break, so an update never becomes its
    own predecessor's duplicate merely because its ID sorts first.
    """
    cutoff = utc(decision_time)

    def result(status: str, related: list[str], reason: str) -> dict:
        return {"status": status, "related_article_ids": sorted(set(related)), "reason": reason}

    if article.published_at > cutoff or article.first_seen_at > cutoff:
        return result("unresolved", [], "Article was not published and first seen by the cutoff")
    available = {
        previous.article_id: previous
        for previous in articles
        if previous.published_at <= cutoff and previous.first_seen_at <= cutoff
    }
    available[article.article_id] = article

    def ancestors(item: Article) -> set[str]:
        identifiers = set()
        while item.predecessor_id and item.predecessor_id not in identifiers:
            identifiers.add(item.predecessor_id)
            previous = available.get(item.predecessor_id)
            if previous is None:
                break
            item = previous
        return identifiers

    lineage = ancestors(article)
    if article.article_id in lineage:
        return result("unresolved", [], "Explicit predecessor history is cyclic")

    def precedes(previous: Article) -> bool:
        previous_time = (previous.first_seen_at, previous.published_at)
        article_time = (article.first_seen_at, article.published_at)
        if previous_time != article_time:
            return previous_time < article_time

        # Rank equal-time ancestors before their descendants, then use IDs for
        # independent sources. A total order avoids duplicate cycles when an
        # unrelated copy arrives alongside an unchanged source update.
        def rank(item: Article) -> tuple[int, str]:
            depth = sum(
                1
                for identifier in ancestors(item)
                if identifier in available
                and (available[identifier].first_seen_at, available[identifier].published_at)
                == article_time
            )
            return depth, item.article_id

        return rank(previous) < rank(article)

    eligible = [
        previous
        for previous in available.values()
        if previous.article_id != article.article_id and precedes(previous)
    ]
    duplicates = [item.article_id for item in eligible if item.content_hash == article.content_hash]
    if duplicates:
        return result(
            "duplicate", duplicates, "Exact normalized-content duplicate in eligible history"
        )
    if article.predecessor_id:
        predecessor = next(
            (item for item in eligible if item.article_id == article.predecessor_id), None
        )
        if predecessor is None:
            return result(
                "unresolved", [], "Explicit predecessor is missing, self-referential or ineligible"
            )
        return result(
            "update", [predecessor.article_id], "Explicit predecessor has different content"
        )
    same_source = [item.article_id for item in eligible if item.source_url == article.source_url]
    if same_source:
        return result(
            "unresolved",
            same_source,
            "Source has different content without an explicit predecessor",
        )
    return result(
        "new", [], "No exact duplicate or explicit predecessor within eligible dataset history"
    )
