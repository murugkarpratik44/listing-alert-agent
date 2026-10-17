# RTB average rent benchmark (Ireland)

File: `rtb-2025.csv` · Source: Residential Tenancies Board average monthly rent, CSO table RIQ02 (https://data.cso.ie/table/RIQ02) · Licence: CC BY 4.0 · Downloaded 2026-10-16 · Data to 2025 Q4. Re-checked 2026-10-17 against the CSO open-data API: all 311 rows match, and 2025 Q4 is still the latest quarter in the table (last updated 14 May 2026).

## Columns

| Column | Meaning |
|---|---|
| `location` | RTB location: county ("Kildare"), town with county ("Naas, Kildare"), Dublin area with district ("Rathmines, Dublin 6") or town ("Kildare Town") |
| `property_type` | "All property types" or "Apartment" |
| `bedrooms` | 1 or 2 |
| `value` | Mean of the 2025 quarterly averages, euro per month |
| `n_periods` | Number of 2025 quarters with data. The engine ignores rows with fewer than 2 and falls back to the county row |
| `latest_quarter_value` | 2025 Q4 average, euro per month (blank where Q4 had no data) |

Only locations relevant to the worked example are included (Dublin, Kildare and the Midlands). Contributors can add rows from the same table; keep the columns.

## How to read the comparison

RTB figures are agreed rents for tenancies registered with the RTB. Listings show asking rents, later in time. The comparison is a guide to whether a listing is unusually cheap or dear for the area, not a valuation.

Attribution required by the licence: "Source: Residential Tenancies Board / Central Statistics Office, licensed under CC BY 4.0." The alert footer includes it.
