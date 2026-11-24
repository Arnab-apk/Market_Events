"""Paper-portfolio sizing. Splits a hypothetical INR budget across a shortlist into whole-share
paper buys: a cash buffer is kept, weights are water-filled under a per-name cap, slices under the
minimum order are dropped, and leftover rupees buy single extra shares without breaking the cap
or the buffer. Prices come only from cutoff-safe ledger bars. Research only, not advice.
"""

import json
import math
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from .schemas import MarketObservation, PaperPlan, PaperPosition, PaperTradeProposal, utc

EPS = 1e-9
MARKET_FAMILIES = {"equity", "commodity", "benchmark"}
PORTFOLIO_KEYS = {
    "version",
    "currency",
    "budget_inr",
    "cash_buffer_pct",
    "max_position_pct",
    "min_order_inr",
    "max_order_inr",
    "weighting",
    "rebalance_band_pp",
    "min_trade_inr",
    "max_price_age_days",
    "allowed_market_families",
    "blocked_instruments",
    "max_proposals_per_plan",
}


def finite_number(value) -> bool:
    """True for a real int/float that is not NaN or infinite (bools excluded)."""
    return type(value) in (int, float) and math.isfinite(value)


def inr(amount: float) -> str:
    """Format rupees for warnings and reasons."""
    return f"₹{amount:,.2f}"


def validate_portfolio_rules(rules: dict) -> dict:
    """Return a private copy of valid portfolio rules; raise ValueError otherwise."""
    if not isinstance(rules, dict):
        raise ValueError("Portfolio rules must be a JSON object")
    rules = deepcopy(rules)
    if set(rules) != PORTFOLIO_KEYS:
        missing, unknown = PORTFOLIO_KEYS - set(rules), set(rules) - PORTFOLIO_KEYS
        raise ValueError(
            f"Portfolio rules keys: missing {sorted(missing)}, unknown {sorted(unknown)}"
        )
    version = rules["version"]
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Portfolio rules require a nonempty version")
    if rules["currency"] != "INR":
        raise ValueError("Portfolio currency must be INR")
    for key in ("cash_buffer_pct", "max_position_pct"):
        if not finite_number(rules[key]) or not 0 < rules[key] < 1:
            raise ValueError(f"{key} must be a fraction strictly between 0 and 1")
    for key in (
        "budget_inr",
        "min_order_inr",
        "max_order_inr",
        "min_trade_inr",
        "max_price_age_days",
    ):
        if not finite_number(rules[key]) or rules[key] <= 0:
            raise ValueError(f"{key} must be a finite number above 0")
    if rules["min_order_inr"] > rules["max_order_inr"]:
        raise ValueError("min_order_inr cannot exceed max_order_inr")
    band = rules["rebalance_band_pp"]
    if not finite_number(band) or not 0 < band < 100:
        raise ValueError("rebalance_band_pp must be between 0 and 100 percentage points")
    if rules["weighting"] not in {"score", "equal"}:
        raise ValueError("weighting must be 'score' or 'equal'")
    families = rules["allowed_market_families"]
    if not isinstance(families, list) or not set(families) <= MARKET_FAMILIES:
        raise ValueError(f"allowed_market_families must be a list from {sorted(MARKET_FAMILIES)}")
    blocked = rules["blocked_instruments"]
    if not isinstance(blocked, list) or any(not isinstance(b, str) or not b for b in blocked):
        raise ValueError("blocked_instruments must be a list of instrument IDs")
    limit = rules["max_proposals_per_plan"]
    if type(limit) is not int or limit < 1:
        raise ValueError("max_proposals_per_plan must be a positive integer")
    return rules


def load_portfolio_rules(root: Path = Path(".")) -> dict:
    """Read and validate configs/portfolio_rules.json."""
    path = Path(root) / "configs" / "portfolio_rules.json"
    return validate_portfolio_rules(json.loads(path.read_text(encoding="utf-8")))


def latest_quotes(
    observations: Iterable[MarketObservation], as_of: datetime
) -> dict[str, MarketObservation]:
    """Newest bar per instrument whose session and availability are both at or before as_of."""
    cutoff = utc(as_of)
    latest: dict[str, MarketObservation] = {}
    eligible = [o for o in observations if o.timestamp <= cutoff and o.available_at <= cutoff]
    for row in sorted(eligible, key=lambda o: (o.timestamp, o.available_at, o.model_dump_json())):
        latest[row.instrument_id] = row
    return latest


