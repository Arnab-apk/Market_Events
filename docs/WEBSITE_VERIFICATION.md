# Website verification — 27 October 2026

> **Historical record (annotated 2026-11-23).** File names below describe the frontend as it was then. Since commit `7ef4918`, the web CSS is six files: `tokens.css`, `base.css`, `layout.css`, `components.css`, `overview.css` and `presentation.css`. The old `globals.css`, `crypto-system.css`, `fintech-theme.css`, `hero.css`, `premium-overview.css`, `premium-theme.css` and `color-modes.css`, and `_components/signal-hero.tsx`, were removed. See `web/README.md` for the current structure.

## Premium dashboard revision

The latest revision follows the user's agreed design direction: the [Zajno crypto reference](https://dribbble.com/shots/26372656-AI-Helper-for-Smarter-Crypto-Investing-and-Trading) supplies the compact dashboard structure and charcoal/lime/gold palette; the [Zajno health reference](https://dribbble.com/shots/26451832-AI-Powered-Platform-for-Proactive-Health-Monitoring) informs the spacing, fine chart grids and information hierarchy. The overview replaces the previous large promotional hero.

- New horizontal desktop navigation retains all eight workflows; the accessible mobile drawer opens below 1101px.
- The overview shows real workspace counts, saved company snapshots, an explicit local-price loader, a keyboard-inspectable area chart, a session-range selector, original-price tables, searchable watchlist, and saved-source links.
- Evidence coverage is the mean coverage of saved assessed cases and is labelled as evidence completeness rather than predictive confidence. Prices and one-session changes use eligible saved observations. No invented balances, forecasts, gains or trades are displayed.
- Browser verification loaded 16 Asian Paints sessions from the synthetic demo through the Next proxy and Python technicals endpoint and rendered the original closing prices. It also confirmed mobile drawer opening/Escape/focus restoration and no page overflow at 375px or the 1120px desktop boundary.
- Final TypeScript/ESLint, production build and 13 origin-regression tests passed. No Python implementation changed, so the prior 521-test Python checkpoint remains applicable.
- The existing Herdr theme agent implemented the shared premium theme; a separate reviewer inspected the overview and navigation. No provider/model calls or dependency installations were required.
- Review corrections: watchlist timestamps use Asia/Kolkata while date-only chart labels retain their session dates; the request callback depends on workspace/universe primitives, so toggling visual effects does not reload the workspace. All chart-range choices remain available on mobile. Watchlist filtering and the 10-session range were verified in the browser.

## Earlier React Bits checkpoint

The Next.js website reuses the Python research engine. The visual update adds official React Bits Aurora and Spotlight Card source, a custom evidence-engine illustration, an ambient-effects pause control, and an obsidian/mint/cyan theme across existing workflows.

## Verification

- Full offline Python suite: **521 passed**, one upstream Starlette/httpx deprecation warning. No Python application code changed during this visual update.
- TypeScript and ESLint: `npm.cmd run check` passed.
- Production compilation: `npm.cmd run build` passed.
- Proxy origin regression suite: `npm.cmd run test:proxy` passed **13 tests**. This uses the installed Node 24 runtime, which supports TypeScript source in Node tests.
- Rendered website checked in Brave at desktop size, 375px mobile and 768px tablet: no document overflow; mobile tables scroll within their containers. Hero, workspace metrics and navigation were visually inspected.
- Mobile menu: closed navigation is inert; opening moves keyboard focus into navigation; Escape closes it and restores focus to the opener.
- The effects control pauses the CSS illustration and WebGL background and cancels spotlight animation frames. System reduced motion is observed dynamically. Browser verification confirmed the global paused state and paused orbit animation.
- Explicit **Explore the demo** completed through the browser → Next proxy → Python API → saved demo workspace → rendered overview, showing 35 synthetic articles, 128 market observations and 3 saved runs. No real provider or model requests were made.
- **Open saved evidence** retrieved and rendered a retained case with the source passages, evidence score, coverage and recorded model audit. The import form and strategy lab were also inspected in the browser; the lab correctly showed zero qualifying pre-2021 bars for the synthetic demo.
- Browser console contained no warnings or errors at the verified overview checkpoint.
- Separate Herdr agents implemented the shared theme and performed a read-only implementation review. The review identified and cleared fixes for WebGL Strict Mode cleanup, spotlight pause, and mobile keyboard navigation.

## Proxy correction

Browser integration exposed an existing bug: NextURL normalizes `127.0.0.1` to `localhost`, so comparing a browser Origin directly to `request.nextUrl.origin` rejected legitimate requests from the documented local address. The proxy now checks the original Host, scheme and configured port, restricting browser mutations to matching loopback origins. Different schemes, ports, aliases, remote hosts, opaque origins and malformed hosts remain rejected. Actual HTTP verification observed a same-origin request reach validation (422 for an intentionally empty payload) while mismatched origins received 403.

## Scope

The synthetic demo is a software demonstration. Provider connectivity, predictive quality and production multi-user operation remain outside this verification. Strategy history still ends on 2020-12-31; the bundled 2026 demo is not substituted for historical strategy data. The original Streamlit browser-verification notes describe earlier checkpoints and are not claims about this Next.js verification.

Source and licensing information is in `web/app/_components/react-bits/README.md` and `LICENSE.md`.
# Uniform Crypto Helper design revision

## Light/dark modes and guided research update

The header now includes an accessible sun/moon toggle. A script before the first paint applies the saved preference or follows the operating system on a first visit. Explicit choices persist locally, synchronize across tabs, and continue to work for the current tab if browser storage is blocked. Shared semantic colors cover all eight views, native inputs, evidence tables, SVG charts, local Lightweight Charts and the separately enabled hosted widget.

The overview now explains the source → event → retained-result workflow through three keyboard-accessible React Bits SpotlightCard links and a static Aurora accent. Workflow hints reflect saved workspace data. Empty event/result views and successful imports provide direct next-step links that retain workspace/universe selection. The manual article form opens for an empty inbox; analysis options explain replay versus configured model requests. No provider/model calls, dependency installations or Python changes were required.

Validation for this update: TypeScript/ESLint and production build passed; all **25 Node tests** passed (12 theme/persistence/contrast tests and 13 existing request-origin tests). Text, chart-line and focus contrast thresholds are checked in both palettes. Browser/devserver runs were reserved for the coordinator by the task's earlier instruction, so the rendered checks elsewhere in this document describe earlier checkpoints rather than visual verification of these new modes.

The shared `crypto-system.css` applies the supplied Zajno Crypto Helper reference across all eight sections: charcoal surfaces, inset controls, dimensional lime actions, gold/lime local charts, matching navigation, typography, borders, and tables. All seven workflow pages now use a semantic, factual `WorkspaceSummary` band. Existing research actions and data provenance are preserved.

Validation: TypeScript, ESLint and production build passed. All eight sections were visited at desktop and narrow phone viewport sizes; no document horizontal overflow was found. Fixed the narrow header's wrapping title. Overview chart explicitly loaded 16 saved observations. Desktop research, strategy, imports and connections screens were visually reviewed. Screenshots are in `scratch/fintech-preview/crypto-*.jpg`. A transient HMR missing-stylesheet message occurred while the stylesheet was being created; the subsequent successful build and rendered pages confirm resolution.

