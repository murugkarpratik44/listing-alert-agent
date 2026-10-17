# Example.com alert email – parser notes

Status: layout to be confirmed

## Identify

- Sender: `alerts@example.com`
- Subject: describe the pattern.

## Fields

| Field | Where it is | Notes |
|---|---|---|
| `rent_amount`, `rent_period` | | |
| `address` | | |
| `bedrooms`, `bathrooms` | | Missing means null. |
| `property_type` | | |
| `url` | | Copy as it appears; the engine removes tracking. |

## Ignore

- Names, phone numbers and email addresses of agents, landlords or sellers.
- Promoted or "similar" listings.

## Failure signs

If no listing fields can be found, report the email under "Could not read".
