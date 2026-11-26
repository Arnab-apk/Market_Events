"""Rebalance: drift band, sells before buys, buffer-limited buys, cap and cutoff (offline)."""

from datetime import datetime, timedelta, timezone

import pytest

from market_events.rebalance import rebalance
from market_events.risk_limits import check
from market_events.schemas import MarketObservation, PaperPosition

AS_OF = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)
AAA, BBB, CCC = "SYNTHETIC:NSE:AAA", "SYNTHETIC:NSE:BBB", "SYNTHETIC:NSE:CCC"


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


# The worked example targets 45 % per name, so it needs a 50 % cap (default is 25 %).
EXAMPLE_RULES = portfolio_rules(max_position_pct=0.50)


def bar(instrument, close, when=None, available=None):
    when = when or AS_OF - timedelta(days=1)
    return MarketObservation(
        instrument_id=instrument,
        market_family="equity",
        timestamp=when,
        available_at=available or when,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        currency="INR",
        unit="share",
    )


def held(instrument, quantity, price):
    return PaperPosition(
        instrument_id=instrument, quantity=quantity, price=price, value=quantity * price, weight=0.0
    )


EXAMPLE_POSITIONS = [held(AAA, 40, 1450), held(BBB, 40, 820)]
EXAMPLE_PRICES = [bar(AAA, 1450), bar(BBB, 820)]
EXAMPLE_TARGETS = {AAA: 0.45, BBB: 0.45}


def test_brief_worked_example_exactly():
    plan = rebalance(EXAMPLE_POSITIONS, 9200, EXAMPLE_TARGETS, EXAMPLE_PRICES, EXAMPLE_RULES, AS_OF)
    trades = [(p.side, p.instrument_id, p.quantity, p.amount_inr) for p in plan.proposals]
    assert trades == [("sell", AAA, 8, 11600), ("buy", BBB, 13, 10660)]  # sells first
    after = {p.instrument_id: (p.quantity, p.value) for p in plan.positions}
    assert after == {AAA: (32, 46400), BBB: (53, 43460)}
    assert plan.cash_inr == 10140
    assert plan.budget_inr == 100000
    assert 46400 + 43460 + plan.cash_inr == 100000
    assert plan.rules_version == "portfolio-test"
    assert all(p.label.endswith("research only, not advice") for p in plan.proposals)


def test_worked_example_passes_risk_with_stated_fifty_percent_cap():
    plan = rebalance(EXAMPLE_POSITIONS, 9200, EXAMPLE_TARGETS, EXAMPLE_PRICES, EXAMPLE_RULES, AS_OF)
    verdicts = check(plan.proposals, EXAMPLE_POSITIONS, 9200, EXAMPLE_PRICES, EXAMPLE_RULES, AS_OF)
    assert [v.verdict for v in verdicts] == ["PASS", "PASS"]
    assert [v.proposal_id for v in verdicts] == [p.proposal_id for p in plan.proposals]


def test_inside_band_means_no_trades():
    positions = [held(AAA, 31, 1450), held(BBB, 55, 820)]  # 44.95 % and 45.10 %
    plan = rebalance(
        positions,
        100000 - 31 * 1450 - 55 * 820,
        EXAMPLE_TARGETS,
        EXAMPLE_PRICES,
        EXAMPLE_RULES,
        AS_OF,
    )
    assert plan.proposals == []
    assert {p.instrument_id: p.quantity for p in plan.positions} == {AAA: 31, BBB: 55}


def test_buffer_limits_buys():
    positions = [held(AAA, 60, 1450)]  # 87,000 held, cash 13,000, total 1,00,000
    plan = rebalance(
        positions,
        13000,
        {AAA: 0.87, BBB: 0.10},
        [bar(AAA, 1450), bar(BBB, 100)],
        EXAMPLE_RULES | {"max_position_pct": 0.9},
        AS_OF,
    )
    [proposal] = plan.proposals
    # Target says 10,000 of BBB, but only 13,000 - 10,000 = 3,000 is above the buffer.
    assert (proposal.side, proposal.instrument_id, proposal.quantity) == ("buy", BBB, 30)
    assert plan.cash_inr == 10000


