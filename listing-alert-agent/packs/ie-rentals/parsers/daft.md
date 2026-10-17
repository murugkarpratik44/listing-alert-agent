# Daft.ie alert email – parser notes

Status: **layout to be confirmed.** No real Daft.ie alert email has been inspected yet. The notes below describe what to extract and how to behave until the layout is confirmed. When a real email is seen, the maintainer updates this file and replaces the fixture with a synthetic copy of the real structure.

## Identify

- Sender: an `@daft.ie` address. Setup records the exact address from the first alert email.
- Subject usually mentions new properties for a saved search.
- Not alerts: account, marketing and "price report" emails. Do not read or label them.

## What to extract per listing

| Field | Expect | Notes |
|---|---|---|
| `rent_amount`, `rent_period` | A price such as `€1,750 per month` or `€400 per week` | Weekly is converted by the engine (× 52 / 12). Ranges: lower figure, `rent_is_range: true`. |
| `address` | Address line or listing title | Keep "Co." and county or Dublin postal district as shown. |
| `bedrooms`, `bathrooms` | "2 Bed", "1 Bath" | Missing means null. |
| `property_type` | Apartment, House, Duplex, Studio, Flat | |
| `url` | Link to the listing | Copy as it appears; the engine removes tracking. |

## Ignore

- Agent or landlord names, phone numbers and email addresses.
- Promoted or "you may also like" blocks.

## Failure signs

If no listing fields can be found, report the email under "Could not read" with its Gmail link and suggest the user opens a "format changed" issue with a redacted sample.
