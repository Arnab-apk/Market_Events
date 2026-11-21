"""Shared data records (Pydantic models) passed between every module and stored in the ledger:
articles, observations, events, exposure rules, features, assessments, model calls, runs and
outcomes. Unknown fields are rejected and every timestamp must be timezone-aware; it is
normalised to UTC.
"""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def utc(value: datetime) -> datetime:
    """Normalise an aware datetime to UTC; naive datetimes are rejected."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(timezone.utc)


AwareTime = Annotated[datetime, AfterValidator(utc)]
EventType = Literal[
    "earnings", "order_announcement", "commodity_supply_disruption", "other", "uncertain"
]


# Base for all records: unknown fields rejected, assignments re-validated.
# Prompt-bound subclasses (FilterDecision, ExtractedAmount, EventExtraction)
# deliberately have no class docstrings: their JSON schema is sent in the live
# prompt and hashed into request_hash, so a docstring would change requests.
class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Article(Record):
    """A source article version; its content hash is computed from the text."""

    article_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    text: str = Field(min_length=1)
    published_at: AwareTime
    first_seen_at: AwareTime
    source_version: str = "1"
    content_hash: str = ""
    predecessor_id: str | None = None

    @model_validator(mode="after")
    def fingerprint(self):
        """Compute the content hash and check publication ordering."""
        if not self.text.strip():
            raise ValueError("Article text cannot be blank")
        calculated = hashlib.sha256(" ".join(self.text.split()).encode()).hexdigest()
        if self.content_hash and self.content_hash != calculated:
            raise ValueError("content_hash does not match text")
        object.__setattr__(self, "content_hash", calculated)
        if self.first_seen_at < self.published_at:
            raise ValueError("first_seen_at cannot precede published_at")
        return self


class MarketObservation(Record):
    """One daily OHLCV bar with the time it became available."""

    observation_id: str = ""
    instrument_id: str = Field(min_length=1)
    market_family: Literal["equity", "commodity", "benchmark"]
    timestamp: AwareTime
    available_at: AwareTime
    open: float = Field(gt=0, allow_inf_nan=False)
    high: float = Field(gt=0, allow_inf_nan=False)
    low: float = Field(gt=0, allow_inf_nan=False)
    close: float = Field(gt=0, allow_inf_nan=False)
    volume: float = Field(ge=0, allow_inf_nan=False)
    currency: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    contract_id: str | None = None

    @model_validator(mode="after")
    def validate_bar(self):
        """Check OHLC consistency and availability, and derive the observation ID."""
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC relationship is impossible")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.available_at < self.timestamp:
            raise ValueError("available_at must be at or after session timestamp")
        if self.market_family == "commodity" and not self.contract_id:
            raise ValueError("Commodity observations require an explicit contract_id")
        key = f"{self.instrument_id}|{self.timestamp.isoformat()}|{self.contract_id or ''}"
        identifier = hashlib.sha256(key.encode()).hexdigest()[:24]
        if self.observation_id and self.observation_id != identifier:
            raise ValueError("observation_id does not match natural key")
        object.__setattr__(self, "observation_id", identifier)
        return self


class ImportResult(Record):
    """Parsed records plus per-row errors and warnings from an import."""

    records: list[Any] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExecutionPolicy(str, Enum):
    """Which model handles filtering and how much the SLM is trusted."""

    llm_only = "llm_only"
    slm_filter = "slm_filter"
    slm_delegate = "slm_delegate"


# Filter task answer (prompt-bound schema; see Record).
class FilterDecision(Record):
    relevance: Literal["relevant", "irrelevant", "uncertain"]
    event_type: EventType = "uncertain"
    candidate_entities: list[str] = Field(default_factory=list)
    source_spans: list[str] = Field(default_factory=list)
    reason: str
    trace_id: str | None = None


# One amount quoted in an extraction (prompt-bound schema).
class ExtractedAmount(Record):
    value: str | float
    unit: str = Field(min_length=1)
    scale: str | None = None
    source_span: str = Field(min_length=1)


# Extraction task answer (prompt-bound schema; see Record).
class EventExtraction(Record):
    event_id: str
    source_version: str = "1"
    event_type: EventType
    company_id: str | None = None
    candidate_entities: list[str] = Field(default_factory=list)
    commodity_id: str | None = None
    direction: Literal["positive", "negative", "neutral", "uncertain"] = "uncertain"
    amounts: list[ExtractedAmount] = Field(default_factory=list)
    source_spans: list[str] = Field(default_factory=list)
    validation_status: Literal["validated", "unresolved", "unsupported"] = "unresolved"
    reason: str = ""
    trace_id: str | None = None


class ExposureRule(Record):
    """A reviewed company-commodity sensitivity with its validity times."""

    company_id: str
    commodity_id: str
    relationship: str
    source: str
    direction: Literal[-1, 1]
    effective_at: AwareTime
    known_at: AwareTime
    version: str
    rule_id: str


class ExposureMatch(Record):
    """Result of looking up an exposure rule for an event."""

    status: Literal["matched", "missing", "ambiguous", "not_required"]
    rule: ExposureRule | None = None
    reason: str = ""


class TechnicalSnapshot(Record):
    """Cutoff-safe technical context, independent of models and event scoring."""

    decision_time: AwareTime
    company_id: str | None = None
    values: dict[str, float | None] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    history_bars: int = Field(default=0, ge=0)
    required_history: dict[str, int] = Field(default_factory=dict)
    interpretation: dict[str, str] = Field(default_factory=dict)
    definition_version: str = "technicals-v1"


class MarketFeatures(Record):
    """Market evidence values computed at a cutoff, with gaps listed."""

    decision_time: AwareTime
    company_id: str | None = None
    values: dict[str, float | None] = Field(default_factory=dict)
    observation_ids: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    definition_version: str = "features-v1"


class Assessment(Record):
    """Deterministic evidence result: direction, score, coverage, reasons."""

    direction: Literal["positive", "negative", "neutral", "abstain"]
    evidence_score: float | None = None
    coverage: float = Field(ge=0, le=1)
    conflicts: list[str] = Field(default_factory=list)
    abstention_reasons: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    rules_version: str
    explanation: str
    evidence_label: Literal[
        "positive_evidence", "negative_evidence", "mixed_evidence", "insufficient_evidence"
    ] = "insufficient_evidence"

    @model_validator(mode="after")
    def display_label(self):
        """Derive the guide-compatible evidence label."""
        label = "insufficient_evidence"
        if self.direction != "abstain":
            if self.conflicts or self.direction == "neutral":
                label = "mixed_evidence"
            else:
                label = f"{self.direction}_evidence"
        object.__setattr__(self, "evidence_label", label)
        return self


class ModelCall(Record):
    """Audit record of one model (or replay) call."""

    trace_id: str
    run_id: str
    task: str
    provider: str
    model: str
    prompt_version: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float = Field(ge=0)
    retries: int = 0
    status: str
    error: str | None = None
    mode: Literal["live", "replay"]
    request_hash: str | None = None
    requested_model: str | None = None
    compatibility_warning: str | None = None


class AnalysisRun(Record):
    """Everything saved for one analysis, from snapshot to assessment."""

    run_id: str
    article_id: str
    event_id: str | None = None
    policy: ExecutionPolicy
    decision_time: AwareTime
    status: str
    created_at: AwareTime
    config_snapshot: dict
    memory: dict = Field(default_factory=dict)
    filter_decision: FilterDecision | None = None
    extraction: EventExtraction | None = None
    exposure: ExposureMatch | None = None
    features: MarketFeatures | None = None
    technicals: TechnicalSnapshot | None = None
    assessment: Assessment | None = None
    calls: list[ModelCall] = Field(default_factory=list)
    error: str | None = None
    latency_ms: float = 0
    mode: Literal["live", "replay"]
    request_key: str | None = None
    parent_run_id: str | None = None
    stage_durations_ms: dict[str, float] = Field(default_factory=dict)


class EventOutcome(Record):
    """Later hypothetical return for a run, kept apart from the decision."""

    run_id: str
    status: Literal["pending", "completed", "invalid"]
    entry_time: AwareTime | None = None
    exit_time: AwareTime | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    gross_return: float | None = None
    net_return: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    label: str | None = None
    reason: str = ""
    definition_version: str = "outcome-v1"
