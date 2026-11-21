"""Synthetic imports test validation, row isolation and source availability."""

import csv
import io
import json

import pytest

from market_events.ingestion import import_articles, import_market_prices


def article(**overrides):
    return {
        "article_id": "a1",
        "source_url": "https://example.invalid/a1",
        "text": "Synthetic earnings announcement.",
        "published_at": "2026-01-12T14:00:00+05:30",
        "first_seen_at": "2026-01-12T14:01:00+05:30",
        "source_version": "1",
        **overrides,
    }


def bar(**overrides):
    return {
        "instrument_id": "NSE:ASIANPAINT",
        "market_family": "equity",
        "timestamp": "2026-01-12T10:00:00Z",
        "available_at": "2026-01-12T10:01:00Z",
        "open": 100,
        "high": 110,
        "low": 90,
        "close": 105,
        "volume": 1000,
        "currency": "INR",
        "unit": "share",
        "contract_id": "",
        **overrides,
    }


def write_csv(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(bar()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8")


def test_jsonl_keeps_good_rows_and_reports_physical_lines(tmp_path):
    path = tmp_path / "articles.jsonl"
    path.write_text(
        "\ufeff"
        + json.dumps(article())
        + "\n\n{bad json}\n"
        + json.dumps(article(article_id="bad", first_seen_at=None))
        + "\n"
        + json.dumps(article(article_id="a2", source_url="https://example.invalid/a2")),
        encoding="utf-8",
    )
    result = import_articles(path)
    assert [item.article_id for item in result.records] == ["a1", "a2"]
    assert [error["line"] for error in result.errors] == [3, 4]
    assert all("Line" in error["error"] for error in result.errors)
    assert result.records[0].published_at.isoformat() == "2026-01-12T08:30:00+00:00"
    assert len(result.records[0].content_hash) == 64


@pytest.mark.parametrize(
    "changes",
    [
        {"published_at": "2026-01-12T10:00:00"},
        {"first_seen_at": "2026-01-12T08:00:00Z"},
        {"content_hash": "invented"},
        {"text": "   "},
        {"unexpected": "field"},
    ],
)
def test_article_constraints_produce_row_errors(tmp_path, changes):
    path = tmp_path / "articles.jsonl"
    path.write_text(json.dumps(article(**changes)), encoding="utf-8")
    result = import_articles(path)
    assert not result.records
    assert result.errors[0]["line"] == 1


def test_article_identity_and_source_version_collisions(tmp_path):
    path = tmp_path / "articles.jsonl"
    rows = [
        article(),
        article(),
        article(article_id="different"),
        article(article_id="v2", source_version="2", predecessor_id="a1", text="Correction"),
        article(article_id="copy", source_url="https://example.invalid/copy"),
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    result = import_articles(path)
    assert [item.article_id for item in result.records] == ["a1", "v2", "copy"]
    assert [error["line"] for error in result.errors] == [2, 3]
    assert result.records[0].content_hash == result.records[-1].content_hash


def test_duplicate_json_keys_are_not_silently_overwritten(tmp_path):
    path = tmp_path / "articles.jsonl"
    path.write_text('{"article_id":"one","article_id":"two"}', encoding="utf-8")
    result = import_articles(path)
    assert "Duplicate JSON field" in result.errors[0]["error"]


def test_market_import_continues_past_invalid_and_duplicate_rows(tmp_path):
    path = tmp_path / "market.csv"
    write_csv(path, [bar(), bar(low=106), bar(), bar(instrument_id="NSE:BERGEPAINT")])
    result = import_market_prices(path)
    assert len(result.records) == 2
    assert [error["line"] for error in result.errors] == [3, 4]
    assert result.records[0].contract_id is None


@pytest.mark.parametrize(
    "changes",
    [
        {"available_at": ""},
        {"available_at": "2026-01-12T09:59:00Z"},
        {"timestamp": "2026-01-12T10:00:00"},
        {"open": ""},
        {"high": 99},
        {"volume": -1},
        {"close": "nan"},
        {"market_family": "commodity"},
    ],
)
def test_invalid_market_cells_are_explicit_errors(tmp_path, changes):
    path = tmp_path / "market.csv"
    write_csv(path, [bar(**changes), bar()])
    result = import_market_prices(path)
    assert len(result.records) == 1
    assert result.errors[0]["line"] == 2


def test_different_commodity_contracts_are_distinct_keys(tmp_path):
    path = tmp_path / "market.csv"
    write_csv(
        path,
        [
            bar(market_family="commodity", contract_id="JAN"),
            bar(market_family="commodity", contract_id="FEB"),
        ],
    )
    result = import_market_prices(path)
    assert len(result.records) == 2
    assert not result.errors
    assert result.records[0].observation_id != result.records[1].observation_id


def test_market_duplicate_offsets_normalize_to_same_key(tmp_path):
    path = tmp_path / "market.csv"
    write_csv(path, [bar(), bar(timestamp="2026-01-12T15:30:00+05:30")])
    result = import_market_prices(path)
    assert len(result.records) == 1
    assert "Duplicate observation" in result.errors[0]["error"]


@pytest.mark.parametrize("content", ["", "timestamp,timestamp\n", "timestamp,open\n"])
def test_bad_csv_headers_are_reported(tmp_path, content):
    path = tmp_path / "market.csv"
    path.write_text(content, encoding="utf-8")
    result = import_market_prices(path)
    assert result.errors[0]["line"] == 1


def test_csv_extra_cells_and_short_rows_do_not_abort_import(tmp_path):
    path = tmp_path / "market.csv"
    write_csv(path, [bar()])
    text = path.read_text(encoding="utf-8")
    header, row = text.splitlines()
    path.write_text(header + "\n" + row + ",extra\nshort\n" + row, encoding="utf-8")
    result = import_market_prices(path)
    assert len(result.records) == 1
    assert [error["line"] for error in result.errors] == [2, 3]


def test_file_read_errors_are_returned(tmp_path):
    for importer in (import_articles, import_market_prices):
        result = importer(tmp_path / "missing")
        assert not result.records
        assert "Cannot read" in result.errors[0]["error"]


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_unicode_text_separators_do_not_split_jsonl_records(tmp_path, separator, newline):
    path = tmp_path / "articles.jsonl"
    text = f"Synthetic{separator}earnings announcement."
    rows = [json.dumps(article(text=text), ensure_ascii=False), "{bad json}"]
    path.write_bytes(newline.join(rows).encode("utf-8"))
    result = import_articles(path)
    assert [item.text for item in result.records] == [text]
    assert [error["line"] for error in result.errors] == [2]
