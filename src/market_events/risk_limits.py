"""Paper-portfolio risk limits. Checks each paper proposal, in order, against the user's limits in
configs/portfolio_rules.json and a running paper state, returning PASS or BLOCK with every reason.
Blocked proposals do not change the state; passed ones do. Prices, their age and market family
come only from cutoff-safe ledger bars. Research only, not advice; nothing places orders.
"""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from pydantic import BaseModel, ValidationError

from .schemas import MarketObservation, PaperPosition, PaperTradeProposal, RiskVerdict, utc
from .sizing import EPS, finite_number, inr, latest_quotes, validate_portfolio_rules

BUYABLE_FAMILIES = {"equity"}


def _raw(proposal) -> dict:
    """Field values of a proposal without re-validating (it may be malformed)."""
    if isinstance(proposal, BaseModel):
        return dict(proposal.__dict__)
    if isinstance(proposal, Mapping):
        return dict(proposal)
    raise ValueError("Each proposal must be a PaperTradeProposal or a mapping")


def _malformed(raw: dict, index: int) -> tuple[list[str], str]:
    """Malformed reasons and the proposal ID to report."""
    reasons = []
    instrument = raw.get("instrument_id")
    quantity, price, amount = raw.get("quantity"), raw.get("price"), raw.get("amount_inr")
    if not isinstance(instrument, str) or not instrument.strip():
        reasons.append("malformed: missing instrument_id")
    if raw.get("side") not in {"buy", "sell"}:
        reasons.append(f"malformed: unknown side {raw.get('side')!r}")
    if type(quantity) is not int or quantity <= 0:
        reasons.append(f"malformed: quantity {quantity!r} is not a positive whole number")
    if not finite_number(price) or price <= 0:
        reasons.append(f"malformed: price {price!r} is not a finite number above 0")
    if not finite_number(amount):
        reasons.append(f"malformed: amount_inr {amount!r} is not a finite number")
    elif not reasons and abs(amount - quantity * price) > 0.01 + EPS:
        reasons.append("malformed: amount_inr does not equal quantity × price")
    given = raw.get("proposal_id") or ""
    if reasons:
        return reasons, given or f"malformed-{index}"
    try:
        validated = PaperTradeProposal.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        return [f"malformed: {first['msg']}"], given or f"malformed-{index}"
    return [], validated.proposal_id


def check(
    proposals: list[PaperTradeProposal | Mapping],
    positions: list[PaperPosition],
    cash_inr: float,
    prices: Iterable[MarketObservation],
    rules: dict,
    as_of: datetime,
) -> list[RiskVerdict]:
    """Return one verdict per proposal, applying passed ones to a running paper state."""
    rules = validate_portfolio_rules(rules)
    cutoff = utc(as_of)
    if not finite_number(cash_inr) or cash_inr < 0:
        raise ValueError("cash_inr must be a finite number of at least 0")
    holdings: dict[str, tuple[int, float]] = {}
    for position in positions:
        if position.instrument_id in holdings:
            raise ValueError(f"{position.instrument_id} appears twice in positions")
        holdings[position.instrument_id] = (position.quantity, position.price)
    cash = float(cash_inr)
    quotes = latest_quotes(prices, cutoff)
    max_age = timedelta(days=rules["max_price_age_days"])
    seen: set[str] = set()
    verdicts = []

    for index, proposal in enumerate(proposals):
        raw = _raw(proposal)
        reasons, proposal_id = _malformed(raw, index)
        if proposal_id in seen:
            reasons.append("duplicate proposal_id")
        seen.add(proposal_id)
        if index >= rules["max_proposals_per_plan"]:
            reasons.append(f"exceeds max_proposals_per_plan ({rules['max_proposals_per_plan']})")
        instrument = raw.get("instrument_id")
        if instrument in rules["blocked_instruments"]:
            reasons.append("blocked instrument")
        if any(reason.startswith("malformed") for reason in reasons):
            verdicts.append(RiskVerdict(proposal_id=proposal_id, verdict="BLOCK", reasons=reasons))
            continue

        side, quantity, price = raw["side"], raw["quantity"], float(raw["price"])
        amount = float(raw["amount_inr"])
        quote = quotes.get(instrument)
        if quote is None:
            reasons.append(f"no cutoff-safe price at or before {cutoff.isoformat()}")
        else:
            family = quote.market_family
            if side == "buy" and family not in BUYABLE_FAMILIES:
                reasons.append(f"{family} instruments cannot be bought")
            if family not in rules["allowed_market_families"]:
                reasons.append(f"market family '{family}' not allowed")
            age = cutoff - quote.timestamp
            if age > max_age:
                reasons.append(
                    f"stale price: newest bar is {age.days} days old "
                    f"(limit {rules['max_price_age_days']})"
                )

        held_quantity, held_price = holdings.get(instrument, (0, price))
        if amount > rules["max_order_inr"] + EPS:
            reasons.append(f"order {inr(amount)} above max_order_inr {inr(rules['max_order_inr'])}")
        closes_position = side == "sell" and quantity == held_quantity
        if amount < rules["min_order_inr"] - EPS and not closes_position:
            reasons.append(f"order {inr(amount)} below min_order_inr {inr(rules['min_order_inr'])}")
        if side == "sell" and quantity > held_quantity:
            reasons.append(f"would go short: selling {quantity}, holding {held_quantity}")

        new_quantity = held_quantity + quantity if side == "buy" else held_quantity - quantity
        new_cash = cash - amount if side == "buy" else cash + amount
        others = sum(q * p for name, (q, p) in holdings.items() if name != instrument)
        position_value = max(new_quantity, 0) * price
        total = new_cash + others + position_value
        if side == "buy":
            if total > 0 and position_value / total > rules["max_position_pct"] + EPS:
                reasons.append(
                    f"position weight {position_value / total:.2%} above max_position_pct "
                    f"{rules['max_position_pct']:.0%}"
                )
            if new_cash < rules["cash_buffer_pct"] * total - EPS:
                reasons.append(
                    f"eats cash buffer: cash after {inr(new_cash)} is under "
                    f"{rules['cash_buffer_pct']:.0%} of {inr(total)}"
                )

        if reasons:
            verdicts.append(RiskVerdict(proposal_id=proposal_id, verdict="BLOCK", reasons=reasons))
            continue
        cash = new_cash
        if new_quantity:
            holdings[instrument] = (new_quantity, price if side == "buy" else held_price)
        else:
            holdings.pop(instrument, None)
        verdicts.append(RiskVerdict(proposal_id=proposal_id, verdict="PASS", reasons=[]))
    return verdicts
