"""Sizing: water-fill with cap, min-order drops, whole shares, leftover use (offline)."""

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from market_events.schemas import MarketObservation
from market_events.sizing import (
    latest_quotes,
    load_portfolio_rules,
    price_table,
    size,
    validate_portfolio_rules,
)

AS_OF = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
AAA, BBB, CCC, DDD, EEE = (f"SYNTHETIC:NSE:{x}" for x in ("AAA", "BBB", "CCC", "DDD", "EEE"))


def portfolio_rules(**overrides):
    base = {
        "version": "portfolio-test",
        "currency": "INR",
        "budget_inr": 100000,
        "cash_buffer_pct": 0.10,
        "max_position_pct": 0.25,
        "min_order_inr": 5000,
        "max_order_inr": 50000,
        "weighting": "score",
        "rebalance_band_pp": 5,
        "min_trade_inr": 1000,
        "max_price_age_days": 5,
        "allowed_market_families": ["equity"],
        "blocked_instruments": [],
        "max_proposals_per_plan": 20,
    }
    return {**base, **overrides}


def bar(instrument, close, when, available=None, family="equity"):
    return MarketObservation(
        instrument_id=instrument,
        market_family=family,
        timestamp=when,
        available_at=available or when,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        currency="INR",
        unit="share",
        contract_id="SYNTHETIC:contract" if family == "commodity" else None,
    )


SCORES = {AAA: 0.60, BBB: 0.40, CCC: 0.30, DDD: 0.20, EEE: 0.05}
PRICES = {AAA: 1450, BBB: 820, CCC: 2310, DDD: 415, EEE: 990}


def test_default_config_file_is_valid():
    rules = load_portfolio_rules(ROOT)
    assert rules["version"] == "portfolio-v1" and rules["max_position_pct"] == 0.25


def test_brief_worked_example_exactly():
    plan = size(SCORES, PRICES, portfolio_rules(), AS_OF)
    quantities = {p.instrument_id: p.quantity for p in plan.proposals}
    amounts = {p.instrument_id: p.amount_inr for p in plan.proposals}
    assert quantities == {AAA: 17, BBB: 30, CCC: 10, DDD: 42}
    assert amounts == {AAA: 24650, BBB: 24600, CCC: 23100, DDD: 17430}
    assert sum(amounts.values()) == 89780
    assert plan.cash_inr == 10220
    assert plan.budget_inr == 100000
    assert all(
        p.side == "buy" and p.label.endswith("research only, not advice") for p in plan.proposals
    )
    # EEE's slice (2,903.23 before capping or 3,636.36 after) is under the 5,000 minimum.
    assert EEE not in quantities
    assert any(EEE in warning and "minimum" in warning for warning in plan.warnings)
    weights = {p.instrument_id: p.weight for p in plan.positions}
    assert weights[AAA] == pytest.approx(0.2465)
    assert plan.verdicts == []


def test_leftover_shares_never_exceed_cap_or_touch_buffer():
    plan = size(SCORES, PRICES, portfolio_rules(), AS_OF)
    cap = 100000 * 0.25
    assert all(p.amount_inr <= cap for p in plan.proposals)
    assert plan.cash_inr >= 100000 * 0.10


def test_equal_weighting():
    prices = {AAA: 100, BBB: 100, CCC: 100, DDD: 100}
    plan = size(
        {k: 0.9 for k in prices} | {AAA: 0.1}, prices, portfolio_rules(weighting="equal"), AS_OF
    )
    assert {p.instrument_id: p.quantity for p in plan.proposals} == {
        AAA: 225,
        BBB: 225,
        CCC: 225,
        DDD: 225,
    }
    assert plan.cash_inr == 10000


def test_all_capped_leaves_rest_in_cash_with_warning():
    plan = size({AAA: 0.5, BBB: 0.5}, {AAA: 100, BBB: 100}, portfolio_rules(), AS_OF)
    assert {p.instrument_id: p.quantity for p in plan.proposals} == {AAA: 250, BBB: 250}
    assert plan.cash_inr == 50000
    assert any("cap" in warning for warning in plan.warnings)


def test_every_name_under_min_order_gives_empty_plan_and_warning():
    plan = size({AAA: 0.5, BBB: 0.5}, {AAA: 10, BBB: 10}, portfolio_rules(budget_inr=6000), AS_OF)
    assert plan.proposals == [] and plan.positions == []
    assert plan.cash_inr == 6000
    assert any("minimum" in warning for warning in plan.warnings)
    assert any("no paper buys" in warning.lower() for warning in plan.warnings)


