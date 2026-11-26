# Diagnostics and release evidence

Start here when something stops working. The directory contains the troubleshooting runbook, a read-only doctor, historical diagnostic records, and selected release evidence. Runtime source and tests remain in their normal application directories.

| Path | Purpose | Committed? |
|---|---|---|
| [RUNBOOK.md](RUNBOOK.md) | Diagnose provider, persistence, website and deployment problems | Yes |
| [doctor.py](doctor.py) | Export package versions, configuration presence flags and optional database counts | Yes |
| [evidence/2026-11-26/](evidence/2026-11-26/) | Sanitized redeploy proof and desktop/mobile UI previews | Yes |
| [history/](history/) | Earlier implementation, website verification and UX audit records | Yes; historical findings may be superseded |
| `local/` | Full test output, scratch exports, copied test databases and private troubleshooting artifacts | **No — ignored by Git and Vercel** |

The 26 November local archive retains the pre-cleanup synthetic demo database, the old root scratch export and the complete persistence/browser verification output. It preserves those records without shipping generated test runs in the bundled fixture.

For the presentation, use [the mentor workflow](../docs/MENTOR_SHOWCASE.md). For optional future extension work, see [the integration ideas](../docs/EXTENSION_INTEGRATION_IDEAS.md).
