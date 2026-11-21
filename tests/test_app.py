"""Offline UI guards: opening the page must not create a demo or database."""

from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys
from types import ModuleType

import pytest
from streamlit.testing.v1 import AppTest

from app import parse_cutoff

APP = Path(__file__).resolve().parent.parent / "app.py"


def test_cutoff_requires_offset_and_normalizes_ist():
    assert parse_cutoff("2026-01-12T17:30:00+05:30").isoformat() == "2026-01-12T12:00:00+00:00"
    with pytest.raises(ValueError, match="timezone"):
        parse_cutoff("2026-01-12T17:30:00")


def test_page_open_never_creates_database(tmp_path, monkeypatch):
    # Load pipeline before patching so its imported Storage reference stays real
    # for subsequent AppTest sessions in this same Python process.
    import market_events.pipeline  # noqa: F401
    import market_events.storage

    def unexpected_storage(*args, **kwargs):
        raise AssertionError("Page opening must not instantiate storage")

    monkeypatch.setattr(market_events.storage, "Storage", unexpected_storage)
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert not app.error
    assert not (tmp_path / "data").exists()
    assert any("Load synthetic demo" in button.label for button in app.button)
    assert app.radio[0].value == "replay"


def test_strategy_lab_navigation_preserves_existing_evidence(tmp_path, monkeypatch):
    """The integrated route renders without silently analysing or fetching data."""
    import market_events.live_data
    import market_events.pipeline
    from market_events.storage import Storage

    app = AppTest.from_file(str(APP), default_timeout=20).run()
    database = tmp_path / "lab.sqlite"
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(database)
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    with Storage(database) as storage:
        before = (len(storage.list_runs()), len(storage.list_observations()))

    def forbidden(*args, **kwargs):
        raise AssertionError("Navigation must never fetch data or analyse an article")

    monkeypatch.setattr(market_events.live_data, "sync_live", forbidden)
    monkeypatch.setattr(market_events.live_data, "sync_historical", forbidden)
    monkeypatch.setattr(market_events.pipeline, "analyse_article", forbidden)
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Strategy lab"
    ).run()
    assert not app.exception
    assert not app.error
    assert any("2020" in str(item.value) for item in app.caption)
    with Storage(database) as storage:
        assert (len(storage.list_runs()), len(storage.list_observations())) == before


def test_explicit_demo_and_saved_views(tmp_path):
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(tmp_path / "demo.sqlite")
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    assert not app.exception
    assert not app.error
    assert (tmp_path / "demo.sqlite").exists()
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Saved runs"
    ).run()
    assert not app.exception
    assert not app.error
    from market_events.storage import Storage

    with Storage(tmp_path / "demo.sqlite") as storage:
        assessed = next(run for run in storage.list_runs() if run.assessment is not None)
        original_count = len(storage.list_runs())
    next(select for select in app.selectbox if select.label == "Saved run").set_value(
        assessed.run_id
    ).run()
    assert any("Evidence score" in metric.label for metric in app.metric)
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Comparisons"
    ).run()
    assert not app.exception
    assert not app.error
    assert len(app.dataframe) >= 3
    with Storage(tmp_path / "demo.sqlite") as storage:
        assert len(storage.list_runs()) == original_count


def test_repeat_requires_submit_and_filters_watchlist_do_not_analyse(tmp_path, monkeypatch):
    import market_events.pipeline

    calls = []

    def analyse(article_id, decision, policy, dependencies, **kwargs):
        calls.append(kwargs)
        return dependencies.storage.list_runs()[0]

    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(tmp_path / "demo.sqlite")
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    monkeypatch.setattr(market_events.pipeline, "analyse_article", analyse)
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Research"
    ).run()
    assert not app.checkbox[0].value
    next(button for button in app.button if button.label == "Analyse and save run").click().run()
    assert calls == [{}]
    app.checkbox[0].check().run()
    assert calls == [{}]
    # Form values are batched with the submit, rather than an unrelated rerun.
    app.checkbox[0].check()
    next(button for button in app.button if button.label == "Analyse and save run").click().run()
    assert calls == [{}, {"repeat_run": True}]
    next(field for field in app.selectbox if field.label == "Inbox status").set_value(
        "completed"
    ).run()
    assert all(row == "Analysis saved" for row in app.dataframe[0].value["status"])
    assert calls == [{}, {"repeat_run": True}]
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value("Import").run()
    assert not app.exception
    app.multiselect[0].set_value(["NSE:ASIANPAINT"]).run()
    assert list(app.dataframe[0].value["company"]) == ["NSE:ASIANPAINT"]
    assert calls == [{}, {"repeat_run": True}]


