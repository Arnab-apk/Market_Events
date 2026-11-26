"""Risk limits: one test per BLOCK reason, running state and cutoff safety (offline)."""

from datetime import datetime, timedelta, timezone

import pytest

from market_events.risk_limits import check
from market_events.schemas import MarketObservation, PaperPosition, PaperTradeProposal

AS_OF = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)
AAA, BBB = "SYNTHETIC:NSE:AAA", "SYNTHETIC:NSE:BBB"
GOLD, NIFTY = "SYNTHETIC:MCX:GOLD", "NIFTY50"


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


def bar(instrument, close, when=None, available=None, family="equity"):
    when = when or AS_OF - timedelta(days=1)
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


PRICES = [
    bar(AAA, 1450),
    bar(BBB, 820),
    bar(GOLD, 6000, family="commodity"),
    bar(NIFTY, 22000, family="benchmark"),
]


def buy(instrument, quantity, price, reason="test"):
    return PaperTradeProposal(
        instrument_id=instrument,
        side="buy",
        quantity=quantity,
        price=price,
        amount_inr=round(quantity * price, 2),
        reason=reason,
    )


def sell(instrument, quantity, price, reason="test"):
    return PaperTradeProposal(
        instrument_id=instrument,
        side="sell",
        quantity=quantity,
        price=price,
        amount_inr=round(quantity * price, 2),
        reason=reason,
    )


def held(instrument, quantity, price):
    return PaperPosition(
        instrument_id=instrument, quantity=quantity, price=price, value=quantity * price, weight=0.0
    )


def one(proposal, positions=(), cash=100000, prices=PRICES, **overrides):
    [verdict] = check(
        [proposal], list(positions), cash, prices, portfolio_rules(**overrides), AS_OF
    )
    return verdict


def has(verdict, text):
    return verdict.verdict == "BLOCK" and any(text in reason for reason in verdict.reasons)


def test_valid_buy_passes():
    verdict = one(buy(AAA, 17, 1450))
    assert verdict.verdict == "PASS" and verdict.reasons == []
    assert verdict.proposal_id == buy(AAA, 17, 1450).proposal_id


def test_blocked_instrument():
    assert has(one(buy(AAA, 17, 1450), blocked_instruments=[AAA]), "blocked instrument")


def test_commodity_and_benchmark_buys_always_blocked():
    everything = ["equity", "commodity", "benchmark"]
    assert has(one(buy(GOLD, 1, 6000), allowed_market_families=everything), "cannot be bought")
    assert has(one(buy(NIFTY, 1, 22000), allowed_market_families=everything), "cannot be bought")
    assert has(one(buy(NIFTY, 1, 22000)), "not allowed")


def test_market_family_not_allowed_blocks_sell():
    verdict = one(sell(GOLD, 1, 6000), positions=[held(GOLD, 1, 6000)], cash=94000)
    assert has(verdict, "market family 'commodity' not allowed")


@pytest.mark.parametrize(
    "raw",
    [
        {"instrument_id": AAA, "side": "buy", "quantity": 0, "price": 1450, "amount_inr": 0},
        {"instrument_id": AAA, "side": "buy", "quantity": 1.5, "price": 1450, "amount_inr": 2175},
        {"instrument_id": AAA, "side": "buy", "quantity": 4, "price": -1, "amount_inr": -4},
        {
            "instrument_id": AAA,
            "side": "buy",
            "quantity": 4,
            "price": float("nan"),
            "amount_inr": 5800,
        },
        {
            "instrument_id": AAA,
            "side": "buy",
            "quantity": 4,
            "price": float("inf"),
            "amount_inr": 5800,
        },
        {"instrument_id": AAA, "side": "short", "quantity": 4, "price": 1450, "amount_inr": 5800},
        {"instrument_id": AAA, "side": "buy", "quantity": 4, "price": 1450, "amount_inr": 9999},
        {"instrument_id": "", "side": "buy", "quantity": 4, "price": 1450, "amount_inr": 5800},
    ],
)
def test_malformed_proposals_blocked(raw):
    raw = {**raw, "reason": "bad", "proposal_id": "manual"}
    for proposal in (raw, PaperTradeProposal.model_construct(**raw)):
        verdict = one(proposal)
        assert has(verdict, "malformed") and verdict.proposal_id == "manual"


