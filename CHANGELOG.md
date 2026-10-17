# Changelog

All notable changes are recorded here. Format: version, date, changes. Versions follow semantic versioning.

## 0.3.0 – 2026-10-17

- New skill `dashboard`: a private claude.ai dashboard (Dashboard artifact type) with headline figures, a map of listing areas, a shortlist tracker, a searchable listings table and a chart of alert runs. Alert runs refresh it when something changes and at least once a day; `dashboard.url` and `dashboard.refresh` in the profile.
- Engine: `dashboard-data` exports listings, runs and places as JSON for the dashboard.
- Listing statuses: `new`, `shortlisted`, `contacted`, `viewing`, `applied`, `offer`, `not_for_me`, `rejected`, `let_agreed`, recorded with `feedback --verdict`. The latest entry per listing is its status.
- Cost estimate: `costs.energy_monthly_eur` takes the user's own monthly energy bill (a figure or a range) in place of the BER-based estimate.
- Behaviour tests (`evals/`): ignores instructions inside alert emails, never visits listing sites, setup asks before assuming, viewing pack cites the rules. Run by hand; results in `docs/evals.md`.
- `run-alerts` forbids browsers by name and now also triggers on pasted alert emails and on "check Daft.ie"-type requests, after the first eval runs.
- Maintenance: `tools/maintenance_check.py` (tests, checks, stale dates, links to verify, benchmark period) for a monthly scheduled check that emails the maintainer and opens a GitHub issue.
- Releases: a GitHub Actions workflow creates the GitHub release from the CHANGELOG when the version in `plugin.json` changes.

## 0.2.0 – 2026-10-17

- New skills: `compare` (2–5 listings side by side with a recommendation), `viewing-pack` (draft enquiry the user sends, questions, documents, red flags, money rules), `tune` (records verdicts, suggests precise rule changes, applies only with agreement).
- Monthly cost estimate on every card: rent share + energy (BER band midpoint × floor area × price) + commute (km × trips × cost per km, or fares). User prices first, sourced pack defaults otherwise (SEAI, CSO, Revenue for Ireland).
- Travel score weights places by trips per week; areas can override trips (`anchor_trips`).
- Storage options: Google Drive folder (versioned files, nothing deleted, `--write-if-changed`) and local folder, alongside GitHub.
- Travel cache: geocodes cached, county-level and shared-point results rejected, clean stop on quota.
- Engine: compare, feedback and tune subcommands; CSV files gain new columns without losing rows.
- Ireland pack: sourced viewing checklist (RTB, SEAI, Garda advice) and cost defaults.
- CI actions moved to v6.

## 0.1.1 – 2026-10-17

- Areas can override an important place's travel limit (`anchor_limits`), for example a longer limit for a weekly-commute area, or `null` to leave that place out of the travel score.
- Areas can carry a `commute_note` shown on every listing in the area.
- Directions links use an important place's coordinates when known, as map search can misplace business-park addresses.
- MyHome.ie parser notes: the first cell of the details row is the photo count.
- Setup guidance on checking geocodes and the free geocoding quota, from the first real setup.
- Alert subject times are shown in the owner's time zone (scheduled runs use UTC).
- HTML alert email: cards per listing with fit badge, coloured reason chips, facts table, flag chips and buttons; compact rows for over budget and check location. The plain-text version is still sent alongside.
- HTML weekly digest in the same style; Claude's short "What this means" paragraph is passed to the engine (`--insight`) and escaped.
- `alerts.monthly_reminders`: extra lines in the first digest of each month.

## 0.1.0 – 2026-10-17

- Skills: `setup`, `run-alerts`, `weekly-digest`, `doctor`; optional `alert-runner` agent.
- Engine `laa.py`: rent normalisation, place matching, travel-time cache (openrouteservice), areas, occupancy-based budget tiers, RTB benchmark lookup, fit score with reasons, duplicate, price-change and re-list detection, risk flags with scam score cap, plain-text alert and weekly digest, daily health checks, quiet hours.
- Pack `ie-rentals` (Daft.ie, MyHome.ie, RTB 2025 averages, Dublin postal districts) and pack `_template`.
- JSON schemas for profile, sources, places and extracted listings.
- Tests on synthetic data; pack and directory pre-submission checks; CI workflow.