def test_optional_explanation_failure_keeps_deterministic_result(tmp_path, monkeypatch):
    import market_events.pipeline
    from market_events.storage import Storage

    calls = []

    def explain(run_id, dependencies):
        calls.append(run_id)
        raise ValueError("Offline provider")

    monkeypatch.setattr(market_events.pipeline, "explain_run", explain)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    path = tmp_path / "demo.sqlite"
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(path)
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    with Storage(path) as storage:
        assessed = next(run for run in storage.list_runs() if run.assessment is not None)
        before = assessed.model_dump_json()
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Saved runs"
    ).run()
    next(select for select in app.selectbox if select.label == "Saved run").set_value(
        assessed.run_id
    ).run()
    assert calls == []
    next(
        button for button in app.button if button.label == "Request optional explanation"
    ).click().run()
    assert calls == [assessed.run_id]
    assert not app.exception
    assert any("saved deterministic explanation" in item.value for item in app.warning)
    assert any(item.value == assessed.assessment.explanation for item in app.markdown)
    with Storage(path) as storage:
        assert storage.get_run(assessed.run_id).model_dump_json() == before


def test_comparison_outcomes_require_explicit_action(tmp_path, monkeypatch):
    import market_events.pipeline
    from market_events.storage import Storage

    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(tmp_path / "demo.sqlite")
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    calls = []
    monkeypatch.setattr(
        market_events.pipeline, "compute_outcomes", lambda dependencies: calls.append(True) or []
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only interaction must not write saved evidence")

    for name in ("save_run", "save_outcome", "add_articles", "add_observations"):
        monkeypatch.setattr(Storage, name, forbidden)
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Comparisons"
    ).run()
    app.run()
    assert calls == []
    assert not app.exception
    assert not app.error
    next(button for button in app.button if button.label == "Evaluate later outcomes").click().run()
    assert calls == [True]
    app.run()
    assert calls == [True]


def test_root_change_requires_workspace_open_even_with_same_absolute_database(tmp_path):
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(tmp_path / "demo.sqlite")
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    next(field for field in app.text_input if field.label == "Project root").set_value(
        str(tmp_path / "other-root")
    ).run()
    assert not app.exception
    assert not app.error
    assert not any(radio.label == "Workbench view" for radio in app.radio)
    assert any("Open a workspace" in item.value for item in app.info)
    assert not (tmp_path / "other-root").exists()


def test_persisted_explanation_renders_after_reload_without_changing_inbox_status(tmp_path):
    from market_events.storage import Storage

    app = AppTest.from_file(str(APP), default_timeout=20).run()
    path = tmp_path / "demo.sqlite"
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(path)
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    with Storage(path) as storage:
        assessed = next(run for run in storage.list_runs() if run.assessment is not None)
        child = assessed.model_copy(deep=True)
        child.run_id = "explanation-child"
        child.created_at = child.created_at.replace(year=2027)
        child.parent_run_id = assessed.run_id
        child.status = "explanation_completed"
        child.calls = []
        child.request_key = None
        child.config_snapshot["explanation_parent_run_id"] = assessed.run_id
        child.config_snapshot["explanation_result"] = {
            "text": "Persisted grounded explanation.",
            "source_spans": assessed.extraction.source_spans,
        }
        storage.save_run(child)
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Research"
    ).run()
    assert "explanation_completed" not in list(app.dataframe[0].value["status"])
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Saved runs"
    ).run()
    next(select for select in app.selectbox if select.label == "Saved run").set_value(
        child.run_id
    ).run()
    assert not app.exception
    assert any(item.value == "Persisted grounded explanation." for item in app.markdown)
    assert any("inherited" in item.value for item in app.info)
    assert any("Referenced market observations" == item.value for item in app.markdown)
    app.run()
    assert any(item.value == "Persisted grounded explanation." for item in app.markdown)


def test_analysis_requires_valid_cutoff_and_offers_saved_result_navigation(tmp_path, monkeypatch):
    import market_events.pipeline
    from market_events.storage import Storage

    app = AppTest.from_file(str(APP), default_timeout=20).run()
    path = tmp_path / "demo.sqlite"
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(path)
    )
    next(button for button in app.button if "Load synthetic demo" in button.label).click().run()
    with Storage(path) as storage:
        run = next(item for item in storage.list_runs() if item.assessment is not None)
    calls = []
    monkeypatch.setattr(
        market_events.pipeline, "analyse_article", lambda *args, **kwargs: calls.append(args) or run
    )
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Research"
    ).run()
    cutoff = next(field for field in app.text_input if field.label.startswith("Decision cutoff"))
    cutoff.set_value("2026-01-12T17:30:00")
    next(button for button in app.button if button.label == "Analyse and save run").click().run()
    assert calls == []
    assert app.error
    next(field for field in app.text_input if field.label.startswith("Decision cutoff")).set_value(
        "2026-01-12T17:30:00+05:30"
    )
    next(button for button in app.button if button.label == "Analyse and save run").click().run()
    assert len(calls) == 1
    next(button for button in app.button if button.label == "Open saved result").click().run()
    assert (
        next(select for select in app.selectbox if select.label == "Saved run").value == run.run_id
    )
    assert (
        next(metric for metric in app.metric if metric.label == "Evidence coverage").value
        == f"{run.assessment.coverage:.0%}"
    )
    assert len(calls) == 1
    assert not app.exception


