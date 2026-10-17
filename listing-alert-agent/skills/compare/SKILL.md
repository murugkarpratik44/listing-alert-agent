---
name: compare
description: Compare 2 to 5 listings the user has been alerted about, side by side on cost to them, travel, value against the market, fit and risks, and end with a clear recommendation and trade-offs. Use when the user says "compare these", "which is better, X or Y", or lists several listings they are considering.
argument-hint: "<listing link or address words> <another> [...]"
---

# Compare listings

Read-only. Rules in `${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/references/security.md` apply.

## Steps

1. Identify the listings. Accept links or a few words from each address. If the user's words are ambiguous, ask which one they mean. Two to five listings; if more, ask which five.
2. Run:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" compare <state> "<ref 1>" "<ref 2>" ...
   ```
   Output: `listings` (facts per listing), `best` (which listing leads on each criterion), `not_found`.
3. If anything is in `not_found`, say so. The plugin only knows listings it has alerted about; never look a listing up on the website.
4. Show one table, listings as columns, rows in this order: Rent (your share) · Estimated monthly cost · Beds / baths · Type · Area · Travel · Versus market · Fit score · Flags · Link. Bold the leading value in each row, using `best`.
5. Recommend, in three to five sentences:
   - the overall pick and the one or two facts that decide it;
   - "If <criterion> matters most, choose <other listing> because <fact>" for each real trade-off;
   - anything to check before deciding (flags, missing BER or bathrooms, "possible scam").
   Use only facts from the output. Say when a figure is an estimate.
6. Offer next steps: a viewing pack for the pick (`viewing-pack`), or recording a verdict ("not for me – too far") with `tune`.

## Notes

- Travel times are area-level from the listing's town or district; mention the directions link for exact trips.
- Market comparison is against average agreed rents for registered tenancies, not asking rents.
