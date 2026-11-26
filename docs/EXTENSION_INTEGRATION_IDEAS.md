# Recommended extension integration

The extension should accompany a news page; the website remains the detailed research workspace. These ideas are proposals, not shipped features. Current version 1.5 previews saved assessments, opens Portfolio, and routes optional Upstox sign-in.

| Priority | Feature | Workflow | Value |
|---|---|---|---|
| 1 | Analyse selected news | Highlight a passage → context menu → editable website draft → confirm source/publication time → save and analyse. | Strongest mentor demonstration of the extension's purpose. |
| 2 | Confirmed company recognition | Invoke the extension on a supported stock page → confirm the proposed ticker → open matching holdings or research. | Useful context with a small, testable supported-site scope. |
| 3 | Research side panel | Open a panel with paper cash/equity, quote timestamps and the selected company's saved evidence → open full case on the website. | Persistent context beside the original article. |

First improve the popup: remember website/workspace selection, distinguish empty real data from a recorded demo, distinguish sign-in failure from network/service errors, and replace the full-workspace download with a bounded summary response.

For capture, use the selected passage as an excerpt, preserve the page URL, and record capture time as first-seen time. Ask for publication time when unavailable. Transfer a bounded draft through a deliberate handoff with an ID; do not place article text or private holdings in query strings. The website still requires explicit import/analysis confirmation and preserves cutoff eligibility.

Chrome's [contextMenus API](https://developer.chrome.com/docs/extensions/reference/api/contextMenus) supplies user-invoked selection context. Use [activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab) for temporary page access when needed; script extraction additionally needs [scripting](https://developer.chrome.com/docs/extensions/reference/api/scripting). Avoid broad browsing-history or all-site permissions.

The [Side Panel API](https://developer.chrome.com/docs/extensions/reference/api/sidePanel) supports persistent companion UI. A panel does not itself authorize reading every newly visited page. Programmatic opening requires a user action. The current popup also matters: [action.onClicked](https://developer.chrome.com/docs/extensions/reference/api/action) does not fire while an action popup is configured; use an explicit panel button or deliberately change the toolbar interaction.

The current research proxy rejects cross-origin writes. Host permission permits extension network access but does not override the application's origin policy. Design a narrow authenticated read/summary contract, or retain live refresh on the website; do not broadly loosen write-origin checks. See [Chrome network requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests).

Current production is a private workspace behind Vercel project authentication, shared by authorized project visitors. Per-user real-holdings summaries require explicit application identity and ownership isolation before exposing them through a future extension API.

Keep the existing conceptual broker flow: extension → website → Upstox-hosted login → server-side authorization-code exchange → website preview → explicit import confirmation. Never collect PINs/OTPs or store broker tokens in the extension. See [Upstox authentication](https://upstox.com/developer/api-documentation/authentication/).

Recommended implementation order: popup clarity and deep links, selected-news capture with confirmed ticker matching, then a portfolio/evidence side panel. Keep TradingView charts on the website and use Upstox quotes for paper valuation.
