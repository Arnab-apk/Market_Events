import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from market_events.market_features import compute_market_features
from market_events.schemas import MarketObservation

CUTOFF = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


def bars():
    with (Path(__file__).parent / "fixtures/market_prices.csv").open() as stream:
        return [
            MarketObservation.model_validate({**r, "contract_id": r["contract_id"] or None})
            for r in csv.DictReader(stream)
        ]


def features(rows, cutoff=CUTOFF):
    return compute_market_features(
        rows, cutoff, "NSE:ASIANPAINT", "MCX:CRUDEOIL", "NSE:NIFTY_MATERIALS"
    )


def test_known_returns_volume_and_future_exclusion():
    rows = bars()
    result = features(rows)
    assert result.values["equity_return"] == pytest.approx(0.01)
    assert result.values["benchmark_return"] == pytest.approx(0.002)
    assert result.values["excess_return"] == pytest.approx(0.008)
    assert result.values["commodity_return"] == pytest.approx(0.015)
    assert result.values["relative_volume"] == pytest.approx(1600 / 1300)
    allowed = {o.observation_id for o in rows if o.timestamp <= CUTOFF and o.available_at <= CUTOFF}
    assert set(result.observation_ids) <= allowed
    assert features(list(reversed(rows))) == result
    dates = {o.timestamp.date() for o in rows}
    assert len(dates) >= 12
    assert len([d for d in dates if d > CUTOFF.date()]) >= 5


def test_availability_alignment_and_contract_isolation():
    rows = bars()
    delayed = [
        o.model_copy(update={"available_at": CUTOFF + timedelta(days=1)})
        if o.instrument_id == "NSE:NIFTY_MATERIALS" and o.timestamp.date() == CUTOFF.date()
        else o
        for o in rows
    ]
    assert features(delayed).values["excess_return"] is None
    mixed = [
        o.model_copy(update={"contract_id": "OTHER"})
        if o.market_family == "commodity" and o.timestamp.date() == CUTOFF.date()
        else o
        for o in rows
    ]
    assert features(mixed).values["commodity_return"] is None
    # A not-yet-known foreign contract must not contaminate eligible history.
    assert features(rows + [rows[-1].model_copy(update={"contract_id": "FUTURE"})]) == features(
        rows
    )


def test_stale_zero_volume_and_short_history():
    rows = [o for o in bars() if o.timestamp <= CUTOFF]
    assert "excess_return" in features(rows, CUTOFF + timedelta(days=5)).stale
    zero = [o.model_copy(update={"volume": 0}) for o in rows]
    assert features(zero).values["relative_volume"] is None
    assert all(v is None for v in features([]).values.values())


def test_exact_availability_boundary_and_four_day_staleness():
    rows = [o for o in bars() if o.timestamp <= CUTOFF]
    rows = [
        o.model_copy(update={"available_at": CUTOFF}) if o.timestamp.date() == CUTOFF.date() else o
        for o in rows
    ]
    result = features(rows)
    assert result.values["excess_return"] is not None
    assert (
        "excess_return" not in features(rows, datetime(2026, 1, 16, 10, tzinfo=timezone.utc)).stale
    )
    assert (
        "excess_return"
        in features(rows, datetime(2026, 1, 16, 10, 0, 1, tzinfo=timezone.utc)).stale
    )


def test_duplicate_rows_units_and_misaligned_commodity_windows():
    rows = bars()
    equity = next(
        o
        for o in rows
        if o.instrument_id == "NSE:ASIANPAINT" and o.timestamp.date() == CUTOFF.date()
    )
    assert features(rows + [equity]) == features(rows)
    conflict = equity.model_copy(update={"volume": equity.volume + 1})
    conflicted = features(rows + [conflict])
    assert conflicted.values["excess_return"] is None
    assert conflicted.values["relative_volume"] is None
    changed_unit = [
        o.model_copy(update={"unit": "different unit"}) if o == equity else o for o in rows
    ]
    assert features(changed_unit).values["equity_return"] is None
    without_latest_commodity = [
        o
        for o in rows
        if not (o.market_family == "commodity" and o.timestamp.date() == CUTOFF.date())
    ]
    assert features(without_latest_commodity).values["commodity_return"] is None


def test_naive_cutoff_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        features(bars(), CUTOFF.replace(tzinfo=None))
