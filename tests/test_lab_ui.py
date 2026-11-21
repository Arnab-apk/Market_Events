"""Offline Strategy lab interaction and chart boundary tests; fictional QA only."""

import hashlib
import json
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from market_events.chart_widgets import (
    _LIGHTWEIGHT_JS,
    hosted_chart_html,
    local_chart_html,
    monte_carlo_html,
    ohlc_rows,
    script_json,
)
from market_events.lab_ui import PREFIX, csv_text, fingerprint, result_manifest, scope_results
from market_events.schemas import MarketObservation
from market_events.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


def qa_bars(count=80, year=2019):
    rows = []
    for i in range(count):
        timestamp = datetime(year, 1, 1, 10, tzinfo=timezone.utc) + timedelta(days=i)
        price = 100 + i * 0.2 + (i % 10 - 5)
        rows.append(
            MarketObservation(
                instrument_id="SYNTHETIC:LAB_QA_ONLY",
                market_family="equity",
                timestamp=timestamp,
                available_at=timestamp,
                open=price,
                high=price + 2,
                low=price - 2,
                close=price + 1,
                volume=1000,
                currency="INR",
                unit="share",
            )
        )
    return rows


def render_fixture(database, root, universe="demo"):
    from pathlib import Path
    from types import SimpleNamespace

    from market_events.config import Settings
    from market_events.lab_ui import render_strategy_lab
    from market_events.storage import Storage

    settings = Settings(root=Path(root), database_path=Path(database), universe=universe)
    with Storage(Path(database)) as storage:
        render_strategy_lab(SimpleNamespace(settings=settings, storage=storage))


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Rendering/test must not access the network")

    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture
def lab(tmp_path):
    database = tmp_path / "qa.sqlite"
    with Storage(database) as storage:
        storage.add_observations(qa_bars())
    return AppTest.from_function(
        render_fixture, args=(str(database), str(ROOT)), default_timeout=20
    ).run()


def button(app, label):
    return next(x for x in app.button if x.label == label)


def test_local_bundle_is_pinned_and_no_external_script():
    assert len(_LIGHTWEIGHT_JS.encode()) == 189472
    assert hashlib.sha256(_LIGHTWEIGHT_JS.encode()).hexdigest() == (
        "756b0ba9f58930226d6b8b9d47ad310448ab85d799ea1f7c2c02304777c10b52"
    )
    html = local_chart_html(ohlc_rows(qa_bars(2)), {}, [])
    assert not re.search(r"<script[^>]+src=", html)
    assert "Copyright" in html and "TradingView" in html
    assert "Interactive chart unavailable" in html
    assert "height:580px" in html


def test_hosted_widget_validates_and_uses_official_embed():
    assert "embed-widget-advanced-chart.js" in hosted_chart_html("NSE:RELIANCE")
    assert "beyond 2020" in hosted_chart_html()
    with pytest.raises(ValueError):
        hosted_chart_html("</script><script>alert(1)</script>")


def test_chart_json_cannot_escape_script_context():
    text = "</script><img src=x onerror=alert(1)>"
    encoded = script_json({"label": text})
    assert "<" not in encoded and "</script>" not in encoded
    assert json.loads(encoded)["label"] == text
    with pytest.raises(ValueError):
        script_json({"value": float("nan")})


def test_results_invalidate_on_changed_input_and_workspace():
    state = {PREFIX + "backtest": {"old": True}, PREFIX + "simulation": {}, "other": 10}
    scope_results(state, "scope-one")
    assert PREFIX + "backtest" not in state
    state[PREFIX + "backtest"] = {"current": True}
    scope_results(state, "scope-one")
    assert state[PREFIX + "backtest"] == {"current": True}
    scope_results(state, "workspace-two")
    assert PREFIX + "backtest" not in state and state["other"] == 10


