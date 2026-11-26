"""Paper-portfolio rebalance. Values paper positions at their latest cutoff-safe prices, measures
drift from target weights, and proposes whole-share paper sells (first) and buys (then, using only
cash above the buffer and never above the per-name cap) for names outside the drift band. Names
not in the targets are sold fully. Research only, not advice; nothing places orders.
"""

import math
from collections.abc import Iterable, Mapping
from datetime import datetime

from .schemas import MarketObservation, PaperPlan, PaperPosition, PaperTradeProposal, utc
from .sizing import EPS, finite_number, inr, price_table, validate_portfolio_rules


def _validate_targets(targets: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(targets, Mapping):
        raise ValueError("targets must map instrument IDs to weights")
    for name, weight in targets.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Target instrument IDs must be nonempty strings")
        if not finite_number(weight) or not 0 <= weight <= 1:
            raise ValueError(f"Target weight for {name} must be a number from 0 to 1")
    if sum(targets.values()) > 1 + EPS:
        raise ValueError("Target weights cannot add up to more than 1")
    return {name: float(targets[name]) for name in sorted(targets)}


def _proposal(name, side, quantity, price, reason) -> PaperTradeProposal:
    return PaperTradeProposal(
        instrument_id=name,
        side=side,
        quantity=quantity,
        price=price,
        amount_inr=round(quantity * price, 2),
        reason=reason,
    )


def rebalance(
    positions: list[PaperPosition],
    cash_inr: float,
    targets: Mapping[str, float],
    prices: Mapping[str, float] | Iterable[MarketObservation],
    rules: dict,
    as_of: datetime,
) -> PaperPlan:
    """Propose paper trades that bring positions back toward target weights."""
    rules = validate_portfolio_rules(rules)
    cutoff = utc(as_of)
    targets = _validate_targets(targets)
    if not finite_number(cash_inr) or cash_inr < 0:
        raise ValueError("cash_inr must be a finite number of at least 0")
    table = price_table(prices, cutoff)
    warnings: list[str] = []

    quantity: dict[str, int] = {}
    price: dict[str, float] = {}
    tradable: set[str] = set()
    for position in sorted(positions, key=lambda p: p.instrument_id):
        name = position.instrument_id
        if name in quantity:
            raise ValueError(f"{name} appears twice in positions")
        quantity[name] = position.quantity
        if name in table:
            price[name] = table[name]
            tradable.add(name)
        else:
            price[name] = position.price
            warnings.append(
                f"{name} not traded: no cutoff-safe price, valued at given {inr(position.price)}"
            )
    for name in targets:
        if name not in quantity:
            quantity[name] = 0
            if name in table:
                price[name] = table[name]
                tradable.add(name)
            else:
                warnings.append(f"{name} not bought: no cutoff-safe price")

    cash = float(cash_inr)
    total = cash + sum(quantity[n] * price[n] for n in quantity if n in price)
    band = rules["rebalance_band_pp"]
    cap_value = rules["max_position_pct"] * total
    buffer = rules["cash_buffer_pct"] * total
    sells, buys = [], []

    def drift(name):
        weight = quantity[name] * price[name] / total if total else 0.0
        return (weight - targets.get(name, 0.0)) * 100, weight

    for name in sorted(tradable):
        if name not in targets:
            if quantity[name] > 0:
                sells.append((name, quantity[name], "not in targets; sell the whole position"))
            continue
        pp, weight = drift(name)
        if abs(pp) <= band + EPS:
            continue
        target_value = targets[name] * total
        value = quantity[name] * price[name]
        description = (
            f"weight {weight:.2%} vs target {targets[name]:.2%} "
            f"(drift {pp:+.2f} pp, band {band} pp)"
        )
        if pp > 0:
            shares = math.floor((value - target_value) / price[name] + EPS)
            sells.append((name, shares, description))  # partial: subject to min_trade_inr
        else:
            buys.append((pp, name, description))

    proposals = []
    for name, shares, description in sells:
        closes = shares == quantity[name]  # Closing sells are kept whatever their size.
        if not closes and (shares <= 0 or shares * price[name] < rules["min_trade_inr"] - EPS):
            warnings.append(
                f"{name} sell skipped: {inr(max(shares, 0) * price[name])} is under "
                f"min_trade_inr {inr(rules['min_trade_inr'])}"
            )
            continue
        proposals.append(_proposal(name, "sell", shares, price[name], f"rebalance: {description}"))
    for proposal in proposals:
        quantity[proposal.instrument_id] -= proposal.quantity
        cash += proposal.amount_inr

    for _, name, description in sorted(buys):
        value = quantity[name] * price[name]
        available = max(cash - buffer, 0.0)
        wanted = targets[name] * total - value
        shares = math.floor(min(wanted, available) / price[name] + EPS)
        room = math.floor(max(cap_value - value, 0.0) / price[name] + EPS)
        if shares > room:
            warnings.append(f"{name} buy limited by the {rules['max_position_pct']:.0%} cap")
            shares = room
        if shares <= 0 or shares * price[name] < rules["min_trade_inr"] - EPS:
            warnings.append(
                f"{name} buy skipped: {inr(max(shares, 0) * price[name])} is under "
                f"min_trade_inr {inr(rules['min_trade_inr'])} "
                f"(cash above buffer {inr(available)})"
            )
            continue
        proposal = _proposal(name, "buy", shares, price[name], f"rebalance: {description}")
        proposals.append(proposal)
        quantity[name] += shares
        cash -= proposal.amount_inr

    cash = round(cash, 2)
    result = [
        PaperPosition(
            instrument_id=name,
            quantity=quantity[name],
            price=price[name],
            value=round(quantity[name] * price[name], 2),
            weight=quantity[name] * price[name] / total if total else 0.0,
        )
        for name in sorted(quantity)
        if quantity[name] > 0
    ]
    return PaperPlan(
        as_of=cutoff,
        rules_version=rules["version"],
        budget_inr=round(total, 2),
        cash_inr=cash,
        positions=result,
        proposals=proposals,
        warnings=warnings,
    )
