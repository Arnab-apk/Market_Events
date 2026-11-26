"""Request bodies accepted by api.py. They bound sizes, dates and numbers before any work starts, so
malformed requests fail with a 422 and no side effects. Domain records themselves are validated
by schemas.py.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import AwareTime, ExecutionPolicy


class WebRequest(BaseModel):
    """Base for API bodies: unknown fields and NaN/infinity are rejected."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PortfolioHolding(WebRequest):
    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9&._-]{0,29}$")
    exchange: Literal["NSE", "BSE"]
    quantity: float = Field(gt=0, le=100_000_000)
    averageCost: float = Field(ge=0, le=10_000_000)


class PaperAccount(WebRequest):
    startingCash: float = Field(gt=0, le=1_000_000_000_000)
    cash: float = Field(ge=0, le=1_000_000_000_000)


class PortfolioSnapshot(WebRequest):
    source: str = Field(min_length=1, max_length=300)
    importedAt: AwareTime
    holdings: list[PortfolioHolding] = Field(min_length=1, max_length=250)
    paper: PaperAccount | None = None

    @model_validator(mode="after")
    def valid_account(self):
        keys = {(row.exchange, row.symbol) for row in self.holdings}
        if len(keys) != len(self.holdings):
            raise ValueError("Duplicate portfolio holdings")
        invested = sum(row.quantity * row.averageCost for row in self.holdings)
        if self.paper and abs(self.paper.startingCash - self.paper.cash - invested) > 0.01:
            raise ValueError("Paper cash and invested cost must equal starting balance")
        return self


class PortfolioSaveRequest(WebRequest):
    revision: int = Field(ge=0, le=2_000_000_000)
    snapshot: PortfolioSnapshot | None


class AnalysisRequest(WebRequest):
    """Body for POST /api/analyse: one article, cutoff, policy and mode."""

    article_id: str = Field(min_length=1, max_length=300)
    decision_time: AwareTime
    policy: ExecutionPolicy = ExecutionPolicy.slm_delegate
    mode: Literal["replay", "live"] = "replay"
    repeat_run: bool = False


class PortfolioReviewRequest(WebRequest):
    """Bounded selection of saved cases for a single portfolio research question."""

    topic: Literal["recent", "conflicts", "gaps"]
    run_ids: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        min_length=1, max_length=12
    )


class ImportRequest(WebRequest):
    """Body for POST /api/import: raw JSONL articles or CSV prices."""

    kind: Literal["articles", "prices"]
    content: str = Field(min_length=1, max_length=8_000_000)


class TechnicalRequest(WebRequest):
    """Body for POST /api/technicals: company and decision cutoff."""

    company_id: str = Field(min_length=1, max_length=300)
    decision_time: AwareTime


class HistoryRequest(WebRequest):
    """Study window for the strategy lab, capped at 2020-12-31."""

    company_id: str = Field(min_length=1, max_length=300)
    start_date: date = date(2015, 1, 1)
    end_date: date = date(2020, 12, 31)
    as_of: AwareTime | None = None

    @model_validator(mode="after")
    def date_window(self):
        """Reject windows outside 2000-01-01 to 2020-12-31."""
        if not date(2000, 1, 1) <= self.start_date <= self.end_date <= date(2020, 12, 31):
            raise ValueError("Research dates must satisfy 2000-01-01 <= start <= end <= 2020-12-31")
        return self


class BacktestRequest(HistoryRequest):
    """Study window plus strategy, costs and indicator parameters."""

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
    # Optional: also run the same configuration in-sample/out-of-sample around this
    # out-of-sample start date. Omitted, the response is exactly the plain backtest.
    walk_forward_split: date | None = None

    @model_validator(mode="after")
    def split_inside_window(self):
        """A walk-forward split must leave bars on both sides of the study window."""
        split = self.walk_forward_split
        if split is not None and not self.start_date < split <= self.end_date:
            raise ValueError("walk_forward_split must satisfy start_date < split <= end_date")
        return self


class MonteCarloRequest(WebRequest):
    """Returns to resample and the bootstrap settings."""

    daily_returns: list[float] = Field(min_length=5, max_length=10000)
    initial_capital: float = Field(default=100000, gt=0, le=1e12)
    simulations: int = Field(default=300, ge=10, le=1000)
    horizon: int = Field(default=252, ge=1, le=1000)
    seed: int = 42
    block_size: int = Field(default=5, ge=1, le=252)


class SyncRequest(WebRequest):
    """Body for explicit provider downloads (historical or live)."""

    company_ids: list[str] = Field(min_length=1, max_length=20)
    start_date: date = date(2015, 1, 1)
    end_date: date = date(2020, 12, 31)
    lookback_days: int = Field(default=550, ge=1, le=3650)
    include_news: bool = False
    # Live sync also fetches commodities linked by reviewed exposure rules (near-month MCX).
    include_commodities: bool = True


class BatchRequest(WebRequest):
    """Body for an explicit live-model batch over synced news."""

    article_ids: list[str] = Field(min_length=1, max_length=100)
    decision_time: AwareTime
    policy: ExecutionPolicy = ExecutionPolicy.slm_delegate
    limit: int = Field(default=10, ge=1, le=100)