def test_manifest_links_dates_parameters_and_observations():
    bars = qa_bars(2)
    params = {"strategy": "buy_hold", "initial_capital": 100000.0}
    manifest = result_manifest(bars, params, date(2015, 1, 1), date(2020, 12, 31))
    manifest = json.loads(json.dumps(manifest, allow_nan=False))
    assert manifest["params"] == params
    assert manifest["study_dates"]["requested_end"] == "2020-12-31"
    assert manifest["study_dates"]["actual_start"] == "2019-01-01"
    assert manifest["supporting_observation_ids"] == [r.observation_id for r in bars]
    assert manifest["synthetic"] is True
    assert manifest["history_fingerprint"] == fingerprint([r.model_dump(mode="json") for r in bars])
    assert "token" not in json.dumps(manifest)
    assert csv_text([]) == ""


def test_empty_history_download_form_remains_accessible_and_credentials_explicit(tmp_path):
    app = AppTest.from_function(
        render_fixture, args=(str(tmp_path / "empty.sqlite"), str(ROOT))
    ).run()
    assert not app.exception
    assert any("No eligible local equity history" in x.value for x in app.info)
    assert any("credentials are missing" in x.value for x in app.info)
    button(app, "Download historical candles").click().run()
    assert not app.exception
    assert any("access token" in x.value for x in app.warning)
    assert app.session_state[PREFIX + "download_report"][1]["network_requests"] == 0
    assert all(x.value <= date(2020, 12, 31) for x in app.date_input)


def test_2026_demo_is_excluded_without_fabricated_fallback(tmp_path):
    database = tmp_path / "demo.sqlite"
    with Storage(database) as storage:
        storage.add_observations(qa_bars(5, year=2026))
    app = AppTest.from_function(render_fixture, args=(str(database), str(ROOT))).run()
    assert not app.exception
    assert any("bundled 2026 demo" in x.value for x in app.info)
    assert not any(x.label == "Run backtest" for x in app.button)


def test_render_is_offline_no_auto_run_and_synthetic_label_visible(lab):
    assert not lab.exception
    assert any("SYNTHETIC QA HISTORY" in x.value for x in lab.warning)
    assert PREFIX + "backtest" not in lab.session_state
    assert not lab.checkbox(key=PREFIX + "hosted").value
    assert button(lab, "Download historical candles")


@pytest.mark.parametrize("universe", ["demo", "live"])
def test_universe_namespace_boundary(tmp_path, universe):
    database = tmp_path / "namespaces.sqlite"
    local = qa_bars(2)
    live = [
        MarketObservation.model_validate(
            {**r.model_dump(exclude={"observation_id"}), "instrument_id": "LIVE:NSE:RELIANCE"}
        )
        for r in local
    ]
    with Storage(database) as storage:
        storage.add_observations(local + live)
    app = AppTest.from_function(render_fixture, args=(str(database), str(ROOT), universe)).run()
    assert not app.exception
    choice = app.selectbox(key=PREFIX + "instrument")
    assert choice.options == (
        ["LIVE:NSE:RELIANCE"] if universe == "live" else ["SYNTHETIC:LAB_QA_ONLY"]
    )
    if universe == "demo":
        assert any("Select the live universe" in x.value for x in app.caption)


def test_backtest_monte_carlo_and_input_invalidation(lab):
    button(lab, "Run backtest").click().run()
    assert not lab.exception
    result = lab.session_state[PREFIX + "backtest"]
    assert result["equity"] and result["manifest"]["supporting_observation_ids"]
    assert result["manifest"]["params"]["slow_period"] == 50
    button(lab, "Simulate return paths").click().run()
    assert not lab.exception
    simulation = lab.session_state[PREFIX + "simulation"]
    assert len(simulation["paths"]) == 300
    assert simulation["manifest"]["params"]["seed"] == 42
    assert simulation["manifest"]["parent_backtest"] == result["manifest"]
    lab.number_input(key=PREFIX + "capital").set_value(200000.0).run()
    assert not lab.exception
    assert PREFIX + "backtest" not in lab.session_state
    assert PREFIX + "simulation" not in lab.session_state


