"""Paper portfolio orchestrator: screen -> size -> risk for a new plan, and rebalance -> risk for
existing paper holdings. It reads only the local ledger (saved runs and observations at or before
``as_of``), never a network or broker, and every output is a labelled paper proposal for research,
not an order or advice. Numerical rules live in screener, sizing, risk_limits and rebalance.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .rebalance import rebalance
from .risk_limits import check
from .schemas import (
    PAPER_LABEL,
    AnalysisRun,
    MarketObservation,
    PaperPlan,
    PaperPosition,
    PaperTradeProposal,
    ScreenResult,
    utc,
)
from .screener import load_screener_rules, screen
from .sizing import latest_quotes, load_portfolio_rules, size
from .technicals import compute_technicals

IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Universe scoping (synthetic and live records never mix in one plan)
# ---------------------------------------------------------------------------


class ScopedLedger:
    """Read-only slice of a ledger holding one universe's runs and observations."""

    def __init__(self, storage, universe: str):
        if universe not in {"demo", "live"}:
            raise ValueError("Universe must be demo or live")
        self.storage = storage
        self.live = universe == "live"

    def list_runs(self) -> list[AnalysisRun]:
        """Runs whose article belongs to this universe."""
        return [
            r for r in self.storage.list_runs() if r.article_id.startswith("LIVE:") == self.live
        ]

    def list_observations(self) -> list[MarketObservation]:
        """Observations whose instrument belongs to this universe."""
        return [
            o
            for o in self.storage.list_observations()
            if o.instrument_id.startswith("LIVE:") == self.live
        ]


def scoped(storage, universe: str) -> ScopedLedger:
    """Wrap a Storage (or read-only view) so only one universe is visible."""
    return ScopedLedger(storage, universe)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


def _versions(screener_rules: dict, portfolio_rules: dict) -> str:
    return f"{screener_rules['version']}+{portfolio_rules['version']}"


def _screen(storage, screener_rules: dict, as_of: datetime) -> ScreenResult:
    runs = storage.list_runs()
    observations = storage.list_observations()
    companies = sorted(
        {
            r.extraction.company_id
            for r in runs
            if r.extraction
            and r.extraction.company_id
            and r.assessment
            and r.decision_time <= as_of
        }
    )
    technicals = {c: compute_technicals(observations, as_of, c) for c in companies}
    return screen(runs, technicals, screener_rules, as_of)


def _screen_warnings(result: ScreenResult) -> list[str]:
    when = result.as_of.isoformat()
    if not result.rows:
        return [f"No assessed runs at or before as_of {when}; nothing to screen or size"]
    if not result.shortlist:
        return [f"No company passed screener rules {result.rules_version} at as_of {when}"]
    return []


def _apply(
    positions: list[PaperPosition],
    cash_inr: float,
    proposals: list[PaperTradeProposal],
    prices: Mapping[str, float],
) -> tuple[list[PaperPosition], float]:
    """Resulting holdings and cash after the given proposals fill at their own prices."""
    held = {p.instrument_id: p.quantity for p in positions}
    price = {p.instrument_id: p.price for p in positions} | dict(prices)
    cash = cash_inr
    for proposal in proposals:
        sign = 1 if proposal.side == "buy" else -1
        held[proposal.instrument_id] = (
            held.get(proposal.instrument_id, 0) + sign * proposal.quantity
        )
        price[proposal.instrument_id] = proposal.price
        cash -= sign * proposal.amount_inr
    cash = round(cash, 2)
    values = {k: round(q * price[k], 2) for k, q in held.items() if q > 0}
    total = sum(values.values()) + cash
    result = [
        PaperPosition(
            instrument_id=k,
            quantity=held[k],
            price=price[k],
            value=values[k],
            weight=values[k] / total if total > 0 else 0.0,
        )
        for k in sorted(values)
    ]
    return result, cash


