# Writing a pack

A pack teaches listing-alert-agent about one country and one kind of listing: which sites send alert emails, how to read those emails, which places to use, and (optionally) open market averages.

## Rules

1. **Email only.** A pack must never tell Claude to visit, fetch or search a listing site. Users create saved-search alerts themselves; the plugin reads the emails.
2. **Check the terms.** Read each site's terms of use and record the date in `terms_checked`. If the terms forbid reading alert emails with software, leave the site out.
3. **No personal data.** Fixtures are invented. Never commit a real alert email, a real person's name, phone number or email address, or anyone's home or work address.
4. **Open data only.** A benchmark file must come from a source whose licence allows redistribution (for example CC BY 4.0). Say what it measures and its limits.
5. **Date everything.** Every note that can go out of date carries a "checked" date and a link to the source.

## Files

| File | Purpose |
|---|---|
| `pack.yaml` | The interface. Every path in it must exist. |
| `sources/<id>.md` | Steps a user follows to create saved-search alerts on the site, plus what to do when no alerts arrive. |
| `parsers/<id>.md` | Where each listing field sits in the alert email, what to ignore, and failure signs. Mark the status: confirmed from real emails (with date) or "layout to be confirmed". |
| `places/README.md` | How to choose search places in this country (towns, districts, postcodes) and any spelling variants. |
| `benchmark/<file>.csv` + `benchmark/README.md` | Optional market averages with columns `location,property_type,bedrooms,value,n_periods`. |
| `fixtures/<id>-alert-sample.txt` | A synthetic email with the same structure as the real one. First line must start with `SYNTHETIC TEST EMAIL`. |
| `fixtures/expected-extraction.json` | The listing JSON Claude should extract from each fixture (see `schemas/listing.schema.json`). |

## Checklist before opening a pull request

- [ ] `python tools/check_packs.py` passes (paths exist, fixtures marked synthetic, extraction JSON valid).
- [ ] `python -m unittest discover -s tests` passes.
- [ ] Each source has `terms_checked` within the last 12 months.
- [ ] No real personal data anywhere in the pack.
