# Scheduling

Two schedules: the alert run (hourly) and the weekly digest. Both run as the user, read Gmail through the connector and write to the user's private state repository.

Facts that shape this (Claude Code routines documentation, checked 2026-10-17):
- Routines run in Anthropic's cloud, at most once an hour, and are a research preview.
- The cloud environment's default network setting allows a list of approved domains. Gmail and GitHub connectors are not affected. Listing sites are never needed.

## Option 1 – Routine (any surface; recommended)

Create at https://claude.ai/code/routines, or with `/schedule` in Claude Code.

| Setting | Alert run | Weekly digest |
|---|---|---|
| Repositories | the user's state repository, plus the plugin repository if the picker offers it | same |
| Connectors | Gmail | same |
| Schedule | Hourly | Weekly, on the day and time in `alerts.digest` |
| Prompt | below | below |

### Making the plugin available inside the routine

A cloud session does not install plugins, even ones a repository turns on in `.claude/settings.json` (Claude Code cloud environments documentation, "What carries over from your setup", checked 2026-10-17). The routine therefore gets the plugin files in one of two ways:

1. **Attach the plugin repository** (`murugkarpratik44/listing-alert-agent`) as a second repository, if the routine's repository picker offers it. A user can also fork it and attach the fork (sync the fork occasionally).
2. **Download the runtime files**: the prompt fetches the files listed in `listing-alert-agent/runtime-manifest.txt` from `raw.githubusercontent.com`, which the default network setting allows for public repositories.

### Alert run prompt

```text
Run one listing-alert-agent alert pass for the state repository <owner>/<repo> in this session.
Plugin files: if a listing-alert-agent repository is in this session, use its listing-alert-agent/ folder as the
plugin root. Otherwise download every path in
https://raw.githubusercontent.com/murugkarpratik44/listing-alert-agent/main/listing-alert-agent/runtime-manifest.txt
from https://raw.githubusercontent.com/murugkarpratik44/listing-alert-agent/main/listing-alert-agent/<path>
into ./laa-plugin/<path> and use ./laa-plugin as the plugin root.
Then follow <plugin root>/skills/run-alerts/SKILL.md exactly, reading ${CLAUDE_PLUGIN_ROOT} as the plugin root.
Send alerts only to the owner email in config/profile.yaml. Never visit listing websites.
Do not commit the plugin files to the state repository.
Finish with the one-line notification the skill describes.
```

### Weekly digest prompt

```text
Run the listing-alert-agent weekly digest for the state repository <owner>/<repo> in this session.
Get the plugin files exactly as in the alert run prompt, then follow <plugin root>/skills/weekly-digest/SKILL.md,
reading ${CLAUDE_PLUGIN_ROOT} as the plugin root. Do not modify the state repository.
Finish with the one-line notification the skill describes.
```

The state template's `.claude/settings.json` only helps on the user's own computer: Claude Code offers to install the plugin when the repository folder is trusted.

Notifications: turn on push notifications for the routine in its settings so the final line reaches the user's phone.

## Option 2 – Scheduled task in the Claude desktop app

Use the app's scheduled tasks with the same prompts. Runs only while the computer is on and the app is open; good for local-folder storage (v0.2).

## Check the first run

After creating the schedule, start one run manually (routines have a "Run now" option). Confirm: an email arrived (or the run reported "No new matching listings"), and `data/run-log.csv` has a new row. If not, run `doctor`.

## Instant notice from the sites themselves

Scheduled runs are at most hourly. For the fastest notice, the user can let Gmail notify them as soon as a site's own alert arrives:

1. Gmail → search box → "Show search options".
2. From: `<sender 1> OR <sender 2>` (exact addresses from `sources.yaml`).
3. "Create filter" → tick **Never send it to Spam**, **Always mark it as important**, and optionally **Star it**.
4. In the Gmail phone app, set notifications to "High priority only" if the user wants only important mail to buzz.

The plugin's hourly alert then adds the ranking, travel times and market comparison.
