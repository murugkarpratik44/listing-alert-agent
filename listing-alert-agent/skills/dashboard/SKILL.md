---
name: dashboard
description: Create or refresh the user's private listing dashboard - a page with headline figures, a map of where listings are, a shortlist tracker, a searchable table of every alerted listing and a chart of alert runs. Use when the user asks for a dashboard or an overview of their search, and from alert runs to keep it current.
argument-hint: "[create | refresh]"
---

# Listing dashboard

A private claude.ai page built from the Dashboard artifact type. It shows only what the state storage holds: listing facts, statuses, run counts and place coordinates. No contact details exist to show.

## Create (once, with the user)

1. Check the Artifact tool is available and offers the Dashboard type (Artifact `quickstart` with intent `other`). If not, say the dashboard needs the claude.ai artifacts feature and stop.
2. Export the data:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" dashboard-data <state> --out <tmp>/dash
   ```
   This writes `listings.json`, `runs.json` and `places.json`.
3. Create the dashboard from the Dashboard type (title: "Rental search", or the user's own name for it) and follow the type's instructions:
   - upload the three JSON files as assets;
   - write `dash/meta`, one `datasets/<id>` per file (`listings`, `runs`, `places`) with a file source, `updated` and `schedule` ("Refreshed by the alert run when something changes, and at least once a day"), `staleAfterHours: 48` (places: 2160);
   - write `files/index.html` from `page.html` in this folder, unchanged.
4. Record the link in `config/profile.yaml` as `dashboard: {url: <link>, refresh: on_change}`, validate and save the state.
5. Tell the user what the page shows, that it is private until they share it, and that statuses change when they tell Claude (for example "mark Example Court as viewing", which runs `laa.py feedback ... --verdict viewing`).

## Refresh (from an alert run or on request)

Run after `process --write` and before the state is committed, when `dashboard.url` is set and either this run reported listings, a status changed, or the dashboard was not refreshed today (its `updated.at`). Skip when `refresh: off`.

1. Export as in step 2 above.
2. Upload `listings.json` and `runs.json` as new assets of the dashboard (`places.json` only when the travel-time table changed).
3. Read `datasets/listings` and `datasets/runs`, then `update` each with the new `source.url`, `source.name` and `updated: {at, by: "listing-alert-agent"}`, pinned to the version you read.
4. Delete the asset each dataset pointed to before, once nothing references it.
5. First check the Artifact and ArtifactData tools are available (load them with tool search if they are deferred). If they are not, skip the refresh. Either way, give the alert run its outcome for the commit message: `dashboard refreshed` or `dashboard skipped: <reason>`.

## Statuses

`new`, `shortlisted`, `contacted`, `viewing`, `applied`, `offer`, `not_for_me`, `rejected`, `let_agreed`. Recorded with `laa.py feedback <state> "<listing>" --verdict <status> --reason "<note>"`; `yes` counts as shortlisted, `no` as not for me. The latest entry per listing is its status.
