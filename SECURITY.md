# Security Policy

## Supported Versions

ComplianceAgent is pre-1.0. Security fixes are applied to the latest released
version on PyPI. Please upgrade before reporting (`compliance-agent upgrade`).

| Version | Supported |
|---------|-----------|
| latest `0.1.x` | ✅ |
| older | ❌ |

## Reporting a Vulnerability

**Do not open a public issue for security reports.**

Please report privately via GitHub's
[private vulnerability reporting](https://github.com/latreon/compliance-agent/security/advisories/new)
("Report a vulnerability" under the repository's **Security** tab). If that is
unavailable, email the maintainer at **ferdakerim@gmail.com** with:

- a description of the issue and its impact,
- steps to reproduce (a minimal project or command is ideal),
- affected version (`compliance-agent version`).

You can expect an acknowledgement within a few business days. Once a fix is
released, we are happy to credit reporters who wish to be named.

## Scope & Threat Model

ComplianceAgent reads project files locally and parses them (AST + patterns). It
does **not** execute the code it scans. Relevant considerations:

- **Untrusted input:** the scanner processes arbitrary source files. Parsing or
  resource-exhaustion issues (e.g. crafted files) are in scope.
- **Network:** the only outbound request is an optional PyPI version check
  (opt-out via `--no-update-check`, `COMPLIANCE_AGENT_NO_UPDATE_CHECK`, or
  `NO_UPDATE_NOTIFIER`) and the `upgrade` command, which shells out to your
  package manager without a shell (no injection surface).
- **PDF generation** uses WeasyPrint (system libraries). Report WeasyPrint
  vulnerabilities upstream.

## Not a Legal Compliance Guarantee

This tool provides technical analysis, not legal advice, and does not guarantee
regulatory compliance. See the README disclaimer.
