# Data dictionary

All stored times are timezone-aware UTC; the workbench displays the decision/source times in `Asia/Kolkata` (IST, UTC+05:30). JSON preserves explicit offsets. Publication time, first-seen time, session timestamp and data availability are separate fields.

| Record | Meaning and conventions |
| --- | --- |
| Article | Required ID, source URL/identifier, text, published and first-seen times; source version, optional predecessor. Content hash is SHA256 of whitespace-normalized text. |
| MarketObservation | Canonical instrument, family, OHLC strictly positive, volume nonnegative, currency/unit, timestamp and available-at. Commodity requires an explicit contract. Natural-key observation ID is derived by the schema. |
| EventExtraction | Event type, candidate/canonical entities, exact spans, amounts and narrative direction. `validated` means source-supported structure, not economic truth. |
| ExposureRule | Reviewed conceptual relationship and sign, source, known/effective times, rule ID and version. Demonstration mappings are assumptions. |
| MarketFeatures | Decision cutoff, supporting observation IDs, values, missing/stale lists and definition version. Missing values remain null. |
| Assessment | Internal direction, guide-compatible `evidence_label`, signed score, coverage 0–1, conflicts, abstention reasons, exact inputs, rules version and explanation. Display labels are `positive_evidence`, `negative_evidence`, `mixed_evidence`, `insufficient_evidence`; the schema derives them from the existing direction/conflict state. |
| ModelCall | Provider/model/prompt version, replay/live mode, usage if known, retries, latency and failure. Unknown tokens are null, not zero. |
| AnalysisRun | Run/article IDs, policy, mode, cutoff, original configuration and stage results, immutable assessment and failure context. |
| EventOutcome | Separate pending/completed/invalid record keyed by run; entry/exit, gross/net/benchmark/excess returns, reason and definition version. |

Article import is one JSON object per line with `article_id`, `source_url`, `text`, `published_at`, `first_seen_at`, optional `source_version` and `predecessor_id`. Market CSV columns are `instrument_id,market_family,timestamp,available_at,open,high,low,close,volume,currency,unit,contract_id`. Use explicit offsets. Importers report row errors independently.

Contract numerical definitions: price return = latest / previous − 1; equity excess = equity return − benchmark return. Relative volume = latest volume / preceding five-session mean. A 0.01 return means 1%; the UI displays fractional values. Observations must satisfy timestamp AND available-at ≤ cutoff; stale means older than four calendar days at EOD. Commodity contracts are never combined.

Baseline equity signal clips excess return / 0.02 to [−1,1]; commodity signal clips return × reviewed sign / 0.03. Cross-market baseline weights are 0.6/0.4; directional threshold is ±0.15; minimum coverage is 0.6. Missing mandatory evidence gates direction regardless of a partial score. Relative volume is context only. Configuration and the domain module are authoritative.

Outcome entry is the first later equity session's open; exit is the fifth session including entry, at close. Net return subtracts round-trip cost_bps / 10000 from gross. Benchmark entry/exit use matching session dates; missing benchmark remains explicit. Hypothetical outcomes are not executed trades or short-side strategy P&L.

Run audit fields include `request_key`, optional `parent_run_id` and `stage_durations_ms`. A parent may identify an explicit repeat analysis or a distinct optional explanation. Explanation children have `explanation_*` status and/or `config_snapshot.explanation_parent_run_id`; their inherited assessment is not a new analysis. Successful new children retain `config_snapshot.explanation_result` with `text` and `source_spans`. Older records may lack it.

Case JSON includes `observations` resolved from saved feature references and `missing_observation_ids`; bundle JSON includes their union and `missing_observation_ids_by_run`. These are original decision references, not the later outcome series. Comparison outcome rows add run mode/policy/article/cutoff as export context without changing the stored outcome schema.
