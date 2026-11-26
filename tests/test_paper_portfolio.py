"""Paper portfolio orchestrator end-to-end: screen -> size -> risk, and rebalance -> risk.

Offline and synthetic only (tests/fixtures/paper_portfolio.json). Nothing here places orders.
"""

import json
import shutil
import socket
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from market_events.paper_portfolio import (
    build_plan,
    build_rebalance,
    build_screen,
    check_plan,
    load_plan,
    save_plan,
    scoped,
)
from market_events.schemas import (
    PAPER_LABEL,
    AnalysisRun,
    Article,
    Assessment,
    EventExtraction,
    ExecutionPolicy,
    MarketObservation,
    PaperPlan,
)
from market_events.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/paper_portfolio.json").read_text(encoding="utf-8"))
AS_OF = datetime.fromisoformat(FIXTURE["as_of"])
LATER = datetime.fromisoformat(FIXTURE["later_as_of"])
EXPECTED = FIXTURE["expected_plan"]
AAA, BBB, CCC, DDD, EEE = (f"SYNTHETIC:NSE:{name}" for name in ("AAA", "BBB", "CCC", "DDD", "EEE"))


def bar(instrument_id, timestamp, available_at, close):
    """One synthetic daily bar with a small, valid high/low range."""
    return MarketObservation(
        instrument_id=instrument_id,
        market_family="equity",
        timestamp=timestamp,
        available_at=available_at,
        open=close,
        high=close * 1.005,
        low=close * 0.995,
        close=close,
        volume=1000,
        currency="INR",
        unit="share",
    )


def fixture_observations():
    """Every fixture bar, including the ones after the default cutoff."""
    close_time = time.fromisoformat(FIXTURE["close_time_utc"])
    delay = timedelta(minutes=FIXTURE["available_after_minutes"])
    rows = []
    for instrument_id, closes in FIXTURE["series"].items():
        for session, close in zip(FIXTURE["sessions"], closes):
            stamp = datetime.combine(
                datetime.fromisoformat(session).date(), close_time, tzinfo=timezone.utc
            )
            rows.append(bar(instrument_id, stamp, stamp + delay, close))
    for extra in FIXTURE["extra_bars"]:
        rows.append(
            bar(
                extra["instrument_id"],
                datetime.fromisoformat(extra["timestamp"]),
                datetime.fromisoformat(extra["available_at"]),
                extra["close"],
            )
        )
    return rows


def fixture_runs():
    """Saved-run shaped records (article + extraction + assessment) for every fixture run."""
    pairs = []
    for row in FIXTURE["runs"]:
        when = datetime.fromisoformat(row["decision_time"])
        suffix = row["run_id"].rsplit(":", 1)[-1]
        article = Article(
            article_id=f"SYNTHETIC:ART:{suffix}",
            source_url=f"https://fixtures.invalid/paper/{suffix}",
            text=f"SYNTHETIC paper-portfolio fixture article {suffix}.",
            published_at=when - timedelta(hours=1),
            first_seen_at=when - timedelta(minutes=55),
        )
        run = AnalysisRun(
            run_id=row["run_id"],
            article_id=article.article_id,
            event_id=f"SYNTHETIC:EVT:{suffix}",
            policy=ExecutionPolicy.slm_delegate,
            decision_time=when,
            status="abstained" if row["direction"] == "abstain" else "completed",
            created_at=when,
            config_snapshot={"fixture": "paper_portfolio"},
            extraction=EventExtraction(
                event_id=f"SYNTHETIC:EVT:{suffix}",
                event_type="earnings",
                company_id=row["company_id"],
                direction="uncertain" if row["direction"] == "abstain" else row["direction"],
            ),
            assessment=Assessment(
                direction=row["direction"],
                evidence_score=row["evidence_score"],
                coverage=row["coverage"],
                abstention_reasons=row["abstention_reasons"],
                rules_version="fusion-fixture",
                explanation="SYNTHETIC fixture assessment",
            ),
            mode="replay",
        )
        pairs.append((article, run))
    return pairs


def load_paper_fixture(database: Path) -> Path:
    """Write the synthetic fixture into a fresh ledger and return its path."""
    with Storage(database) as storage:
        storage.add_observations(fixture_observations())
        pairs = fixture_runs()
        storage.add_articles(article for article, _ in pairs)
        for _, run in pairs:
            storage.save_run(run)
    return database


def rules_root(tmp_path: Path) -> Path:
    """A root holding the repository's real default paper configs."""
    (tmp_path / "configs").mkdir(exist_ok=True)
    for name in ("screener_rules.json", "portfolio_rules.json"):
        shutil.copy(ROOT / "configs" / name, tmp_path / "configs" / name)
    return tmp_path


