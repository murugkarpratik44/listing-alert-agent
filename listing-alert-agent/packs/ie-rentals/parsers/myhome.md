# MyHome.ie alert email – parser notes

Status: layout confirmed from real alert emails, 2026-10-16. Fixture: `fixtures/myhome-alert-sample.txt` (synthetic, same structure).

## Identify

- Sender: `notifications@myhome.ie`
- Subject: `<address> - €<rent> / month` for one match. Emails with several matches repeat the listing block in the body.
- Body opens with "Property Alert | <date>" and "<site> found new matches for your <search name> saved search".

## Listing block (repeats per listing)

| Field | Where it is | Notes |
|---|---|---|
| `rent_amount`, `rent_period` | Heading line such as `€1,850 / month` | `/ week` means weekly. "From €x" or a range: use the lower figure and set `rent_is_range: true`. |
| `address` | Line under the price | Full address as shown, including "Co." and county. |
| `bedrooms`, `bathrooms`, `floor_area_m2`, `property_type` | A row of short cells: **photo count**, beds, baths, m², type, for example `14 · 2 · 2 · 72m² · Apartment` (shown as table cells) | The first number is the number of photos, not bedrooms. Cells can be empty (`13 · 2 · 2 · (empty) · Apartment` has no floor area). Empty means null, not zero. |
| `url` | The listing link (button or address link) | Links are wrapped in a tracking redirect (`...awstrack.me/L0/https:%2F%2Fwww.myhome.ie%2Frentals%2Fbrochure%2F...`). Copy the link as it appears; the engine unwraps it and removes `utm_` parameters. |
| `energy_rating` | Sometimes shown as "BER: B2" | Optional. |

## Ignore

- Agent or landlord names, phone numbers and email addresses: never extract them.
- "Similar properties" or "recommended" blocks that are not part of the saved-search results. If unsure, extract the listing and add nothing to `matched_*` fields.
- Unsubscribe and settings links.

## Failure signs

If the body has none of the fields above, do not guess: report the email under "Could not read" with its Gmail link.
