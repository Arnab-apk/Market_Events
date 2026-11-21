"""Exports of saved research. case_payload builds the evidence view of one run for the UI and JSON
downloads; export_bundle writes runs, articles, outcomes and the exact supporting observations to
a portable JSON file. Only observations a run actually referenced are included, and missing ones
are listed.
"""

import json
from pathlib import Path


def selected_observations(run, observations) -> dict:
    """Resolve only saved feature references; never substitute newer market rows."""
    lookup = {item.observation_id: item for item in observations}
    references = list(
        dict.fromkeys(
            (run.features.observation_ids if run.features else [])
            + (run.technicals.observation_ids if run.technicals else [])
        )
    )
    return {
        "observations": [
            lookup[key].model_dump(mode="json") for key in references if key in lookup
        ],
        "missing_observation_ids": [key for key in references if key not in lookup],
    }


def case_payload(storage, run) -> dict:
    """Build the same read-only evidence payload for the UI and JSON downloads."""
    article = storage.get_article(run.article_id)
    outcome = storage.get_outcome(run.run_id)
    return {
        "run": run.model_dump(mode="json"),
        "article": article.model_dump(mode="json") if article else None,
        "outcome": outcome.model_dump(mode="json") if outcome else None,
        **selected_observations(run, storage.list_observations()),
    }


def export_bundle(storage, output: Path, run_id: str | None = None) -> dict:
    """Write all (or one) saved runs with their sources, outcomes and evidence to JSON."""
    runs = storage.list_runs()
    if run_id:
        runs = [r for r in runs if r.run_id == run_id]
        if not runs:
            raise ValueError(f"Unknown run: {run_id}")
    ids = {r.run_id for r in runs}
    article_ids = {r.article_id for r in runs}
    articles = [a for a in storage.list_articles() if a.article_id in article_ids]
    outcomes = [o for o in storage.list_outcomes() if o.run_id in ids]
    observations = storage.list_observations()
    evidence = {run.run_id: selected_observations(run, observations) for run in runs}
    selected = {
        item["observation_id"]: item for case in evidence.values() for item in case["observations"]
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provenance": "See article source identifiers and run modes. Bundled demo is synthetic.",
        "articles": [a.model_dump(mode="json") for a in articles],
        "runs": [r.model_dump(mode="json") for r in runs],
        "outcomes": [o.model_dump(mode="json") for o in outcomes],
        "observations": [selected[key] for key in sorted(selected)],
        "missing_observation_ids_by_run": {
            key: case["missing_observation_ids"]
            for key, case in evidence.items()
            if case["missing_observation_ids"]
        },
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    usage_path = output.with_suffix(".usage.json")
    usage_path.write_text(
        json.dumps(
            {
                "model_calls": [c.model_dump(mode="json") for r in runs for c in r.calls],
                "outcomes": payload["outcomes"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    case_dir = output.parent / (output.stem + "-cases")
    case_dir.mkdir(exist_ok=True)
    for run in runs:
        article = next(a for a in articles if a.article_id == run.article_id)
        assessment = run.assessment
        text = [
            f"# Research case {run.run_id}",
            "",
            f"Mode: {run.mode}. Policy: {run.policy.value}. Status: {run.status}.",
            "",
            f"Article: {article.article_id}, source version {article.source_version}.",
            f"Source: {article.source_url}",
            f"Decision cutoff (UTC): {run.decision_time.isoformat()}",
            f"Parent run: {run.parent_run_id or 'none'}. Request key: {run.request_key or 'none'}.",
            "",
            "## Evidence assessment",
            "",
            assessment.explanation
            if assessment
            else (run.error or "No numerical assessment produced."),
            "",
            f"Evidence label: {assessment.evidence_label if assessment else 'unavailable'}",
            "",
            "## Exact source passages",
            "",
        ]
        for span in run.extraction.source_spans if run.extraction else []:
            text.extend(["> " + span.replace("\n", "\n> "), ""])
        explanation = run.config_snapshot.get("explanation_result")
        if isinstance(explanation, dict) and explanation.get("text"):
            text.extend(["## Saved optional model explanation", "", explanation["text"], ""])
            for span in explanation.get("source_spans", []):
                text.extend(["> " + span.replace("\n", "\n> "), ""])
        elif run.status == "explanation_completed":
            text.extend(["Optional explanation text was not retained in this older record.", ""])
        if run.features:
            text.extend(
                [
                    "## Market inputs",
                    "",
                    "```json",
                    run.features.model_dump_json(indent=2),
                    "```",
                    "",
                ]
            )
        if run.technicals:
            text.extend(
                [
                    "## Technical indicators at the decision cutoff",
                    "",
                    "Historical price context; indicators do not change the event evidence score.",
                    "",
                    "```json",
                    run.technicals.model_dump_json(indent=2),
                    "```",
                    "",
                ]
            )
        if run.features or run.technicals:
            text.extend(
                [
                    "## Referenced observations",
                    "",
                    "```json",
                    json.dumps(evidence[run.run_id], indent=2),
                    "```",
                    "",
                ]
            )
        outcome = storage.get_outcome(run.run_id)
        text.extend(
            [
                "## Separate later outcome",
                "",
                outcome.model_dump_json(indent=2) if outcome else "Not evaluated.",
                "",
                "## Model calls",
                "",
                "```json",
                json.dumps([c.model_dump(mode="json") for c in run.calls], indent=2),
                "```",
                "",
                "Evidence scores are not probabilities. Outcomes are independent hypothetical long observations, not a funded portfolio.",
            ]
        )
        # Generated UUID is used, never a user-supplied path fragment.
        safe_name = __import__("hashlib").sha256(run.run_id.encode()).hexdigest()[:16]
        (case_dir / f"case-{safe_name}.md").write_text("\n".join(text), encoding="utf-8")
    return {
        "runs": len(runs),
        "json": str(output),
        "usage": str(usage_path),
        "cases": str(case_dir),
    }
