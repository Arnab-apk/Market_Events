"""Developer script: explicit live-model comparison of the three execution policies. It loads the
synthetic demo, re-analyses the same synthetic sources under every policy with live models, and
saves the comparison and export bundles. Results describe development runs on authored inputs,
not real-market validation.
"""

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

from market_events.config import load_settings
from market_events.experiments import run_experiments
from market_events.exporting import export_bundle
from market_events.pipeline import (
    Dependencies,
    analyse_article,
    compute_outcomes,
    explain_run,
    run_demo,
)
from market_events.schemas import ExecutionPolicy
from market_events.storage import Storage


def main():
    """Run every policy over the same sources and save the JSON reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    settings = load_settings()
    if args.database:
        settings.database_path = args.database.resolve()
    run_demo(settings.root, settings.database_path)
    settings.mode = "live"
    settings.max_tokens = 30000
    settings.timeout_seconds = 180
    cutoff = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)
    with Storage(settings.database_path) as storage:
        deps = Dependencies(storage, settings)
        for policy in ExecutionPolicy:
            for article_id in (
                "syn-001",
                "syn-002",
                "syn-003",
                "syn-004",
                "syn-005",
                "syn-031",
                "syn-032",
            ):
                run = analyse_article(article_id, cutoff, policy, deps)
                print(f"{policy.value} {article_id}: {run.status} / {run.error}", flush=True)
        compute_outcomes(deps)
        report = run_experiments(deps)
        report["purpose"] = (
            "Development checks on authored synthetic inputs. Actual configured inference; no held-out, real-data, predictive or latency-superiority claim."
        )
        Path("runs").mkdir(exist_ok=True)
        Path("runs/policy_comparison.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(export_bundle(storage, Path("runs/handover.json")), indent=2), flush=True)
        target = next(
            (
                r
                for r in storage.list_runs()
                if r.mode == "live" and r.assessment and r.status == "completed"
            ),
            None,
        )
        if target:
            try:
                result = explain_run(target.run_id, deps)
                print("Optional explanation preserved the saved decision: " + result, flush=True)
            except (ValueError, RuntimeError) as exc:
                print("Optional explanation fallback retained: " + str(exc), flush=True)
        print("All comparison cases saved.", flush=True)


if __name__ == "__main__":
    main()
