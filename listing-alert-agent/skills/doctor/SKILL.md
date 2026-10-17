---
name: doctor
description: Health check for listing-alert-agent. Checks connectors, config validity, Gmail labels, alert senders, travel-time cache age, recent runs and parsing failures, then explains each problem and its fix in plain words. Use when alerts stop arriving, look wrong, or the user asks "is my listing alert working?".
argument-hint: "[state repo]"
---

# Doctor

Diagnose, explain, and propose fixes. Do not change anything without the user's agreement; then make only the agreed change.

## Checks

Run them in this order and keep a list of findings (OK / warning / problem).

1. **Connectors.** Gmail: run a search. GitHub (or the state folder): read `config/profile.yaml`.
2. **Config.** `python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" validate <state>`. Explain each problem in plain words, with the field and the fix.
3. **Engine report.** `python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" doctor <state>`: travel cache size and age, runs, last listing per source.
4. **Alert emails per source.** For each source in `sources.yaml`, search Gmail for the newest email from its senders in the last 14 days (any label).
   - None: the saved search may be off, the account email may differ, or emails go to Spam. Walk through the pack's `sources/<id>.md` "If no alerts arrive" list. Also search Spam: `in:spam from:<domain>`.
   - Emails present but never labelled `Listing Alerts/Processed`: the schedule is not running, or the sender address does not match. Compare the actual sender with `sources.yaml`.
   - A wildcard sender (`*@domain`) and a real alert seen: propose the exact address for `sources.yaml`.
5. **Unread layouts.** Count emails labelled `Listing Alerts/Could not read` in the last 14 days. If any, open one, compare it with the pack's parser notes and say what changed. Suggest opening a "format changed" issue on the plugin repository with a redacted copy (remove names, phone numbers, email addresses and exact addresses).
6. **Schedule.** The engine report shows the last run. If it is older than three hours, ask the user to check the routine or scheduled task is on and has the Gmail connector.
7. **Labels.** Both labels exist.

## Report

Plain words, shortest first:

```
Everything working: <yes/no>
Problems (fix these first):
- <what is wrong> – <why it matters> – <exact fix>
Warnings:
- ...
Checked: <list of checks that passed>
```

Then offer to make the fixes that are in Claude's reach (edit `sources.yaml`, create a label, rebuild the travel cache) and give exact steps for the ones only the user can do (site settings, Gmail filters, routine settings).
