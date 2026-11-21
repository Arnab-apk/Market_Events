"""Named records crossing application boundaries; all timestamps are UTC-aware."""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(timezone.utc)


AwareTime = Annotated[datetime, AfterValidator(utc)]
EventType = Literal[
    "earnings", "order_announcement", "commodity_supply_disruption", "other", "uncertain"
]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Article(Record):
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
    records: list[Any] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExecutionPolicy(str, Enum):
    llm_only = "llm_only"
    slm_filter = "slm_filter"
    slm_delegate = "slm_delegate"


class FilterDecision(Record):
    relevance: Literal["relevant", "irrelevant", "uncertain"]
    event_type: EventType = "uncertain"
    candidate_entities: list[str] = Field(default_factory=list)
    source_spans: list[str] = Field(default_factory=list)
    reason: str
    trace_id: str | None = None


class ExtractedAmount(Record):
    value: str | float
    unit: str = Field(min_length=1)
    scale: str | None = None
    source_span: str = Field(min_length=1)


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
    decision_time: AwareTime
    company_id: str | None = None
    values: dict[str, float | None] = Field(default_factory=dict)
    observation_ids: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    definition_version: str = "features-v1"


class Assessment(Record):
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
        label = "insufficient_evidence"
        if self.direction != "abstain":
            if self.conflicts or self.direction == "neutral":
                label = "mixed_evidence"
            else:
                label = f"{self.direction}_evidence"
        object.__setattr__(self, "evidence_label", label)
        return self


class ModelCall(Record):
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
