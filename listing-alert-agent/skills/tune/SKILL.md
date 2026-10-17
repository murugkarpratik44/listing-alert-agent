---
name: tune
description: Record the user's verdicts on listings ("not for me - too far", "yes, viewing booked") and turn patterns in them into precise, optional changes to their alert rules, applied only after they agree. Use when the user gives feedback on a listing, or asks to adjust, tighten or loosen their alerts.
argument-hint: "[<listing> yes|maybe|no <reason>] | [suggest]"
---

# Tune alerts

## Record a verdict

When the user reacts to a listing, record it (one call per listing):

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" feedback <state> "<link or address words>" \
  --verdict yes|maybe|no --reason "<their reason in a few words>"
```

Use their words for the reason ("too far", "ground floor", "no parking", "too expensive"). If the listing is not found, say the plugin only knows listings it has alerted about. Commit `data/feedback.csv` with message `Feedback: <verdict> <short address>`.

## Suggest changes

After three or more verdicts, or when the user asks:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" tune <state>
```

The output lists findings and exact proposed changes, for example `areas[athlone].max_minutes: 45 -> 34` or `criteria.deal_breakers: add 'ground floor'`. For each suggestion:

1. Explain it in one sentence with the evidence ("You turned down three places as too far; all were 35 minutes or more from the office").
2. Ask whether to apply it. Offer an alternative where sensible (a smaller change, or a must-have instead of a deal-breaker).
3. Apply only what the user agrees to: edit `config/profile.yaml`, run `laa.py validate <state>`, fix any problem, update `SETUP-SUMMARY.md`, and commit `Tune: <change>`.

The user can also ask for direct changes ("make the budget €1,300", "stop showing over-budget listings"); make them the same way: say what will change, confirm, apply, validate, commit.

## Notes

- Never apply a suggestion without the user's agreement in this conversation.
- Deal-breakers and must-haves only act when an alert email mentions them; say so when adding one.
- A change takes effect from the next scheduled run.