def _with_risk(
    plan: PaperPlan,
    start_positions: list[PaperPosition],
    start_cash: float,
    observations: list[MarketObservation],
    portfolio_rules: dict,
    as_of: datetime,
) -> PaperPlan:
    """Attach risk verdicts; holdings then reflect only the proposals that passed."""
    verdicts = check(
        plan.proposals, start_positions, start_cash, observations, portfolio_rules, as_of
    )
    warnings = list(plan.warnings)
    positions, cash = plan.positions, plan.cash_inr
    blocked = [v for v in verdicts if v.verdict == "BLOCK"]
    if blocked:
        passed = [p for p, v in zip(plan.proposals, verdicts) if v.verdict == "PASS"]
        prices = {k: q.close for k, q in latest_quotes(observations, as_of).items()}
        positions, cash = _apply(start_positions, start_cash, passed, prices)
        warnings.append(
            f"{len(blocked)} of {len(verdicts)} paper proposals blocked by risk limits; "
            "positions and cash include only the proposals that passed"
        )
    return plan.model_copy(
        update={
            "verdicts": verdicts,
            "positions": positions,
            "cash_inr": cash,
            "warnings": warnings,
        }
    )


def build_screen(storage, rules_root: Path, as_of: datetime) -> ScreenResult:
    """Screen the latest cutoff-safe assessment per company with default screener rules."""
    return _screen(storage, load_screener_rules(Path(rules_root)), utc(as_of))


def build_plan(
    storage, rules_root: Path, as_of: datetime, budget_inr: float | None = None
) -> PaperPlan:
    """Screen -> size -> risk. An empty shortlist gives an empty plan with a warning."""
    cutoff = utc(as_of)
    screener_rules = load_screener_rules(Path(rules_root))
    portfolio_rules = load_portfolio_rules(Path(rules_root))
    if budget_inr is not None:
        portfolio_rules = {**portfolio_rules, "budget_inr": budget_inr}
    result = _screen(storage, screener_rules, cutoff)
    scores = {
        row.instrument_id: row.score for row in result.rows if row.instrument_id in result.shortlist
    }
    observations = storage.list_observations()
    plan = size(scores, observations, portfolio_rules, cutoff)
    plan = plan.model_copy(
        update={
            "rules_version": _versions(screener_rules, portfolio_rules),
            "warnings": _screen_warnings(result) + plan.warnings,
        }
    )
    return _with_risk(plan, [], plan.budget_inr, observations, portfolio_rules, cutoff)


def _holdings(positions) -> dict[str, int]:
    """Instrument -> whole-share quantity from PaperPositions or {instrument_id, quantity} rows."""
    held: dict[str, int] = {}
    for row in positions:
        if isinstance(row, PaperPosition):
            instrument, quantity = row.instrument_id, row.quantity
        elif isinstance(row, Mapping):
            instrument, quantity = row.get("instrument_id"), row.get("quantity")
        else:
            raise ValueError("Each position needs instrument_id and quantity")
        if not isinstance(instrument, str) or not instrument.strip():
            raise ValueError("Each position needs a nonempty instrument_id")
        if type(quantity) is not int or quantity < 0:
            raise ValueError(f"Quantity for {instrument} must be a whole number of shares >= 0")
        if instrument in held:
            raise ValueError(f"Position {instrument} is listed more than once")
        if quantity:
            held[instrument] = quantity
    return held


def _value(held: dict[str, int], cash_inr: float, observations, as_of) -> list[PaperPosition]:
    quotes = latest_quotes(observations, as_of)
    missing = sorted(set(held) - set(quotes))
    if missing:
        raise ValueError(
            f"No cutoff-safe price at or before {as_of.isoformat()} for: {', '.join(missing)}"
        )
    values = {k: round(q * quotes[k].close, 2) for k, q in held.items()}
    total = sum(values.values()) + cash_inr
    return [
        PaperPosition(
            instrument_id=k,
            quantity=held[k],
            price=quotes[k].close,
            value=values[k],
            weight=values[k] / total if total > 0 else 0.0,
        )
        for k in sorted(held)
    ]


