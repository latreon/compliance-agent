# Security Policy

## Supported Versions

The latest released `0.1.x` version on PyPI receives security fixes.

## Reporting a Vulnerability

Please report security issues privately rather than opening a public issue.

- Use GitHub's **[Private vulnerability reporting](https://github.com/latreon/compliance-agent/security/advisories/new)**, or
- Email the maintainer at `ferdakerim@gmail.com` with the subject
  `SECURITY: compliance-agent`.

Include a description, reproduction steps, and the affected version. You can
expect an initial acknowledgement within a few days. Please give a reasonable
window to release a fix before any public disclosure.

## Scope

ComplianceAgent runs locally, reads project files read-only, and (unless
disabled) makes one cached HTTPS request to PyPI for update checks. Relevant
concerns include unsafe file handling, path traversal in `recommend`/`report`
output, or unsafe deserialization. It does not execute scanned code.