def test_empty_shortlist_gives_empty_plan():
    plan = size({}, {}, portfolio_rules(), AS_OF)
    assert plan.proposals == [] and plan.cash_inr == 100000 and plan.warnings


def test_missing_price_drops_name_with_warning():
    plan = size({AAA: 0.5, BBB: 0.5}, {AAA: 100}, portfolio_rules(), AS_OF)
    assert [p.instrument_id for p in plan.proposals] == [AAA]
    assert any(BBB in warning and "price" in warning for warning in plan.warnings)


@pytest.mark.parametrize("bad", [0, -5, float("nan"), float("inf"), "12"])
def test_bad_price_rejected(bad):
    with pytest.raises(ValueError):
        size({AAA: 0.5}, {AAA: bad}, portfolio_rules(), AS_OF)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None])
def test_bad_score_rejected(bad):
    with pytest.raises(ValueError):
        size({AAA: bad}, {AAA: 100}, portfolio_rules(), AS_OF)


def test_spent_plus_cash_equals_budget_to_the_paisa():
    prices = {AAA: 1234.57, BBB: 98.13, CCC: 3321.09, DDD: 47.77}
    scores = {AAA: 0.33, BBB: 0.29, CCC: 0.21, DDD: 0.17}
    plan = size(scores, prices, portfolio_rules(budget_inr=87654.32), AS_OF)
    spent = sum(p.amount_inr for p in plan.proposals)
    assert round(spent + plan.cash_inr, 2) == 87654.32
    for proposal in plan.proposals:
        assert proposal.amount_inr == round(proposal.quantity * proposal.price, 2)


def test_deterministic_proposal_ids():
    first = size(SCORES, PRICES, portfolio_rules(), AS_OF)
    second = size(dict(reversed(SCORES.items())), PRICES, portfolio_rules(), AS_OF)
    assert [p.proposal_id for p in first.proposals] == [p.proposal_id for p in second.proposals]


def test_observation_prices_use_latest_cutoff_safe_bar():
    observations = [
        bar(AAA, 1400, AS_OF - timedelta(days=2)),
        bar(AAA, 1450, AS_OF - timedelta(days=1)),
        # Session before the cutoff but only available after it: must be ignored.
        bar(AAA, 9999, AS_OF - timedelta(hours=1), available=AS_OF + timedelta(hours=1)),
        bar(AAA, 5000, AS_OF + timedelta(days=1)),
    ]
    assert price_table(observations, AS_OF) == {AAA: 1450}
    assert latest_quotes(observations, AS_OF)[AAA].close == 1450
    plan = size({AAA: 1.0}, observations, portfolio_rules(), AS_OF)
    assert plan.proposals[0].price == 1450 and plan.proposals[0].quantity == 17


def test_naive_as_of_rejected():
    with pytest.raises(ValueError):
        size(SCORES, PRICES, portfolio_rules(), datetime(2026, 3, 2))


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": ""},
        {"currency": "USD"},
        {"budget_inr": 0},
        {"budget_inr": float("nan")},
        {"budget_inr": True},
        {"cash_buffer_pct": 0},
        {"cash_buffer_pct": 1},
        {"max_position_pct": 1.5},
        {"min_order_inr": -1},
        {"max_order_inr": float("inf")},
        {"min_order_inr": 60000},
        {"weighting": "volatility"},
        {"rebalance_band_pp": 0},
        {"min_trade_inr": 0},
        {"max_price_age_days": 0},
        {"allowed_market_families": ["crypto"]},
        {"blocked_instruments": "AAA"},
        {"max_proposals_per_plan": 0},
        {"surprise": 1},
    ],
)
def test_invalid_portfolio_rules_raise(overrides):
    with pytest.raises(ValueError):
        validate_portfolio_rules(portfolio_rules(**overrides))


def test_missing_portfolio_key_raises():
    rules = portfolio_rules()
    del rules["max_order_inr"]
    with pytest.raises(ValueError):
        validate_portfolio_rules(rules)


def test_validation_does_not_mutate_input():
    rules = portfolio_rules()
    validate_portfolio_rules(rules)["blocked_instruments"].append("X")
    assert rules["blocked_instruments"] == [] and not math.isnan(rules["budget_inr"])