def build_rebalance(
    storage, rules_root: Path, positions: Iterable, cash_inr: float, as_of: datetime
) -> PaperPlan:
    """Rebalance paper holdings toward a fresh plan's weights, then risk-check the trades."""
    cutoff = utc(as_of)
    if (
        isinstance(cash_inr, bool)
        or not isinstance(cash_inr, (int, float))
        or not (0 <= cash_inr < float("inf"))
    ):
        raise ValueError("Cash must be a finite number >= 0")
    screener_rules = load_screener_rules(Path(rules_root))
    portfolio_rules = load_portfolio_rules(Path(rules_root))
    observations = storage.list_observations()
    start = _value(_holdings(positions), float(cash_inr), observations, cutoff)
    target_plan = build_plan(storage, rules_root, cutoff)
    targets = {p.instrument_id: p.weight for p in target_plan.positions if p.quantity}
    warnings = [f"Targets: {warning}" for warning in target_plan.warnings]
    if not targets:
        warnings.append("No target weights: every paper holding is proposed for sale")
    plan = rebalance(start, float(cash_inr), targets, observations, portfolio_rules, cutoff)
    plan = plan.model_copy(
        update={
            "rules_version": _versions(screener_rules, portfolio_rules),
            "warnings": warnings + plan.warnings,
        }
    )
    return _with_risk(plan, start, float(cash_inr), observations, portfolio_rules, cutoff)


def check_plan(storage, rules_root: Path, plan: PaperPlan) -> PaperPlan:
    """Re-run risk limits on a saved plan's proposals from its reconstructed starting state.

    A proposal counts as already applied when it has a PASS verdict at the same position (or
    when the plan carries no verdicts at all); later, unchecked proposals were never applied.
    """
    portfolio_rules = load_portfolio_rules(Path(rules_root))
    if plan.verdicts and any(
        v.proposal_id != p.proposal_id for p, v in zip(plan.proposals, plan.verdicts)
    ):
        raise ValueError("Plan verdicts do not line up with its proposals")
    if len(plan.verdicts) > len(plan.proposals):
        raise ValueError("Plan has more verdicts than proposals")
    applied = [
        p
        for index, p in enumerate(plan.proposals)
        if not plan.verdicts
        or (index < len(plan.verdicts) and plan.verdicts[index].verdict == "PASS")
    ]
    held = {p.instrument_id: p.quantity for p in plan.positions}
    cash = plan.cash_inr
    for proposal in applied:
        sign = 1 if proposal.side == "buy" else -1
        held[proposal.instrument_id] = (
            held.get(proposal.instrument_id, 0) - sign * proposal.quantity
        )
        cash += sign * proposal.amount_inr
    if any(q < 0 for q in held.values()) or cash < -0.005:
        raise ValueError("Plan positions, cash and proposals are inconsistent")
    cash = round(cash, 2)
    observations = storage.list_observations()
    start = _value({k: q for k, q in held.items() if q}, cash, observations, plan.as_of)
    warnings = list(plan.warnings)
    if portfolio_rules["version"] not in plan.rules_version.split("+"):
        warnings.append(
            f"Re-checked with portfolio rules {portfolio_rules['version']}; "
            f"plan was built with {plan.rules_version}"
        )
    # Assume every proposal fills; _with_risk rebuilds holdings if any is now blocked.
    positions, after = _apply(start, cash, plan.proposals, {})
    unchecked = plan.model_copy(
        update={"verdicts": [], "positions": positions, "cash_inr": after, "warnings": warnings}
    )
    return _with_risk(unchecked, start, cash, observations, portfolio_rules, plan.as_of)


# ---------------------------------------------------------------------------
# Saving and printing
# ---------------------------------------------------------------------------


