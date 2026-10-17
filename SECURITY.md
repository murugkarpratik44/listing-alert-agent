# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security → Report a vulnerability** on this repository. Do not open a public issue. Include the plugin version, the surface (Chat, Cowork, Claude Code, routine) and steps to reproduce, with personal details removed.

You can expect an acknowledgement within 7 days.

## In scope

- Prompt injection through alert email content that changes recipients, files or tool use.
- Any path by which the plugin could email someone other than the configured owner (or the single digest copy address).
- Secrets or third-party personal data written to the state repository, emails or logs.
- Any behaviour that visits listing websites.

## Design controls

See `listing-alert-agent/skills/run-alerts/references/security.md`.
