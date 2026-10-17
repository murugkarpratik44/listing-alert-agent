---
name: weekly-digest
description: Weekly listing-alert summary. Reports the past seven days of listings by area and bedrooms (median and lowest price, comparison with market averages), the best five matches, price changes and re-lists, and pipeline health, in one plain-text email. Use on the weekly schedule, or when the user asks "how was the market this week?" or "send my weekly summary".
argument-hint: "[state repo] [--end YYYY-MM-DD]"
---

# Weekly digest

Read-only: this skill never changes the state repository or Gmail labels. Rules in `${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/references/security.md` apply.

## Steps

1. Find the state repository (cloned in the session, or ask). Run `laa.py validate <state>`; stop and report if it fails.
2. Work out the week. Scheduled run: the seven days ending yesterday, in `owner.timezone`. On request: ask only if the user implies a different week.
3. Run:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" digest <state> --end <YYYY-MM-DD> \
     --pack-dir "${CLAUDE_PLUGIN_ROOT}/packs/<pack from sources.yaml>"
   ```
   Output: `subject`, `body`, `html`, `notification`.
4. Write **one short paragraph** (two to four sentences) from the figures in `body` only: for example which area had the most affordable listings, whether supply rose or fell, and one practical suggestion (such as "Kildare 2-beds are going for about the market average; arrange viewings for the top two"). Do not add figures that are not in the body. Plain text, no Markdown. If `goal.move_by` is set, mention how many weeks remain.
5. Run the same command again with `--insight "<your paragraph>"`. The engine places it under "What this means" in both versions and escapes it.
6. Send one email with the Gmail connector to `owner.email`, plus `alerts.digest_cc` if set: subject `subject`, `htmlBody` = `html`, `body` = `body`, both unchanged. If this is not the scheduled day or was requested as a test, prefix the subject with `[TEST] `.
7. Finish with `notification` as the final line.

## Notes

- Fewer than two weeks of history: the body says so; do not invent a trend.
- The digest ends with pipeline health (runs, emails read, last listing per source). If any source has had no listing all week, say so in the paragraph and suggest the user checks that site's saved searches.
- In the first week of each month the digest reminds the user to check their saved searches are still on, plus any lines in `alerts.monthly_reminders`.