def test_order_above_max_and_multiple_reasons_collected():
    verdict = one(buy(AAA, 40, 1450))  # 58,000 is above 50,000 and 58 % of the portfolio.
    assert has(verdict, "above max_order_inr")
    assert has(verdict, "above max_position_pct")
    assert len(verdict.reasons) >= 2


def test_order_below_min():
    assert has(one(buy(AAA, 2, 1450)), "below min_order_inr")


def test_small_sell_allowed_only_when_closing_whole_position():
    positions = [held(AAA, 2, 1450)]
    assert one(sell(AAA, 2, 1450), positions=positions, cash=97100).verdict == "PASS"
    positions = [held(AAA, 3, 1450)]
    assert has(one(sell(AAA, 2, 1450), positions=positions, cash=95650), "below min_order_inr")


def test_would_go_short():
    assert has(
        one(sell(AAA, 5, 1450), positions=[held(AAA, 4, 1450)], cash=94200), "would go short"
    )
    assert has(one(sell(BBB, 10, 820)), "would go short")


def test_position_weight_above_cap():
    assert has(one(buy(AAA, 18, 1450)), "above max_position_pct")  # 26.1 %


def test_eats_cash_buffer():
    positions = [held(BBB, 85, 820)]  # 69,700 held, so total is 1,00,000 with 30,300 cash.
    verdict = one(buy(AAA, 15, 1450), positions=positions, cash=30300)  # leaves 8,550
    assert has(verdict, "eats cash buffer")


def test_stale_price():
    stale = [bar(AAA, 1450, when=AS_OF - timedelta(days=6))]
    assert has(one(buy(AAA, 17, 1450), prices=stale), "stale price")


def test_later_price_is_ignored_for_staleness():
    prices = [
        bar(AAA, 1450, when=AS_OF - timedelta(days=9)),
        bar(AAA, 1450, when=AS_OF + timedelta(hours=2)),  # after the cutoff
        bar(AAA, 1450, when=AS_OF - timedelta(hours=20), available=AS_OF + timedelta(hours=1)),
    ]
    assert has(one(buy(AAA, 17, 1450), prices=prices), "stale price")


def test_no_cutoff_safe_price():
    assert has(one(buy(AAA, 17, 1450), prices=[]), "no cutoff-safe price")


def test_duplicate_proposal_id():
    proposal = buy(AAA, 5, 1450)
    first, second = check([proposal, proposal], [], 100000, PRICES, portfolio_rules(), AS_OF)
    assert first.verdict == "PASS"
    assert has(second, "duplicate proposal_id")


def test_extra_proposals_beyond_limit_blocked():
    proposals = [buy(AAA, 4, 1450, reason=str(i)) for i in range(3)]
    verdicts = check(
        proposals, [], 100000, PRICES, portfolio_rules(max_proposals_per_plan=2), AS_OF
    )
    assert [v.verdict for v in verdicts] == ["PASS", "PASS", "BLOCK"]
    assert has(verdicts[2], "max_proposals_per_plan")


def test_blocked_proposal_does_not_change_state():
    # The first buy is blocked; if it had filled, the second would breach the 25 % cap.
    verdicts = check(
        [buy(AAA, 40, 1450), buy(AAA, 17, 1450)], [], 100000, PRICES, portfolio_rules(), AS_OF
    )
    assert [v.verdict for v in verdicts] == ["BLOCK", "PASS"]


def test_passed_proposal_changes_state():
    proposals = [sell(AAA, 10, 1450, "a"), sell(AAA, 10, 1450, "b")]
    verdicts = check(proposals, [held(AAA, 15, 1450)], 78250, PRICES, portfolio_rules(), AS_OF)
    assert verdicts[0].verdict == "PASS"
    assert has(verdicts[1], "would go short")


def test_bad_inputs_raise():
    with pytest.raises(ValueError):
        check([], [], float("nan"), PRICES, portfolio_rules(), AS_OF)
    with pytest.raises(ValueError):
        check([], [held(AAA, 1, 1450), held(AAA, 2, 1450)], 0, PRICES, portfolio_rules(), AS_OF)
    with pytest.raises(ValueError):
        check([], [], 100, PRICES, portfolio_rules(), datetime(2026, 3, 2))