def save_plan(plan: PaperPlan, root: Path) -> Path:
    """Write the plan to runs/paper/<as_of>-<hash>.json under root and return the path."""
    text = plan.model_dump_json(indent=2)
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    folder = Path(root) / "runs" / "paper"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{plan.as_of:%Y%m%dT%H%M%SZ}-{digest}.json"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def load_plan(path: Path) -> PaperPlan:
    """Read a saved plan file."""
    return PaperPlan.model_validate_json(Path(path).read_text(encoding="utf-8"))


def to_json(record) -> str:
    """ASCII-safe JSON for any paper record (safe on every console encoding)."""
    return json.dumps(record.model_dump(mode="json"), indent=2)


def _when(value: datetime) -> str:
    return f"{value.astimezone(IST):%Y-%m-%d %H:%M} IST"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    widths = [max(len(str(c)) for c in column) for column in zip(header, *rows)]
    return [
        "  ".join(str(cell).ljust(width) for cell, width in zip(line, widths)).rstrip()
        for line in [header, *rows]
    ]


def _failed_check(check: dict) -> str:
    value = check.get("value")
    if value is None:
        return check["rule"]
    shown = f"{value:.4g}" if isinstance(value, (int, float)) else str(value)
    return f"{check['rule']} (was {shown})"


def screen_table(result: ScreenResult) -> str:
    """Readable screener table: rank, company, PASS/FAIL, score and the failed checks."""
    rows = []
    for row in result.rows:
        failed = "; ".join(_failed_check(check) for check in row.checks if not check["passed"])
        rows.append(
            [
                str(row.rank or "-"),
                row.company_id,
                "PASS" if row.passed else "FAIL",
                "-" if row.score is None else f"{row.score:.3f}",
                failed or "-",
            ]
        )
    lines = [f"Paper screen at {_when(result.as_of)} (rules {result.rules_version})", ""]
    lines += (
        _table(["Rank", "Company", "Result", "Score", "Failed checks"], rows)
        if rows
        else ["No assessed runs at or before this cutoff."]
    )
    lines += ["", f"Shortlist: {', '.join(result.shortlist) or 'none'}", PAPER_LABEL]
    return "\n".join(lines)


def plan_table(plan: PaperPlan) -> str:
    """Readable plan: trades with risk verdicts, resulting holdings, cash and warnings."""
    verdicts = {index: v for index, v in enumerate(plan.verdicts)}
    trades = []
    for index, p in enumerate(plan.proposals):
        verdict = verdicts.get(index)
        trades.append(
            [
                p.side,
                p.instrument_id,
                str(p.quantity),
                f"{p.price:,.2f}",
                f"{p.amount_inr:,.2f}",
                verdict.verdict if verdict else "unchecked",
                "; ".join(verdict.reasons) if verdict and verdict.reasons else "-",
            ]
        )
    held = [
        [p.instrument_id, str(p.quantity), f"{p.price:,.2f}", f"{p.value:,.2f}", f"{p.weight:.1%}"]
        for p in plan.positions
    ]
    lines = [
        f"Paper plan at {_when(plan.as_of)} (rules {plan.rules_version})",
        f"Budget INR {plan.budget_inr:,.2f}; cash after plan INR {plan.cash_inr:,.2f}",
        "",
        "Proposals:",
    ]
    lines += (
        _table(["Side", "Instrument", "Qty", "Price INR", "Amount INR", "Risk", "Reasons"], trades)
        if trades
        else ["  none"]
    )
    lines += ["", "Resulting paper positions:"]
    lines += (
        _table(["Instrument", "Qty", "Price INR", "Value INR", "Weight"], held)
        if held
        else ["  none"]
    )
    if plan.warnings:
        lines += [""] + [f"Warning: {warning}" for warning in plan.warnings]
    lines += ["", plan.label]
    return "\n".join(lines)