def test_price_indicators_work_without_articles_models_or_network_and_only_on_compute(
    tmp_path, monkeypatch
):
    import market_events.pipeline
    import market_events.technicals
    from market_events.schemas import MarketObservation
    from market_events.storage import Storage

    path = tmp_path / "prices.sqlite"
    today = datetime.now(timezone.utc).replace(microsecond=0)
    bars = [
        MarketObservation(
            instrument_id="LOCAL:TEST",
            market_family="equity",
            timestamp=today - timedelta(days=60 - i),
            available_at=today - timedelta(days=60 - i),
            open=100 + i,
            high=102 + i,
            low=99 + i,
            close=101 + i,
            volume=100,
            currency="INR",
            unit="share",
        )
        for i in range(60)
    ]
    future = MarketObservation(
        instrument_id="LOCAL:TEST",
        market_family="equity",
        timestamp=today + timedelta(days=1),
        available_at=today + timedelta(days=1),
        open=500,
        high=510,
        low=490,
        close=500,
        volume=100,
        currency="INR",
        unit="share",
    )
    benchmark = bars[0].model_copy(
        update={"observation_id": "", "instrument_id": "LOCAL:BENCH", "market_family": "benchmark"}
    )
    benchmark = MarketObservation.model_validate(benchmark.model_dump())
    with Storage(path) as storage:
        storage.add_observations([*bars, future, benchmark])
    actual = market_events.technicals.compute_technicals
    snapshots = []

    def compute(*args):
        result = actual(*args)
        snapshots.append(result)
        return result

    def forbidden(*args, **kwargs):
        raise AssertionError("Technical views must not call a model or write a run")

    monkeypatch.setattr(market_events.technicals, "compute_technicals", compute)
    monkeypatch.setattr(market_events.pipeline, "analyse_article", forbidden)
    monkeypatch.setattr(market_events.pipeline, "explain_run", forbidden)
    monkeypatch.setattr(Storage, "save_run", forbidden)
    monkeypatch.setenv("SLM_MODEL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(path)
    )
    next(button for button in app.button if button.label == "Open workspace").click().run()
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Technicals"
    ).run()
    assert next(
        select for select in app.selectbox if select.label == "Price history company"
    ).options == ["LOCAL:TEST · LOCAL:TEST"]
    assert snapshots == []
    next(
        button for button in app.button if button.label == "Compute price indicators"
    ).click().run()
    assert not app.exception
    assert not app.error
    assert len(snapshots) == 1
    assert snapshots[0].history_bars == 60
    assert snapshots[0].values["rsi14"] == 100
    assert future.observation_id not in snapshots[0].observation_ids
    assert (
        next(metric for metric in app.metric if metric.label == "RSI · 14 sessions").value
        == "100.00"
    )
    app.run()
    assert len(snapshots) == 1
    with Storage(path) as storage:
        assert storage.list_articles() == []
        assert storage.list_runs() == []


