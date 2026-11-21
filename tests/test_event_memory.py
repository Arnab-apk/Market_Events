"""Synthetic source histories must never introduce after-cutoff information."""

from datetime import datetime, timezone

import pytest

from market_events.event_memory import classify_article
from market_events.schemas import Article


CUTOFF = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


def source(identifier, **overrides):
    return Article.model_validate(
        {
            "article_id": identifier,
            "source_url": f"https://example.invalid/{identifier}",
            "text": "Synthetic earnings increase.",
            "published_at": "2026-01-12T09:00:00Z",
            "first_seen_at": "2026-01-12T09:01:00Z",
            **overrides,
        }
    )


def test_new_is_dataset_scoped_and_self_is_excluded():
    article = source("a")
    result = classify_article(article, [article], CUTOFF)
    assert result["status"] == "new"
    assert result["related_article_ids"] == []
    assert "dataset" in result["reason"]


def test_exact_duplicates_take_priority_over_explicit_update():
    prior = source("prior", first_seen_at="2026-01-12T09:00:00Z")
    duplicate = source("copy", text="Synthetic   earnings\nincrease.")
    current = source("current", predecessor_id="prior")
    result = classify_article(current, [prior, duplicate, current, prior], CUTOFF)
    assert result["status"] == "duplicate"
    assert result["related_article_ids"] == ["copy", "prior"]


@pytest.mark.parametrize(
    "changes",
    [
        {"published_at": "2026-01-12T12:01:00Z", "first_seen_at": "2026-01-12T12:02:00Z"},
        {"first_seen_at": "2026-01-12T12:01:00Z"},
    ],
)
def test_future_history_cannot_make_a_duplicate(changes):
    result = classify_article(source("current"), [source("future", **changes)], CUTOFF)
    assert result["status"] == "new"


def test_cutoff_equality_is_eligible():
    result = classify_article(
        source("current", published_at=CUTOFF, first_seen_at=CUTOFF),
        [source("boundary", published_at=CUTOFF, first_seen_at=CUTOFF)],
        CUTOFF,
    )
    assert result["status"] == "duplicate"


def test_current_article_must_itself_be_available():
    article = source("current", first_seen_at="2026-01-12T12:01:00Z")
    result = classify_article(article, [source("prior")], CUTOFF)
    assert result["status"] == "unresolved"
    assert result["related_article_ids"] == []


def test_explicit_predecessor_preserves_update():
    prior = source("prior", first_seen_at="2026-01-12T09:00:00Z")
    current = source(
        "current", text="Corrected earnings decrease.", predecessor_id="prior", source_version="2"
    )
    result = classify_article(current, [prior], CUTOFF)
    assert result["status"] == "update"
    assert result["related_article_ids"] == ["prior"]


@pytest.mark.parametrize("predecessor", ["missing", "current", "future"])
def test_missing_self_or_future_predecessor_is_unresolved(predecessor):
    current = source("current", text="Correction.", predecessor_id=predecessor)
    future = source("future", first_seen_at="2026-01-12T12:01:00Z")
    result = classify_article(current, [current, future], CUTOFF)
    assert result["status"] == "unresolved"


def test_different_text_same_source_without_predecessor_needs_review():
    prior = source("prior", first_seen_at="2026-01-12T09:00:00Z")
    current = source(
        "current", text="Different fact.", source_url=prior.source_url, source_version="2"
    )
    result = classify_article(current, [prior], CUTOFF)
    assert result["status"] == "unresolved"
    assert result["related_article_ids"] == ["prior"]


def test_similar_distinct_articles_are_not_implicitly_merged():
    current = source("current", text="Synthetic earnings decrease.")
    assert classify_article(current, [source("prior")], CUTOFF)["status"] == "new"


def test_naive_cutoff_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        classify_article(source("a"), [], datetime(2026, 1, 12, 12))


@pytest.mark.parametrize("reverse", [False, True])
def test_equal_timestamp_duplicates_are_nonreciprocal(reverse):
    original, copy = source("syn-001"), source("syn-006")
    history = [copy, original] if reverse else [original, copy]
    assert classify_article(original, history, CUTOFF)["status"] == "new"
    duplicate = classify_article(copy, history, CUTOFF)
    assert duplicate["status"] == "duplicate"
    assert duplicate["related_article_ids"] == ["syn-001"]


def test_first_seen_and_publication_precede_id_in_duplicate_order():
    original = source("z-original", first_seen_at="2026-01-12T09:00:00Z")
    earlier_publication = source("z-publication", published_at="2026-01-12T08:59:00Z")
    copy = source("a-copy")
    history = [copy, earlier_publication, original]
    assert classify_article(original, history, CUTOFF)["status"] == "new"
    assert classify_article(copy, history, CUTOFF)["related_article_ids"] == [
        "z-original",
        "z-publication",
    ]


def test_after_article_predecessor_is_ineligible_even_before_cutoff():
    current = source("current", text="Correction", predecessor_id="later")
    later = source("later", first_seen_at="2026-01-12T09:02:00Z")
    assert classify_article(current, [later], CUTOFF)["status"] == "unresolved"


def test_equal_timestamp_explicit_update_precedes_article_id_tie_break():
    prior = source("z-original")
    current = source(
        "a-update", text="Correction", source_version="2", predecessor_id=prior.article_id
    )
    history = [current, prior]
    assert classify_article(current, history, CUTOFF)["status"] == "update"
    assert classify_article(current, history, CUTOFF)["related_article_ids"] == [prior.article_id]


def test_equal_timestamp_unchanged_update_cannot_make_ancestor_its_duplicate():
    original = source("z-original")
    update = source("b-update", source_version="2", predecessor_id=original.article_id)
    latest = source("a-latest", source_version="3", predecessor_id=update.article_id)
    history = [latest, update, original]
    assert classify_article(original, history, CUTOFF)["status"] == "new"
    assert classify_article(update, history, CUTOFF)["related_article_ids"] == [original.article_id]
    assert classify_article(latest, history, CUTOFF)["related_article_ids"] == [
        update.article_id,
        original.article_id,
    ]


def test_cyclic_explicit_history_is_unresolved():
    first = source("a", predecessor_id="b")
    second = source("b", predecessor_id="a", text="Correction")
    for item in (first, second):
        result = classify_article(item, [first, second], CUTOFF)
        assert result["status"] == "unresolved"
        assert "cyclic" in result["reason"]


def test_equal_timestamp_update_and_independent_copy_have_one_original():
    original = source("z-original")
    update = source("a-update", source_version="2", predecessor_id=original.article_id)
    copy = source("m-copy")
    history = [original, update, copy]
    results = {item.article_id: classify_article(item, history, CUTOFF) for item in history}
    assert [identifier for identifier, result in results.items() if result["status"] == "new"] == [
        copy.article_id
    ]
    assert results[update.article_id]["related_article_ids"] == [
        copy.article_id,
        original.article_id,
    ]
    assert results[original.article_id]["related_article_ids"] == [copy.article_id]