def test_buys_never_exceed_cap():
    plan = rebalance([], 100000, {AAA: 0.45}, [bar(AAA, 1000)], portfolio_rules(), AS_OF)
    [proposal] = plan.proposals
    assert proposal.quantity == 25  # cap 25 % of 1,00,000, not the 45 % target
    assert any("cap" in warning for warning in plan.warnings)


def test_name_not_in_targets_sold_fully():
    positions = [held(AAA, 31, 1450), held(CCC, 3, 500)]
    plan = rebalance(
        positions,
        100000 - 31 * 1450 - 1500,
        {AAA: 0.45},
        [bar(AAA, 1450), bar(CCC, 500)],
        EXAMPLE_RULES,
        AS_OF,
    )
    [proposal] = [p for p in plan.proposals if p.instrument_id == CCC]
    assert (proposal.side, proposal.quantity) == ("sell", 3)  # 1,500 still closes fully
    assert "not in targets" in proposal.reason
    assert CCC not in {p.instrument_id for p in plan.positions}


def test_trade_under_min_trade_skipped():
    positions = [held(AAA, 10, 100)]  # total 2,000: AAA 50 %, target 40 %: sell 2 sh = 200
    plan = rebalance(positions, 1000, {AAA: 0.40}, [bar(AAA, 100)], EXAMPLE_RULES, AS_OF)
    assert plan.proposals == []
    assert any("min_trade_inr" in warning for warning in plan.warnings)


def test_positions_valued_at_latest_cutoff_safe_price():
    prices = [
        bar(AAA, 1450),
        bar(AAA, 3000, when=AS_OF + timedelta(hours=1)),
        bar(AAA, 3000, when=AS_OF - timedelta(hours=2), available=AS_OF + timedelta(minutes=5)),
        bar(BBB, 820),
    ]
    stale_marks = [held(AAA, 40, 999), held(BBB, 40, 820)]  # given price is replaced by 1,450
    plan = rebalance(stale_marks, 9200, EXAMPLE_TARGETS, prices, EXAMPLE_RULES, AS_OF)
    assert [(p.side, p.quantity) for p in plan.proposals] == [("sell", 8), ("buy", 13)]


def test_unpriced_position_is_not_traded():
    plan = rebalance(
        [held(AAA, 40, 1450), held(BBB, 40, 820)],
        9200,
        EXAMPLE_TARGETS,
        [bar(BBB, 820)],
        EXAMPLE_RULES,
        AS_OF,
    )
    assert all(p.instrument_id != AAA for p in plan.proposals)
    assert any(AAA in warning and "price" in warning for warning in plan.warnings)


def test_deterministic():
    first = rebalance(
        EXAMPLE_POSITIONS, 9200, EXAMPLE_TARGETS, EXAMPLE_PRICES, EXAMPLE_RULES, AS_OF
    )
    second = rebalance(
        list(reversed(EXAMPLE_POSITIONS)),
        9200,
        dict(reversed(EXAMPLE_TARGETS.items())),
        list(reversed(EXAMPLE_PRICES)),
        EXAMPLE_RULES,
        AS_OF,
    )
    assert first == second


@pytest.mark.parametrize(
    "targets",
    [{AAA: 0.6, BBB: 0.6}, {AAA: -0.1}, {AAA: float("nan")}, {AAA: "0.4"}, {"": 0.3}],
)
def test_invalid_targets_raise(targets):
    with pytest.raises(ValueError):
        rebalance(EXAMPLE_POSITIONS, 9200, targets, EXAMPLE_PRICES, EXAMPLE_RULES, AS_OF)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        rebalance(EXAMPLE_POSITIONS, -1, EXAMPLE_TARGETS, EXAMPLE_PRICES, EXAMPLE_RULES, AS_OF)
    with pytest.raises(ValueError):
        rebalance(
            EXAMPLE_POSITIONS + [held(AAA, 1, 1450)],
            9200,
            EXAMPLE_TARGETS,
            EXAMPLE_PRICES,
            EXAMPLE_RULES,
            AS_OF,
        )
    with pytest.raises(ValueError):
        rebalance(
            EXAMPLE_POSITIONS,
            9200,
            EXAMPLE_TARGETS,
            EXAMPLE_PRICES,
            EXAMPLE_RULES,
            datetime(2026, 3, 2),
        )
