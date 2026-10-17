# Troubleshoot with the doctor

Ask Claude: **"Run the listing alert doctor."** It checks the following and explains each problem with its fix:

- connectors;
- your settings;
- recent alert emails per site;
- emails it could not read;
- the schedule;
- the Gmail labels.

It changes nothing until you agree.

## Common problems

| What you see | Likely cause | Fix |
|---|---|---|
| No alert emails at all | Nothing new matched, or the sites' emails are not arriving | Check Gmail for the sites' own alerts (Spam too). See [set-up-site-alerts.md](set-up-site-alerts.md). |
| Sites' emails arrive but are never labelled `Listing Alerts/Processed` | The routine is off, has no Gmail connector, or the sender address doesn't match `sources.yaml` | Open the routine and check it is on and has Gmail. The doctor compares the actual sender with your settings. |
| "Could not read" in an alert | The site changed its email layout | The doctor shows what changed. Open a "format changed" issue with a copy of the email that has names, phone numbers, emails and exact addresses removed. |
| Travel times missing | No openrouteservice key at setup, or a place could not be found precisely | Re-run setup's travel step with a key. Places the lookup could only match to a whole county are left out on purpose. |
| Two alerts for the same run | A run was started twice within 10 minutes | The second save is skipped automatically. No action needed. |
| Dashboard looks out of date | Quiet day; it refreshes when something changes and at least daily | Ask "refresh my listing dashboard". |
| Phone notification but no email | Nothing was new enough to email; the notification says so | No action needed. |

## Read a run's own log

Each routine run is a full session. Open it from [claude.ai/code/routines](https://claude.ai/code/routines) → the routine → the run. You can see every step, including any tool error. A green status means only that the session ran, not that the task succeeded.

## Still stuck

Open an issue on the [plugin repository](https://github.com/murugkarpratik44/listing-alert-agent/issues) with:

- the doctor's report;
- your plugin version;
- where you run it (Claude app, Claude Code, routine).

Remove personal details first.
