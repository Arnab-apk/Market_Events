"""Bounded web requests; domain records and numerical validation remain shared."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import AwareTime, ExecutionPolicy


class WebRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AnalysisRequest(WebRequest):
    article_id: str = Field(min_length=1, max_length=300)
    decision_time: AwareTime
    policy: ExecutionPolicy = ExecutionPolicy.slm_delegate
    mode: Literal["replay", "live"] = "replay"
    repeat_run: bool = False


class ImportRequest(WebRequest):
    kind: Literal["articles", "prices"]
    content: str = Field(min_length=1, max_length=8_000_000)


class TechnicalRequest(WebRequest):
    company_id: str = Field(min_length=1, max_length=300)
    decision_time: AwareTime


class HistoryRequest(WebRequest):
    company_id: str = Field(min_length=1, max_length=300)
    start_date: date = date(2015, 1, 1)
    end_date: date = date(2020, 12, 31)
    as_of: AwareTime | None = None

    @model_validator(mode="after")
    def date_window(self):
        if not date(2000, 1, 1) <= self.start_date <= self.end_date <= date(2020, 12, 31):
            raise ValueError("Research dates must satisfy 2000-01-01 <= start <= end <= 2020-12-31")
        return self


class BacktestRequest(HistoryRequest):
    strategy: Literal[
        "buy_hold", "sma_cross", "ema_cross", "rsi_reversion", "macd_cross", "bollinger_reversion"
    ] = "sma_cross"
    initial_capital: float = Field(default=100000, gt=0, le=1e12)
    cost_bps: float = Field(default=10, ge=0, lt=10000)
    slippage_bps: float = Field(default=5, ge=0, lt=10000)
    fast_period: int = Field(default=20, ge=1, le=10000)
    slow_period: int = Field(default=50, ge=2, le=10000)
    rsi_buy: float = Field(default=30, ge=0, le=100)
    rsi_sell: float = Field(default=70, ge=0, le=100)


class MonteCarloRequest(WebRequest):
    daily_returns: list[float] = Field(min_length=5, max_length=10000)
    initial_capital: float = Field(default=100000, gt=0, le=1e12)
    simulations: int = Field(default=300, ge=10, le=1000)
    horizon: int = Field(default=252, ge=1, le=1000)
    seed: int = 42
    block_size: int = Field(default=5, ge=1, le=252)


class SyncRequest(WebRequest):
    company_ids: list[str] = Field(min_length=1, max_length=20)
    start_date: date = date(2015, 1, 1)
    end_date: date = date(2020, 12, 31)
    lookback_days: int = Field(default=550, ge=1, le=3650)
    include_news: bool = False


class BatchRequest(WebRequest):
    article_ids: list[str] = Field(min_length=1, max_length=100)
    decision_time: AwareTime
    policy: ExecutionPolicy = ExecutionPolicy.slm_delegate
    limit: int = Field(default=10, ge=1, le=100)
