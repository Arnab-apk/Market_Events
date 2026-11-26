"""Command line interface (``python -m market_events ...``). Each subcommand opens the configured
ledger and calls one public workflow: demo, import, analyse, outcomes, export, experiments,
technicals, paper portfolio proposals (paper-screen/size/risk/rebalance; research only, never
orders) or explicit live syncs. Numerical rules stay in the domain modules; this file only
parses arguments and prints results.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_settings
from .ingestion import import_articles, import_market_prices
from .pipeline import (
    Dependencies,
    analyse_article,
    analyse_synced_news,
    compute_outcomes,
    readiness,
    run_demo,
)
from .schemas import ExecutionPolicy
from .storage import Storage


def main(argv=None):
    """Parse arguments, run one subcommand and return a process exit code."""
    parser = argparse.ArgumentParser(description="Local financial event research")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--database", type=Path)
    parser.add_argument("--universe", choices=["demo", "live"])
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Load synthetic data and labelled replay")
    demo.add_argument("--database", dest="demo_database", type=Path)
    demo.add_argument("--mode", choices=["replay", "live-model"], default="replay")
    commands.add_parser("init-db")
    commands.add_parser("readiness", help="Offline configuration and coverage checks")
    sync = commands.add_parser("sync-live", help="Explicitly fetch real daily bars and news")
    sync.add_argument("--companies", nargs="+")
    sync.add_argument("--lookback-days", type=int, default=550)
    sync.add_argument("--no-news", action="store_true")
    sync.add_argument(
        "--no-commodities",
        action="store_true",
        help="Skip commodities linked by reviewed live exposure rules",
    )
    technicals = commands.add_parser("technicals", help="Calculate local technical indicators")
    technicals.add_argument("company_id")
    technicals.add_argument(
        "--decision-time", type=lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))
    )
    batch = commands.add_parser("analyse-news", help="Explicit live model batch on synced news")
    batch.add_argument("--article-ids", nargs="+", required=True)
    batch.add_argument(
        "--decision-time",
        type=lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")),
        required=True,
    )
    batch.add_argument(
        "--policy", choices=[p.value for p in ExecutionPolicy], default="slm_delegate"
    )
    batch.add_argument("--limit", type=int, default=10)
    for command in ("import-articles", "import-market"):
        sub = commands.add_parser(
            command, aliases=["import-prices"] if command == "import-market" else []
        )
        sub.add_argument("path", type=Path, nargs="?")
        sub.add_argument("--file", dest="file_path", type=Path)
    analyse = commands.add_parser("analyse")
    analyse.add_argument("article_id", nargs="?")
    analyse.add_argument("--article-id", dest="article_option")
    analyse.add_argument(
        "--decision-time",
        "--as-of",
        type=lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")),
        required=True,
    )
    analyse.add_argument(
        "--policy", choices=[p.value for p in ExecutionPolicy], default="slm_delegate"
    )
    analyse.add_argument("--mode", choices=["live", "replay"])
    analyse.add_argument(
        "--repeat", action="store_true", help="Create a separate linked repeat experiment"
    )
    evaluate = commands.add_parser("outcomes", aliases=["evaluate"])
    evaluate.add_argument("--run-id")
    commands.add_parser("list-runs")
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, default=Path("runs/export.json"))
    export.add_argument("--run-id")
    experiments = commands.add_parser("experiments")
    experiments.add_argument("--output", type=Path, default=Path("runs/experiments.json"))
    _add_paper_commands(commands)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.root)
        if args.universe:
            settings.universe = args.universe
        if args.command in {"sync-live", "analyse-news"}:
            settings.universe = "live"
        if args.command == "analyse-news":
            settings.mode = "live"
        if args.database:
            settings.database_path = args.database.resolve()
        if args.command == "demo":
            runs = run_demo(args.root, args.demo_database or settings.database_path, mode=args.mode)
            print(
                json.dumps(
                    {
                        "mode": args.mode,
                        "data": "synthetic",
                        "runs": [r.model_dump(mode="json") for r in runs],
                    },
                    indent=2,
                )
            )
            return 0 if runs and all(r.status in {"completed", "abstained"} for r in runs) else 1
        if args.command == "analyse" and args.mode:
            settings.mode = args.mode
        with Storage(settings.database_path) as storage:
            dependencies = Dependencies(storage, settings)
            if args.command.startswith("paper-"):
                return _run_paper(args, storage, settings.universe)
            if args.command == "readiness":
                print(json.dumps(readiness(dependencies), indent=2))
                return 0
            if args.command == "sync-live":
                from .live_data import get_live_universe, sync_live

                company_ids = args.companies or [
                    row["instrument_id"]
                    for row in get_live_universe(settings)
                    if row.get("market_family", "equity") == "equity"
                ]
                report = sync_live(
                    dependencies,
                    company_ids,
                    args.lookback_days,
                    include_news=not args.no_news,
                    include_commodities=not args.no_commodities,
                )
                print(json.dumps(report, indent=2))
                return 1 if report["errors"] else 0
            if args.command == "technicals":
                from .technicals import compute_technicals

                expected_live = args.company_id.startswith("LIVE:")
                if expected_live != (settings.universe == "live"):
                    raise ValueError(
                        "Company and --universe differ; select demo or live explicitly"
                    )
                result = compute_technicals(
                    storage.list_observations(),
                    args.decision_time or datetime.now(timezone.utc),
                    args.company_id,
                )
                print(result.model_dump_json(indent=2))
                return 0
            if args.command == "analyse-news":
                results = analyse_synced_news(
                    dependencies, args.article_ids, args.decision_time, args.policy, args.limit
                )
                print(json.dumps(results, indent=2))
                return 1 if any(row["status"] in {"failed", "partial"} for row in results) else 0
            if args.command.startswith("import-"):
                articles = args.command == "import-articles"
                path = args.file_path or args.path
                if path is None:
                    raise ValueError("Provide an import file path or --file PATH")
                result = (import_articles if articles else import_market_prices)(path)
                added = (storage.add_articles if articles else storage.add_observations)(
                    result.records
                )
                print(
                    json.dumps(
                        {"added": added, "errors": result.errors, "warnings": result.warnings},
                        indent=2,
                        default=str,
                    )
                )
                return 1 if result.errors else 0
            if args.command == "analyse":
                article_id = args.article_option or args.article_id
                if not article_id:
                    raise ValueError("Provide article ID or --article-id ID")
                run = analyse_article(
                    article_id,
                    args.decision_time,
                    args.policy,
                    dependencies,
                    repeat_run=args.repeat,
                )
                print(run.model_dump_json(indent=2))
                return 1 if run.status in {"failed", "partial"} else 0
            if args.command in {"outcomes", "evaluate"}:
                print(
                    json.dumps(
                        [
                            r.model_dump(mode="json")
                            for r in compute_outcomes(dependencies, args.run_id)
                        ],
                        indent=2,
                    )
                )
            elif args.command == "list-runs":
                print(
                    json.dumps(
                        [
                            {
                                "run_id": r.run_id,
                                "article_id": r.article_id,
                                "policy": r.policy.value,
                                "mode": r.mode,
                                "status": r.status,
                            }
                            for r in storage.list_runs()
                        ],
                        indent=2,
                    )
                )
            elif args.command == "export":
                from .exporting import export_bundle

                print(json.dumps(export_bundle(storage, args.output, args.run_id), indent=2))
            elif args.command == "experiments":
                from .experiments import run_experiments

                report = run_experiments(dependencies)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
                print(f"Saved comparison to {args.output}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cutoff(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _add_paper_commands(commands) -> None:
    """Paper portfolio subcommands: research proposals only, never orders."""
    note = "paper proposal, research only, not advice"
    screen = commands.add_parser("paper-screen", help=f"Rank saved assessments ({note})")
    size = commands.add_parser("paper-size", help=f"Size an INR budget into paper buys ({note})")
    risk = commands.add_parser("paper-risk", help=f"Re-check a saved paper plan ({note})")
    rebalance = commands.add_parser(
        "paper-rebalance", help=f"Paper trades back to target weights ({note})"
    )
    for sub in (screen, size, rebalance):
        sub.add_argument("--as-of", type=_cutoff, required=True)
    size.add_argument("--budget", type=float, help="INR budget (default: portfolio_rules.json)")
    risk.add_argument("--plan", type=Path, required=True, help="Saved plan JSON file")
    rebalance.add_argument(
        "--positions",
        type=Path,
        required=True,
        help='JSON list of {"instrument_id": ..., "quantity": whole shares}',
    )
    rebalance.add_argument("--cash", type=float, required=True, help="Paper cash in INR")
    for sub in (screen, size, risk, rebalance):
        sub.add_argument("--json", action="store_true", help="Print raw JSON")
    for sub in (size, rebalance):
        sub.add_argument("--no-save", action="store_true", help="Do not write runs/paper/*.json")


def _emit(text: str) -> None:
    """Print readably on any console: non-UTF-8 consoles get ASCII dash and rupee spellings."""
    encoding = sys.stdout.encoding or "utf-8"
    if encoding.lower().replace("-", "") != "utf8":
        text = text.replace("—", "-").replace("₹", "Rs ")
    print(text.encode(encoding, errors="replace").decode(encoding))


def _run_paper(args, storage, universe: str) -> int:
    from .paper_portfolio import (
        build_plan,
        build_rebalance,
        build_screen,
        check_plan,
        load_plan,
        plan_table,
        save_plan,
        scoped,
        screen_table,
        to_json,
    )

    ledger = scoped(storage, universe)
    if args.command == "paper-screen":
        result = build_screen(ledger, args.root, args.as_of)
        _emit(to_json(result) if args.json else screen_table(result))
        return 0
    if args.command == "paper-size":
        plan = build_plan(ledger, args.root, args.as_of, budget_inr=args.budget)
    elif args.command == "paper-risk":
        plan = check_plan(ledger, args.root, load_plan(args.plan))
    else:
        positions = json.loads(args.positions.read_text(encoding="utf-8"))
        if not isinstance(positions, list):
            raise ValueError("Positions file must be a JSON list of {instrument_id, quantity}")
        plan = build_rebalance(ledger, args.root, positions, args.cash, args.as_of)
    if args.command != "paper-risk" and not args.no_save:
        print(f"Saved paper plan to {save_plan(plan, args.root)}", file=sys.stderr)
    _emit(to_json(plan) if args.json else plan_table(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
