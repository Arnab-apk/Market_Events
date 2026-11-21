"""Explicit local settings. Secrets never enter saved configuration snapshots."""

import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["ollama", "openai_compatible"] = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = ""
    api_key: SecretStr = Field(default=SecretStr(""), exclude=True)
    max_output_tokens: int = Field(default=1200, ge=64, le=16000)

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value):
        from urllib.parse import urlparse

        parts = urlparse(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("Model URL requires http(s) and a hostname")
        if parts.username or parts.password or parts.query:
            raise ValueError("Keep credentials out of URLs; use API_KEY environment variables")
        return value.rstrip("/")


class LiveDataSettings(BaseModel):
    """Read-only provider connection. Credentials never enter saved snapshots."""

    model_config = ConfigDict(extra="forbid")
    provider: Literal["upstox"] = "upstox"
    access_token: SecretStr = Field(default=SecretStr(""), exclude=True)
    timeout_seconds: float = Field(default=20, gt=0, le=60)
    min_request_interval_seconds: float = Field(default=0.25, ge=0.1, le=5)
    max_requests: int = Field(default=30, ge=1, le=100)
    news_max_pages: int = Field(default=3, ge=1, le=10)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: Path = Path(".")
    database_path: Path = Path("data/market_events.sqlite")
    mode: Literal["live", "replay"] = "replay"
    universe: Literal["demo", "live"] = "demo"
    live_data: LiveDataSettings = Field(default_factory=LiveDataSettings)
    slm: ModelSettings = Field(default_factory=ModelSettings)
    llm: ModelSettings = Field(default_factory=ModelSettings)
    max_requests: int = Field(default=4, ge=1, le=10)
    max_tokens: int = Field(default=24000, ge=256, le=1000000)
    timeout_seconds: float = Field(default=120, gt=0, le=300)

    def snapshot(self) -> dict:
        return self.model_dump(mode="json")


def load_settings(root: Path = Path(".")) -> Settings:
    root = root.resolve()
    load_dotenv(root / ".env", override=False)
    filename = root / "configs/settings.json"
    raw = json.loads(filename.read_text(encoding="utf-8")) if filename.exists() else {}
    raw["root"] = root
    raw["mode"] = os.getenv("MARKET_EVENTS_MODE", raw.get("mode", "replay"))
    raw["universe"] = os.getenv("MARKET_EVENTS_UNIVERSE", raw.get("universe", "demo"))
    live = raw.get("live_data", {})
    token = os.getenv("UPSTOX_ANALYTICS_TOKEN") or os.getenv("UPSTOX_ACCESS_TOKEN")
    if token:
        live["access_token"] = token
    raw["live_data"] = live
    raw["database_path"] = Path(
        os.getenv("MARKET_EVENTS_DATABASE", raw.get("database_path", "data/market_events.sqlite"))
    )
    if not raw["database_path"].is_absolute():
        raw["database_path"] = root / raw["database_path"]
    for role in ("slm", "llm"):
        model = raw.get(role, {})
        for field in ("provider", "base_url", "model", "api_key"):
            key = f"{role.upper()}_{field.upper()}"
            if key in os.environ:
                model[field] = os.environ[key]
        raw[role] = model
    return Settings.model_validate(raw)


def read_config(root: Path, name: str):
    return json.loads((root / "configs" / name).read_text(encoding="utf-8"))


def read_companies(settings: Settings) -> list[dict]:
    """Select a namespace explicitly; synthetic mappings never identify live bars."""
    if settings.universe == "demo":
        return read_config(settings.root, "companies.json")
    from .live_data import get_live_universe

    return [
        {**record, "aliases": record.get("aliases", []), "sector": record.get("sector", "")}
        for record in get_live_universe(settings)
        if record.get("market_family", "equity") == "equity"
    ]


def read_exposure_rules(settings: Settings) -> list[dict]:
    if settings.universe == "demo":
        return read_config(settings.root, "exposure_rules.json")
    filename = settings.root / "configs" / "live_exposure_rules.json"
    return json.loads(filename.read_text(encoding="utf-8")) if filename.exists() else []
