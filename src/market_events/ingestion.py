"""Offline imports: valid rows survive neighbouring malformed or duplicate rows."""

import csv
import io
import json
from pathlib import Path

from pydantic import ValidationError

from market_events.schemas import Article, ImportResult, MarketObservation


def _read(path: Path, result: ImportResult) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        result.errors.append({"line": None, "error": f"Cannot read {path}: {exc}"})
        return None


def _unique_object(pairs: list[tuple]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON field: {key}")
        value[key] = item
    return value


def import_articles(path: Path) -> ImportResult:
    """Read article JSONL, requiring explicit publication and first-seen times.

    Duplicate IDs/source versions are errors; repeated text at distinct sources
    remains available to event memory. A row never gets an invented availability.
    """
    result = ImportResult()
    content = _read(path, result)
    if content is None:
        return result
    identifiers = set()
    versions = set()
    # JSON permits Unicode line separators inside strings. Only physical CR/LF
    # boundaries delimit JSONL records; str.splitlines() also splits valid text.
    for line_number, line in enumerate(io.StringIO(content, newline=None), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line, object_pairs_hook=_unique_object)
            record = Article.model_validate(data)
            version_key = (record.source_url, record.source_version)
            if record.article_id in identifiers:
                raise ValueError(f"Duplicate article_id: {record.article_id}")
            if version_key in versions:
                raise ValueError("Duplicate or contradictory source_url/source_version")
            identifiers.add(record.article_id)
            versions.add(version_key)
            result.records.append(record)
        except (ValueError, ValidationError) as exc:
            result.errors.append({"line": line_number, "error": f"Line {line_number}: {exc}"})
    return result


def import_market_prices(path: Path) -> ImportResult:
    """Read OHLCV CSV; reject duplicate natural keys and invalid rows individually.

    Instrument identifiers are retained verbatim for reviewed universe resolution
    downstream. Empty optional contract IDs become None; required cells do not.
    Error line numbers refer to physical CSV lines, including the header.
    """
    result = ImportResult()
    content = _read(path, result)
    if content is None:
        return result
    reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
    try:
        headers = reader.fieldnames
    except csv.Error as exc:
        result.errors.append({"line": 1, "error": f"Line 1: Invalid CSV header: {exc}"})
        return result
    required = set(MarketObservation.model_fields) - {"observation_id", "contract_id"}
    if not headers or len(headers) != len(set(headers)) or not required.issubset(headers):
        missing = ", ".join(sorted(required - set(headers or [])))
        result.errors.append(
            {"line": 1, "error": f"Line 1: Missing/duplicate CSV headers; missing: {missing}"}
        )
        return result
    identifiers = set()
    while True:
        line_number = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            result.errors.append({"line": line_number, "error": f"Line {line_number}: {exc}"})
            continue
        try:
            if None in row:
                raise ValueError("More cells than CSV headers")
            if row.get("contract_id") == "":
                row["contract_id"] = None
            record = MarketObservation.model_validate(row)
            if record.observation_id in identifiers:
                raise ValueError("Duplicate observation key (instrument, timestamp, contract)")
            identifiers.add(record.observation_id)
            result.records.append(record)
        except (ValueError, ValidationError) as exc:
            result.errors.append({"line": line_number, "error": f"Line {line_number}: {exc}"})
    return result
