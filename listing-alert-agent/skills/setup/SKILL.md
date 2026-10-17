---
name: setup
description: Guided setup for listing-alert-agent. Interviews the user about what they are looking for (a rental, a home, a job, a car), the places that matter to them and how they travel, budget and deal-breakers; then creates their config, a travel-time cache, Gmail labels and a schedule, and sends a test alert. Use when the user wants to start or redo listing alerts, or says "set up listing alerts".
argument-hint: "[state repo, e.g. you/my-listing-alerts]"
---

# Set up listing alerts

Goal: in about 15 minutes, take a user from nothing to a tested, scheduled alert, by asking questions rather than asking them to edit files. Works for technical and non-technical users: explain each step in plain words, keep jargon out of the conversation, and show defaults for the user to confirm.

Read `${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/references/security.md` first. The same rules apply here.

## How to run the interview

- Ask **one block at a time** (`references/questionnaire.md`), using the question tool when available. Offer sensible defaults, marked as defaults.
- Never assume a value that changes results (budget, places, deal-breakers, who shares the cost). Ask.
- After each block, play back what you understood in one or two lines and ask the user to confirm.
- Keep a running draft of `profile.yaml`, `sources.yaml` and `places.yaml` in memory; write files only at step 5.
- If the user stops part-way, save what is confirmed and tell them how to resume ("run setup again; I will pick up from places").

## Steps

### 1. Check prerequisites
Confirm what is connected; do not ask the user to check things you can check yourself.

| Needed | How to check | If missing |
|---|---|---|
| Gmail connector | Try a Gmail search for one recent email | Ask the user to connect Gmail in Claude settings → Connectors |
| Storage choice | Ask: GitHub (default), Google Drive or a local folder; see `references/storage.md` | – |
| GitHub or Google Drive connector, for those options | List repositories / search Drive | Ask the user to connect it in Claude settings and, for GitHub, to grant the Claude app access to the new repository |
| State storage | `references/storage.md` | Walk them through creating it |
| Python 3.10+ with PyYAML | `python3 -c "import yaml"` | Use the manual fallback in `run-alerts/references/pipeline.md`; mention it once |

### 2. Interview
Blocks 1–6 of `references/questionnaire.md`: goal, the thing, places that matter, search areas, money, alerts.

### 3. Sources and saved searches (block 7)
1. Pick the pack from goal and country (`${CLAUDE_PLUGIN_ROOT}/packs/`). If no pack fits, use `_template` rules: ask which sites they use and their alert sender addresses, and say parsing may be less reliable until a pack exists.
2. For each source the user wants, give the steps from the pack's `sources/<id>.md`, matched to their areas and criteria (for example, "Create one saved search for County Kildare, 1–2 bedrooms, no price limit"). The user creates the searches; you never visit the sites.
3. Search Gmail for existing alerts from each source to confirm the exact sender address. Use the exact address in `sources.yaml`; keep the pack's wildcard only until the first alert arrives.

### 4. Places and travel times
Follow `references/geo-setup.md`:
1. Confirm each important place's location with a Google Maps link the user can open.
2. Build `search_places` from the search areas and the pack's places guidance; show the list for confirmation.
3. Build `data/travel-cache.csv` with openrouteservice if the user has a free API key and network access allows it; otherwise explain the fallback.
4. Show a short table: each search place × each important place, minutes and km. Ask whether the area limits still look right.

### 5. Write the state
Write `config/profile.yaml`, `config/sources.yaml`, `config/places.yaml` into the state storage (including `storage.type`), then run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" validate <state>
```

Fix every problem it reports before going on. Write `SETUP-SUMMARY.md` (template in `references/questionnaire.md`, end of file). Commit with message `Setup: <date>` and push.

### 6. Gmail
- Create labels `Listing Alerts/Processed` and `Listing Alerts/Could not read` if missing.
- Offer a Gmail filter for instant phone notifications from the sites' own emails (`references/scheduling.md`, "Instant notice"). The user creates the filter; give exact text to paste.

### 7. Test run
Run the `run-alerts` skill in `--dry-run` mode on the pack fixtures. Before parsing, replace the fixture town names with two of the user's own search places so the test shows their real travel times. The test email subject starts with `[TEST]`. Ask the user to confirm it arrived and reads well. Adjust anything they dislike (weights, push tiers, quiet hours) and re-test.

### 8. Schedule
Follow `references/scheduling.md` to create the hourly alert run and the weekly digest on the user's surface, using the prompts given there with their repository name filled in. Confirm the first scheduled run succeeded before you finish (or tell the user when to expect it and how to check).

### 9. Finish
Tell the user, in five lines or fewer: what will happen and when, where the summary is, how to change things ("tell Claude: tune my alerts", v0.2) and how to check health ("run doctor").

## Things to avoid

- Do not store a travel-time API key anywhere. It is used once, from an environment variable.
- Do not create saved searches, accounts or filters on the user's behalf.
- Do not promise instant alerts: scheduled runs are at most hourly. The Gmail filter gives instant notice from the sites themselves.
