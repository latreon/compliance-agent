# ComplianceAgent vs. Consultants vs. Enterprise GRC

These solve different problems, not the same problem at different prices.
Here's what each one actually gives you, honestly compared.

| Dimension | **ComplianceAgent** (free, open source) | Independent consultant (€15,000–€80,000/engagement) | Enterprise GRC platform (€50,000+/year) |
|---|---|---|---|
| **Time to first result** | ~5 seconds — one CLI command against your repo | 2–6 weeks — scoping, interviews, drafted report | Weeks–months — procurement, then onboarding |
| **What it inspects** | Your actual code: AI imports, agent loops, logging, disclosure text, docs on disk | Your organization: contracts, processes, interviews, actual code on request | Your policies: questionnaires, risk registers, vendor attestations |
| **Runs in CI/CD** | Yes — SARIF, GitHub Action, `--fail-on` gate | No — point-in-time report, not a pipeline check | Sometimes — a few offer API/webhook integrations |
| **Update cadence** | Every release, as obligations phase in through 2027 | Per engagement — a snapshot, not continuous | Vendor's roadmap, typically quarterly |
| **Legal certainty** | None claimed — heuristic first pass, always verify manually | High — a named professional stands behind the finding | Medium — policy coverage, not a legal opinion |
| **Best for** | Catching obvious gaps *before* they reach a lawyer's desk | High-risk systems, board sign-off, regulatory inquiries | Org-wide policy tracking across many systems and vendors |

> ComplianceAgent is a static-analysis first pass, not legal advice, and does
> not by itself establish compliance. Use it to triage before you engage a
> consultant — not instead of one.