def test_no_selected_window_history_invalidates_backtest(lab):
    button(lab, "Run backtest").click().run()
    lab.date_input(key=PREFIX + "study_start").set_value(date(2020, 1, 1)).run()
    assert not lab.exception
    assert PREFIX + "backtest" not in lab.session_state
    assert any("No eligible historical bars" in x.value for x in lab.info)
    assert button(lab, "Download historical candles")


def test_invalid_strategy_parameters_show_actionable_error(lab):
    lab.number_input(key=PREFIX + "fast").set_value(60).run()
    button(lab, "Run backtest").click().run()
    assert not lab.exception
    assert any("smaller than slow_period" in x.value for x in lab.error)


def test_generated_chart_javascript_parses_and_animation_has_accessibility_controls():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable for JS syntax validation")
    result = {
        "paths": [[100, 101, 99]],
        "bands": [{"step": i, "p05": 98, "p50": 100, "p95": 102} for i in range(3)],
    }
    html = monte_carlo_html(result, reduced_motion=True)
    for expected in (
        "Pause",
        "Replay",
        "prefers-reduced-motion",
        "aria-label",
        "visibilitychange",
        "requestAnimationFrame",
        '"reduced": true',
    ):
        assert expected in html
    for markup in [html, local_chart_html(ohlc_rows(qa_bars(2)), {}, ["MACD"])]:
        scripts = re.findall(r"<script>(.*?)</script>", markup, flags=re.S)
        assert scripts
        for script in scripts:
            checked = subprocess.run(
                [node, "--check"],
                input=script,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=20,
            )
            assert checked.returncode == 0, checked.stderr


def test_animation_progress_and_reduced_motion_status_are_consistent():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable for animation behavior validation")
    result = {
        "paths": [[100] * 253],
        "bands": [{"step": i, "p05": 98, "p50": 100, "p95": 102} for i in range(253)],
    }
    script = re.findall(r"<script>(.*?)</script>", monte_carlo_html(result), flags=re.S)[0]
    environment = """
const assert=require('node:assert/strict');
const elements=Object.fromEntries(['paths','play','replay','reduce','progress','announcements'].map(id=>
 [id,{clientWidth:700,textContent:'',setAttribute(){},addEventListener(){}}]));
elements.paths.getContext=()=>new Proxy({},{get:()=>()=>{}});
global.document={getElementById:id=>elements[id],addEventListener(){},
 querySelector:()=>({addEventListener(){}})};
global.matchMedia=()=>({matches:false,addEventListener(){}});
global.devicePixelRatio=1;
let pendingFrame;
global.requestAnimationFrame=callback=>{pendingFrame=callback;return 1;};
global.cancelAnimationFrame=()=>{pendingFrame=undefined;};
global.ResizeObserver=class{observe(){}};
"""
    assertions = """
assert.equal(elements.progress.textContent,'Step 252 of 252');
elements.play.onclick();
assert.equal(elements.progress.textContent,'Step 0 of 252');
const playingAnnouncement=elements.announcements.textContent;
pendingFrame(100);
assert.equal(elements.progress.textContent,'Step 2 of 252');
pendingFrame(200);
assert.equal(elements.progress.textContent,'Step 4 of 252');
assert.equal(elements.announcements.textContent,playingAnnouncement);
elements.play.onclick();
assert.match(elements.announcements.textContent,/Step 4 of 252.*Paused/);
elements.reduce.checked=true;
elements.reduce.onchange();
assert.equal(elements.progress.textContent,'Step 252 of 252');
assert.match(elements.announcements.textContent,/Step 252 of 252.*Complete/);
assert.equal(elements.play.textContent,'Play');
assert.equal(pendingFrame,undefined);
"""
    checked = subprocess.run(
        [node],
        input=environment + script + assertions,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert checked.returncode == 0, checked.stderr
