# Demo and viva

Project: *A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets*. It is implemented as **Market Events**, the software demonstrated below.

## Presentation pack (1 December 2026)

The presentation uses the Next.js dashboard (`npm.cmd run dev`, http://127.0.0.1:3000). See
[the slides](presentation/SLIDES.md), [the timed demo script with offline fallbacks](presentation/DEMO_SCRIPT.md),
[27 viva answers](presentation/VIVA_QA.md) and [the architecture diagram](presentation/ARCHITECTURE_DIAGRAM.md).
The Streamlit walkthrough below remains the fallback path and uses the same engine. In Next.js, follow the 7-step
**demo tour** on the Overview page (step 1's button is **Load synthetic demo**; the heading button is
**Load synthetic demo (replay)**). Start from a fresh `data/web_demo.sqlite` as described in the demo script's
"Before you present" checklist. In Streamlit, the button is **Load synthetic demo (replay)**.

### Outcome definition (say this explicitly)

The later outcome is a **market-adjusted return with beta implicitly 1**: the equity's gross return from
the first session whose 09:15 IST open is after the decision cutoff to the fifth observed session's
close (entry counts as session one), minus the same-dates benchmark return. A 10 bps total round-trip
cost gives the net figure (`outcomes.evaluate_outcome`). It measures **post-cutoff drift**. The evidence
score, by contrast, uses the **reaction-day** excess return already observable at the cutoff
(`market_features.py`). Score and outcome therefore describe different windows, and comparing them is
not circular. The outcome has no estimation window, fitted beta, cross-event aggregation or test
statistic. **Future work:** market-model abnormal returns with a pre-event estimation window,
CAR/CAAR at several horizons, and Boehmer–Musumeci–Poulsen (BMP) standardised cross-sectional and sign
tests (MacKinlay 1997; Boehmer et al. 1991; see `research/RESEARCH_BRIEF.md` §1.4). In the synthetic demo,
all three outcomes are gross +4.58%, net +4.48%, benchmark +0.90%. They are identical because the
fixture prices are constant-growth paths, so they show the mechanics only.

### Three kinds of look-ahead (viva answer)

1. **Data availability:** handled. Articles need `published_at` and `first_seen_at` ≤ cutoff.
   Observations need `timestamp` and `available_at`. Exposure rules need `effective_at` and `known_at`.
   Provider downloads record their real fetch time.
2. **Revisions:** handled. The ledger is append-only (storage triggers), price revisions are
   reported as conflicts, and requests are hashed over a frozen configuration snapshot.
3. **Parametric model knowledge:** **not tested**. It is limited because the model only extracts and
   never emits a direction or score, and the bundled articles are synthetic. On real news, pretrained knowledge could
   still bias relevance or event-type decisions. The planned test is an entity-anonymisation ablation
   (Glasserman & Lin 2023) plus pre/post knowledge-cutoff splits.

## Streamlit walkthrough (fallback path)

Start Streamlit using the command in the [user guide](USER_GUIDE.md) ("Start locally"). Open the page and observe that no demo or database is created. Select **Load synthetic demo (replay)** and explicitly identify the synthetic provenance. Its decision cutoff is 12 January 2026, 17:30 IST / noon UTC.

The demo action is in the main-area quick start and opens **Review saved results**. Begin with the human-readable evidence label, signed score and percentage coverage. Explain that coverage is available evidence weight, not confidence. Then inspect the source and evidence tabs. Raw source/event records, observation diagnostics, policy/repeat controls and configuration remain in labelled expanders. In **Analyse an article**, use **Open saved result** after the explicit analysis submit; changing an article or filter does not start inference.

The current fresh offline demo produces three completed families: earnings `syn-001`, commodity disruption `syn-002` and order `syn-003`. An early log entry showing `syn-001` as duplicate is historical. The basic demo does not run all seven fixture articles; use explicit analysis submissions for the additional recorded cases.

To demonstrate indicators independently, import at least 50 consistent daily equity bars and choose **Explore price indicators**, a company and an aware cutoff, then **Compute price indicators**. No news or model setup is needed. Only returned supporting observations appear in the chart. At the original January fixture cutoff there are only seven eligible bars, so unavailable indicator warm-ups are expected. Show exact missing/stale/conflict interpretations instead of claiming the demo supplies a complete indicator study.

1. Inspect a clear supported event: original source, spans, canonical company, reviewed exposure assumption, selected observations, score and deterministic explanation.
2. Inspect an irrelevant item: show the retained filter decision and any absence of extraction/assessment rather than asserting success.
3. Show duplicate/update history from the imported dataset, including source version and cutoff. New means new within the dataset, not globally novel news.
4. Inspect conflicting equity/commodity evidence. Show both components and any conflicts, without calling the score a probability.
5. Use a case with missing/stale mandatory evidence. Show abstention, not a manufactured zero or confident direction. If the bundled demo lacks one of these cases, import a reviewed synthetic case explicitly; do not claim an unexercised scenario was verified.

Existing local handover records provide concrete examples: `syn-001`/`syn-003` have supported positive evidence, `syn-002` has conflicting cross-market evidence, `syn-004` is irrelevant, and `syn-031`/`syn-032` are recorded duplicates (the latter is source version 2). `syn-005` is an ambiguous-entity abstention under the SLM policies, but LLM-only filtered it as irrelevant; disclose that disagreement. It is not a missing/stale-market case. The local handover artifacts do not establish a manually exercised missing/stale UI case; automated domain tests cover those gates. The archived JSON/Markdown files are local ignored artifacts and may be absent from a fresh checkout.

Evaluate later outcomes explicitly. Explain next-session entry, the fifth trading session including entry, pending horizons and separate cost/benchmark fields. Export a case JSON and comparison JSON. In comparisons distinguish recorded replay resources from actual live inference measurements, inspect common-input cohorts, and show how commodity ablation changes a score or abstention on identical frozen evidence.

Inspect the case's referenced observation rows and any missing-reference warning; the watchlist is a different view of latest imported sessions. An optional explanation is an explicit request with a separate saved child trace and retained text; select that child to show its parent link and inherited assessment. Policy comparisons exclude explanation children and show their usage separately. The comparison manifest retains run identities and outcome mode/policy. CLI export also writes usage JSON and Markdown case reports; old archived exports lack the new observation fields until exported again from saved storage.

Be ready to answer: Why are first-seen and published time different? Why must availability and observation timestamp both precede cutoff? Why does a missing commodity force abstention? Why does a validated extraction not imply economic truth? Why can fewer LLM calls fail to improve latency? Where are calculations performed? Follow `pipeline` → domain functions; no arithmetic or SQL is hidden in the dashboard.

Live inference is a separate opt-in provider exercise. Configure actual models through `config.py` and local environment settings, use permitted input data, and preserve call identities/errors. The completed synthetic development pilot used `qwen3.5:2b` and `gemma4:e4b`; see model notes for bounded functional results. This does not establish real-market validity.

For the real-data path, follow [LIVE_SETUP.md](LIVE_SETUP.md), select the provider universe and open **Connect and refresh data**. Configuration checks do not test a connection. Refresh data explicitly, inspect counts and per-company errors, then compute local indicators or separately submit the bounded news-model batch. Token presence alone never demonstrates successful access. Adapter/pipeline integration now passes offline with mocked HTTP transports, including repeat-refresh and model-action isolation checks. A real-account demonstration still requires your own configured token and successful explicit fetch.

The dashboard runs locally at `http://127.0.0.1:8501` with the Streamlit command in the [user guide](USER_GUIDE.md). Automated UI checks use Streamlit AppTest. Browser screenshots and visual browser inspection were not checked because the browser tool had no available browser; do not present AppTest as visual or accessibility certification.
