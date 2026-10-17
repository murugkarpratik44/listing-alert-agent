# Create the hourly and weekly schedule

Alerts and the weekly summary run as **routines**. A routine is a scheduled Claude session that runs in Anthropic's cloud, so it keeps working when your computer is off. Routines are in research preview and are available on Pro, Max, Team and Enterprise plans. Source: [Routines](https://code.claude.com/docs/en/routines), checked 2026-10-17.

## 1. Open the routine form

Use either of these:

- In a browser, go to [claude.ai/code/routines](https://claude.ai/code/routines) and select **New routine**.
- In Claude Code, run `/schedule`.

## 2. Fill in the alert routine

| Field | Value |
|---|---|
| Name | Listing alerts |
| Prompt | The alert prompt setup printed. The template is in [scheduling.md](../../listing-alert-agent/skills/setup/references/scheduling.md). |
| Repositories | Your state repository (for example `you/my-listing-alerts`). Add `murugkarpratik44/listing-alert-agent` too if the picker offers it. Otherwise the prompt downloads the plugin files itself. |
| Connectors | Gmail. Remove the ones the routine doesn't need. |
| Schedule | Hourly. Pick a minute past the hour, such as :53, because runs set exactly on the hour can start late. To skip the night, set a custom cron with `/schedule update`, for example `53 6-22 * * *` in your time zone. |
| Notifications | Turn on push notifications. The run's last line becomes the phone notification. |

Select **Create**, then **Run now** once to test.

## 3. Fill in the weekly summary routine

Same as above, with these differences:

- the weekly-summary prompt;
- a **Weekly** schedule on the day and time you chose in setup.

## 4. Check the first run

Within a few minutes of **Run now**, check these:

- **Your inbox:** a "Listing alert – …" email arrived, or the run reported "No new matching listings".
- **Your state repository:** it has a new commit `Alert run …`.
- **`data/run-log.csv`:** it has a new row.

If any of these is missing, open the run from the routine page to read what happened, then ask Claude to "run the listing alert doctor".

## Why the plugin repository is attached

A cloud session doesn't install plugins. The routine therefore reads the plugin's files directly from its repository, or downloads the files listed in `runtime-manifest.txt`.

## Running on your own computer instead

The Claude desktop app can also run a scheduled task locally, using the same prompts. It runs only while the computer is on and the app is open. Use it when your settings live in a local folder rather than a GitHub repository.
