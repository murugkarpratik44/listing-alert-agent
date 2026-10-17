# Contributing

Thank you for helping. The most useful contributions are new packs (countries and listing types) and fixes when a site changes its alert email layout.

## Ground rules

1. **Email only.** No code or instructions that visit, fetch, search or scrape listing websites.
2. **No real personal data.** Fixtures are invented. Never commit a real alert email, or any name, phone number, email address or home address.
3. **Open data only** for benchmarks, with the licence and date recorded.
4. **Tests pass** before a pull request:
   ```bash
   pip install pyyaml jsonschema
   python -m unittest discover -s tests
   python tools/check_packs.py
   python tools/check_plugin_folder.py
   claude plugin validate .
   ```

## Adding a pack

Copy `listing-alert-agent/packs/_template` to `listing-alert-agent/packs/<country>-<domain>` and follow its README. Then run `python tools/check_plugin_folder.py --write` to refresh the runtime manifest.

## Changing the engine

`listing-alert-agent/skills/run-alerts/scripts/laa.py` uses only the Python standard library plus PyYAML (jsonschema optional). Add a test in `tests/` for every rule you change, and update `skills/run-alerts/references/pipeline.md` so the manual fallback matches.

## Versioning

Semantic versioning. Raise `version` in `listing-alert-agent/.claude-plugin/plugin.json` and add a `CHANGELOG.md` entry for any change users would notice.