def price_table(
    prices: Mapping[str, float] | Iterable[MarketObservation], as_of: datetime
) -> dict[str, float]:
    """Instrument -> price, from cutoff-safe observations or an explicit validated mapping."""
    if isinstance(prices, Mapping):
        table = {}
        for instrument, price in prices.items():
            if not finite_number(price) or price <= 0:
                raise ValueError(f"Price for {instrument} must be a finite number above 0")
            table[instrument] = float(price)
        return table
    return {k: v.close for k, v in latest_quotes(prices, as_of).items()}


def water_fill(weights: dict[str, float], money: float, cap: float) -> dict[str, float]:
    """Split money proportional to weight; names over cap are pinned at cap and the rest re-split.

    If every name is capped, the remainder is simply not allocated.
    """
    slices: dict[str, float] = {}
    active = dict(weights)
    while active and money > EPS:
        total = sum(active.values())
        trial = {name: money * weight / total for name, weight in active.items()}
        over = [name for name, amount in trial.items() if amount > cap + EPS]
        if not over:
            slices.update(trial)
            return slices
        for name in over:
            slices[name] = cap
            money -= cap
            del active[name]
    slices.update(dict.fromkeys(active, 0.0))
    return slices


def size(
    shortlist_scores: Mapping[str, float],
    prices: Mapping[str, float] | Iterable[MarketObservation],
    rules: dict,
    as_of: datetime,
) -> PaperPlan:
    """Size whole-share paper buys for a shortlist {instrument_id: evidence score}."""
    rules = validate_portfolio_rules(rules)
    cutoff = utc(as_of)
    table = price_table(prices, cutoff)
    budget = float(rules["budget_inr"])
    investable = budget * (1 - rules["cash_buffer_pct"])
    cap = budget * rules["max_position_pct"]
    warnings: list[str] = []

    weights: dict[str, float] = {}
    for name in sorted(shortlist_scores):
        score = shortlist_scores[name]
        if not finite_number(score):
            raise ValueError(f"Score for {name} must be a finite number")
        if name not in table:
            warnings.append(f"{name} dropped: no cutoff-safe price at or before {cutoff}")
        elif rules["weighting"] == "score" and score <= 0:
            warnings.append(f"{name} dropped: score {score} cannot be used as a weight")
        else:
            weights[name] = 1.0 if rules["weighting"] == "equal" else float(score)

    while True:
        slices = water_fill(weights, investable, cap)
        under = sorted(n for n in weights if slices[n] < rules["min_order_inr"] - EPS)
        if not under:
            break
        for name in under:
            warnings.append(
                f"{name} dropped: slice {inr(slices[name])} is under the minimum order "
                f"{inr(rules['min_order_inr'])}"
            )
            del weights[name]
    if weights and sum(slices.values()) < investable - 0.005:
        idle = investable - sum(slices.values())
        warnings.append(f"Every name is at its cap; {inr(idle)} of investable money stays in cash")

    quantities = {n: math.floor(slices[n] / table[n] + EPS) for n in weights}
    leftover = investable - sum(quantities[n] * table[n] for n in weights)
    while True:
        eligible = [
            n
            for n in weights
            if table[n] <= leftover + EPS and (quantities[n] + 1) * table[n] <= cap + EPS
        ]
        if not eligible:
            break
        pick = min(eligible, key=lambda n: (-(slices[n] - quantities[n] * table[n]), n))
        quantities[pick] += 1
        leftover -= table[pick]

    proposals, positions = [], []
    for name in sorted(weights):
        quantity, price = quantities[name], table[name]
        if quantity == 0:
            warnings.append(f"{name} skipped: one share at {inr(price)} does not fit its slice")
            continue
        amount = round(quantity * price, 2)
        proposals.append(
            PaperTradeProposal(
                instrument_id=name,
                side="buy",
                quantity=quantity,
                price=price,
                amount_inr=amount,
                reason=f"size: slice {inr(slices[name])} of {inr(investable)} investable "
                f"({rules['weighting']} weighting, cap {inr(cap)})",
            )
        )
        positions.append(
            PaperPosition(
                instrument_id=name,
                quantity=quantity,
                price=price,
                value=amount,
                weight=amount / budget,
            )
        )
    if not proposals:
        warnings.append("No paper buys: nothing in the shortlist could be sized")
    cash = round(budget - sum(p.amount_inr for p in proposals), 2)
    return PaperPlan(
        as_of=cutoff,
        rules_version=rules["version"],
        budget_inr=budget,
        cash_inr=cash,
        positions=positions,
        proposals=proposals,
        warnings=warnings,
    )