def test_connections_only_sync_or_analyse_on_explicit_submit_and_clear_universe_context(
    tmp_path, monkeypatch
):
    import market_events.pipeline

    companies = [
        {"instrument_id": "LIVE:NSE:TEST", "name": "Test company", "market_family": "equity"},
        {"instrument_id": "LIVE:NSE:BENCH", "name": "Test benchmark", "market_family": "benchmark"},
    ]
    sync_calls, batch_calls = [], []
    stamp = datetime.now(timezone.utc).isoformat()
    report = {
        "provider": "Test adapter",
        "fetched_at": stamp,
        "decision_time": stamp,
        "requested_company_ids": ["LIVE:NSE:TEST"],
        "observations_added": 1,
        "articles_added": 1,
        "article_ids": ["LIVE:NEWS:TEST"],
        "errors": [],
        "warnings": [],
        "network_requests": 1,
        "data_source": "mocked UI workflow",
        "universe": companies,
    }

    def sync(dependencies, ids, **kwargs):
        sync_calls.append((ids, kwargs))
        return report

    def batch(dependencies, ids, cutoff, **kwargs):
        batch_calls.append((ids, cutoff, kwargs))
        return [{"article_id": ids[0], "run_id": "test-run", "status": "completed", "error": None}]

    # Mock only the public adapter boundary; no HTTP or model method is reachable.
    adapter = ModuleType("market_events.live_data")
    adapter.get_live_universe = lambda source: companies
    adapter.sync_live = sync
    monkeypatch.setitem(sys.modules, "market_events.live_data", adapter)
    monkeypatch.setattr(market_events.pipeline, "analyse_synced_news", batch)
    secret = "UI_TEST_SECRET_MUST_NOT_RENDER"
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", secret)
    monkeypatch.setenv("SLM_MODEL", "test-slm")
    monkeypatch.setenv("LLM_MODEL", "test-llm")
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(tmp_path / "live.sqlite")
    )
    next(button for button in app.button if button.label == "Open workspace").click().run()
    next(radio for radio in app.radio if radio.label == "Company universe").set_value("live").run()
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Connections"
    ).run()
    assert not app.exception
    assert not app.error
    assert next(
        select for select in app.multiselect if select.label == "Provider companies"
    ).value == ["LIVE:NSE:TEST"]
    assert sync_calls == batch_calls == []
    assert any("not checked" in item.value for item in app.info)
    rendered = " ".join(
        item.value for items in (app.markdown, app.caption, app.info, app.error) for item in items
    )
    assert secret not in rendered
    next(button for button in app.button if button.label == "Refresh selected data").click().run()
    assert sync_calls == [(["LIVE:NSE:TEST"], {"lookback_days": 550, "include_news": True})]
    assert batch_calls == []
    assert next(
        button for button in app.button if button.label.startswith("Analyse synced news")
    ).disabled
    app.run()
    assert len(sync_calls) == 1
    next(radio for radio in app.radio if radio.label == "Model execution mode").set_value(
        "live"
    ).run()
    assert batch_calls == []
    next(
        button for button in app.button if button.label.startswith("Analyse synced news")
    ).click().run()
    assert len(batch_calls) == 1
    assert batch_calls[0][0] == ["LIVE:NEWS:TEST"]
    assert batch_calls[0][1].isoformat() == stamp
    assert batch_calls[0][2] == {"policy": "slm_delegate", "limit": 10}
    app.session_state["technical_result"] = "old-scope-result"
    next(radio for radio in app.radio if radio.label == "Company universe").set_value("demo").run()
    for key in ("sync_report", "batch_report", "technical_result"):
        with pytest.raises(KeyError):
            _ = app.session_state[key]
    assert any("not checked" in item.value for item in app.info)
    assert len(sync_calls) == len(batch_calls) == 1
    assert not app.exception


def test_inbox_namespace_filter_does_not_start_analysis(tmp_path, monkeypatch):
    import market_events.pipeline
    from market_events.schemas import Article
    from market_events.storage import Storage

    adapter = ModuleType("market_events.live_data")
    adapter.get_live_universe = lambda source: []
    monkeypatch.setitem(sys.modules, "market_events.live_data", adapter)
    path = tmp_path / "mixed.sqlite"
    now = datetime.now(timezone.utc)
    with Storage(path) as storage:
        storage.add_articles(
            [
                Article(
                    article_id=key,
                    source_url=f"example.invalid/{key}",
                    text=f"Synthetic UI test for {key}",
                    published_at=now,
                    first_seen_at=now,
                )
                for key in ("local-article", "LIVE:NEWS:test")
            ]
        )
    calls = []
    monkeypatch.setattr(
        market_events.pipeline, "analyse_article", lambda *args, **kwargs: calls.append(True)
    )
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(path)
    )
    next(button for button in app.button if button.label == "Open workspace").click().run()
    next(radio for radio in app.radio if radio.label == "Workbench view").set_value(
        "Research"
    ).run()
    assert (
        next(select for select in app.selectbox if select.label == "Article").value
        == "local-article"
    )
    next(radio for radio in app.radio if radio.label == "Company universe").set_value("live").run()
    article = next(select for select in app.selectbox if select.label == "Article")
    assert article.value == "LIVE:NEWS:test"
    assert len(article.options) == 1
    assert calls == []
    assert not app.error


def test_workspace_overview_guides_first_action_without_writing_evidence(tmp_path):
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    path = tmp_path / "overview.sqlite"
    next(field for field in app.text_input if field.label == "SQLite database path").set_value(
        str(path)
    )
    next(button for button in app.button if button.label == "Open workspace").click().run()
    assert not app.exception
    assert not app.error
    assert any("Your research workspace at a glance" in item.value for item in app.markdown)
    assert any(button.label == "Import local evidence" for button in app.button)
    assert any(metric.label == "Articles" and metric.value == "0" for metric in app.metric)
    assert path.exists()