@pytest.fixture
def ledger(tmp_path):
    root = rules_root(tmp_path)
    database = load_paper_fixture(tmp_path / "data/paper.sqlite")
    with Storage(database) as storage:
        yield storage, root


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any socket use fails the test: the paper layer reads only the local ledger."""

    def forbidden(*args, **kwargs):
        raise AssertionError("paper portfolio must never open a network connection")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def quantities(plan):
    return {p.instrument_id: p.quantity for p in plan.positions if p.quantity}


# ---------------------------------------------------------------------------
# screen -> size -> risk
# ---------------------------------------------------------------------------


def test_fixture_plan_reproduces_the_sizing_worked_example(ledger):
    storage, root = ledger
    plan = build_plan(storage, root, AS_OF)

    assert isinstance(plan, PaperPlan)
    assert quantities(plan) == EXPECTED["quantities"]
    assert plan.cash_inr == pytest.approx(EXPECTED["cash_inr"], abs=0.005)
    spent = sum(p.amount_inr for p in plan.proposals)
    assert spent == pytest.approx(EXPECTED["spent_inr"], abs=0.005)
    assert spent + plan.cash_inr == pytest.approx(plan.budget_inr, abs=0.005)
    assert [p.side for p in plan.proposals] == ["buy"] * 4
    assert {v.verdict for v in plan.verdicts} == {"PASS"}
    assert [v.proposal_id for v in plan.verdicts] == [p.proposal_id for p in plan.proposals]


def test_plan_carries_both_config_versions_and_the_research_label(ledger):
    storage, root = ledger
    plan = build_plan(storage, root, AS_OF)

    assert "screener-v1" in plan.rules_version and "portfolio-v1" in plan.rules_version
    assert plan.label == PAPER_LABEL
    assert all(p.label == PAPER_LABEL for p in plan.proposals)


def test_screen_shortlist_and_failure_reasons(ledger):
    storage, root = ledger
    result = build_screen(storage, root, AS_OF)

    assert result.shortlist == EXPECTED["shortlist"]
    rows = {row.company_id: row for row in result.rows}
    # HHH only has a run after the cutoff, so it is not screened at all.
    assert "SYNTHETIC:NSE:HHH" not in rows
    for company, reason in EXPECTED["failed"].items():
        assert not rows[company].passed
        failing = [check["rule"] for check in rows[company].checks if not check["passed"]]
        assert any(reason in str(rule) for rule in failing), (company, rows[company].checks)


def test_later_prices_and_later_runs_are_ignored(ledger):
    storage, root = ledger
    plan = build_plan(storage, root, AS_OF)
    prices = {p.instrument_id: p.price for p in plan.proposals}
    # The 2020-12-31 bar (close 3000) is not yet available at 15:30 IST; 2021 bars are later.
    assert prices[AAA] == 1450
    rows = {row.company_id: row for row in build_screen(storage, root, AS_OF).rows}
    assert rows[AAA].run_id == "SYNTHETIC:RUN:AAA-1"

    later = build_screen(storage, root, LATER)
    later_rows = {row.company_id: row for row in later.rows}
    assert later_rows[AAA].run_id == "SYNTHETIC:RUN:AAA-LATE"
    assert AAA not in later.shortlist


def test_plan_is_deterministic(ledger, tmp_path):
    storage, root = ledger
    first = build_plan(storage, root, AS_OF)
    second = build_plan(storage, root, AS_OF)
    with Storage(load_paper_fixture(tmp_path / "data/copy.sqlite")) as other:
        third = build_plan(other, root, AS_OF)

    ids = [p.proposal_id for p in first.proposals]
    assert ids and ids == [p.proposal_id for p in second.proposals]
    assert ids == [p.proposal_id for p in third.proposals]
    assert first.model_dump_json() == third.model_dump_json()


def test_budget_override_scales_the_plan(ledger):
    storage, root = ledger
    plan = build_plan(storage, root, AS_OF, budget_inr=50000)

    assert plan.budget_inr == 50000
    assert sum(p.amount_inr for p in plan.proposals) + plan.cash_inr == pytest.approx(50000)
    assert plan.cash_inr >= 5000 - 0.005


def test_demo_database_as_of_2020_gives_an_empty_plan_with_a_warning(tmp_path):
    from market_events.pipeline import run_demo

    database = tmp_path / "demo.sqlite"
    run_demo(ROOT, database)
    with Storage(database) as storage:
        plan = build_plan(storage, ROOT, datetime.fromisoformat("2020-12-31T15:30:00+05:30"))

    assert plan.proposals == [] and plan.verdicts == [] and plan.positions == []
    assert plan.cash_inr == plan.budget_inr
    assert plan.warnings, "an empty plan must explain itself"
    assert any("2020-12-31" in warning or "as_of" in warning for warning in plan.warnings)


def test_naive_as_of_is_rejected(ledger):
    storage, root = ledger
    with pytest.raises(ValueError):
        build_plan(storage, root, datetime(2020, 12, 31, 15, 30))


# ---------------------------------------------------------------------------
# rebalance -> risk
# ---------------------------------------------------------------------------


def test_rebalance_brings_holdings_back_to_the_fresh_plan(ledger):
    storage, root = ledger
    holdings = [{"instrument_id": AAA, "quantity": 40}, {"instrument_id": BBB, "quantity": 40}]
    plan = build_rebalance(storage, root, holdings, 9200, AS_OF)

    sides = [p.side for p in plan.proposals]
    assert sides == sorted(sides, key=lambda side: side != "sell"), "sells come first"
    assert {v.verdict for v in plan.verdicts} == {"PASS"}
    # Hand-worked: sell AAA 23 and BBB 10, then buy CCC 10 and DDD 42 (buffer kept).
    trades = {(p.instrument_id, p.side): p.quantity for p in plan.proposals}
    assert trades == {(AAA, "sell"): 23, (BBB, "sell"): 10, (CCC, "buy"): 10, (DDD, "buy"): 42}
    assert quantities(plan) == EXPECTED["quantities"]
    assert plan.cash_inr == pytest.approx(10220, abs=0.005)
    total = sum(p.value for p in plan.positions) + plan.cash_inr
    assert total == pytest.approx(58000 + 32800 + 9200, abs=0.005)
    assert "screener-v1" in plan.rules_version and "portfolio-v1" in plan.rules_version


def test_rebalance_sells_names_not_in_targets(ledger):
    storage, root = ledger
    holdings = [{"instrument_id": EEE, "quantity": 10}]
    plan = build_rebalance(storage, root, holdings, 100000, AS_OF)

    sells = [p for p in plan.proposals if p.instrument_id == EEE]
    assert len(sells) == 1 and sells[0].side == "sell" and sells[0].quantity == 10
    assert "not in targets" in sells[0].reason


def test_rebalance_rejects_holdings_without_a_cutoff_safe_price(ledger):
    storage, root = ledger
    with pytest.raises(ValueError, match="SYNTHETIC:NSE:ZZZ"):
        build_rebalance(
            storage, root, [{"instrument_id": "SYNTHETIC:NSE:ZZZ", "quantity": 1}], 1000, AS_OF
        )


# ---------------------------------------------------------------------------
# saving, reloading and re-checking a plan
# ---------------------------------------------------------------------------


def test_saved_plan_round_trips_and_rechecks_identically(ledger):
    storage, root = ledger
    plan = build_plan(storage, root, AS_OF)
    path = save_plan(plan, root)

    assert path.parent == root / "runs" / "paper"
    assert path.name.startswith("20201231T100000Z-") and path.suffix == ".json"
    assert save_plan(plan, root) == path, "same plan, same file name"
    loaded = load_plan(path)
    assert loaded == plan
    rechecked = check_plan(storage, root, loaded)
    assert rechecked.verdicts == plan.verdicts
    assert quantities(rechecked) == quantities(plan)
    assert rechecked.cash_inr == pytest.approx(plan.cash_inr)


def test_blocked_buys_are_left_out_of_positions_and_survive_a_recheck(ledger):
    storage, root = ledger
    # A 3,00,000 budget gives 25% slices of about 75,000: above max_order_inr (50,000).
    plan = build_plan(storage, root, AS_OF, budget_inr=300000)
    verdicts = {p.instrument_id: v for p, v in zip(plan.proposals, plan.verdicts)}

    assert {k for k, v in verdicts.items() if v.verdict == "PASS"} == {DDD}
    assert all("max_order_inr" in " ".join(verdicts[k].reasons) for k in (AAA, BBB, CCC))
    assert quantities(plan) == {DDD: 120}
    assert plan.cash_inr == pytest.approx(300000 - 120 * 415, abs=0.005)
    assert any("blocked by risk" in warning for warning in plan.warnings)

    rechecked = check_plan(storage, root, load_plan(save_plan(plan, root)))
    assert rechecked.verdicts == plan.verdicts
    assert quantities(rechecked) == {DDD: 120}
    assert rechecked.cash_inr == pytest.approx(plan.cash_inr, abs=0.005)


def test_recheck_blocks_a_tampered_plan(ledger):
    storage, root = ledger
    plan = build_plan(storage, root, AS_OF)
    # Duplicate the first proposal: the copy shares its proposal_id, so risk must block it.
    tampered = plan.model_copy(update={"proposals": [*plan.proposals, plan.proposals[0]]})
    rechecked = check_plan(storage, root, tampered)

    assert rechecked.verdicts[-1].verdict == "BLOCK"
    assert any("duplicate" in reason for reason in rechecked.verdicts[-1].reasons)


def test_scoped_view_separates_synthetic_and_live_records(ledger):
    storage, _ = ledger
    assert scoped(storage, "live").list_runs() == []
    assert scoped(storage, "live").list_observations() == []
    assert len(scoped(storage, "demo").list_runs()) == len(FIXTURE["runs"])
