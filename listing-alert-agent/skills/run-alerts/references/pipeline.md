# Pipeline rules (manual fallback)

The engine `scripts/laa.py` implements these rules and is tested. Use this page only when Python is not available, and follow it exactly so results match.

## 3. Normalise

- Monthly rent: weekly × 52 / 12; yearly / 12; monthly as stated. Round to the nearest whole unit.
- Listing link: if wrapped in a tracking redirect (`.../L0/https:%2F%2F...`), URL-decode the inner address. Remove `utm_*` parameters and any `#fragment`. Lower-case the host.
- Dedupe key: address in lower case, punctuation replaced by spaces, words `apartment apt unit co county the` removed, then `|` and the bedroom count (`?` if unknown).

## 4–5. Locate and travel

- Match the address against `place` names in `data/travel-cache.csv`: whole words, longest name wins. A name followed by road, rd, street, st, avenue, ave, lane, row, quay, terrace or drive is a street, not a match.
- Travel line per anchor in `config/places.yaml` (first mode listed): cached minutes and km, "area-level", plus a Google Maps directions link: `https://www.google.com/maps/dir/?api=1&origin=<address>&destination=<anchor lat,lon if known, else address>&travelmode=<mode>` (URL-encoded).
- No cached time: "time not cached" plus the directions link.
- If the listing's area has a `commute_note`, add the line "Commute: <note>".

## 6. Filters (remove, and list in `excluded` with the reason)

In this order: type in `exclude_types`; type not in `property_types` (when that list is set and the type is known); bedrooms not in `bedrooms`; bathrooms below `min_bathrooms` (unknown bathrooms pass); any matched deal-breaker; a must-have confirmed absent.

## Area

Areas in priority order. `travel_time`: cached minutes to the area's anchor and mode ≤ `max_minutes`. `region`: any `match` word appears as a whole word in the address or the place's region. First match wins. No area: if the place is unknown, "Check location"; if the place is known but outside every area, exclude it.

## 7. Budget tier

- People: `per_person` model → first occupancy rule whose `when` matches (bedrooms equal; bathrooms ≥ `min_bathrooms`, unknown bathrooms never match a bathroom condition) → its `people`; otherwise 1. `total` model → 1.
- Limit = amount × people (per_person) or amount (total). Stretch limit = limit × (1 + stretch_pct / 100).
- Rent ≤ limit: act now. ≤ stretch limit: stretch. Otherwise over budget. Rent unknown: check location, flag "rent not stated".

## 8. Benchmark

From the pack's benchmark CSV. Ignore rows with `n_periods` < 2.
1. Specific rows: "Town, County" or "Area, Dublin N" whose first part appears in the address; "X Town" when "X Town" appears or X is a non-final part of the address. The longest first part wins.
2. Otherwise county rows: the place's region, else the county named latest in the address.
3. Prefer "Apartment" for apartments and flats, otherwise "All property types"; fall back to the other.
Difference % = (rent − value) / value × 100, rounded.

## 9. Fit score (0–100)

Weighted average of components, weights from `profile.weights` (default budget 30, travel 30, value 15, features 15, freshness 5, confidence 5):

| Component | Score |
|---|---|
| Budget | rent/limit ≤ 0.85 → 100; 1.0 → 50; stretch limit → 0; linear between |
| Travel | per anchor: minutes/limit ≤ 0.5 → 100; 1.0 → 0; mean weighted high 3, medium 2, low 1. The limit is the area's `anchor_limits` value for that anchor if set (null = skip the anchor), otherwise the anchor's `max_minutes`. No data → 50 |
| Value | difference ≤ −15% → 100; 0% → 50; ≥ +25% → 0. No benchmark → 50 |
| Features | must-haves met 60 (not stated 30, absent 0) + 40 × share of nice-to-haves matched |
| Freshness | ≤ 6 h old → 100; 72 h → 0 |
| Confidence | exact 100, street 80, area 60, unknown 30 |

Reasons: the three components furthest from 50 after weighting, worded as "€300 under budget", "4 min to Work", "22% above area average", "1/2 nice-to-haves", "listed 2 h ago".

## Cost estimate (shown on cards, not used for tiers)

- Rent share: rent ÷ people (occupancy rules).
- Energy share: BER band midpoint (kWh/m²/yr, pack `notes/costs.yaml`) × floor area × price per kWh ÷ 12 ÷ people. Needs both BER and floor area; otherwise listed under "not included".
- Commute: for each important place with trips (area `anchor_trips`, else `trips_per_week`): driving = cached km × 2 × trips × 52 ÷ 12 × cost per km; transit = return fare × trips × 52 ÷ 12 when the user gave a fare.
- Prices: `profile.costs` first, else the pack's sourced defaults. Every figure says which was used.

## 10. History

Compare with `data/listings.csv` by link, then by dedupe key (the latest row wins):
- Not seen: new.
- Seen with a different rent: price change, flag "price change €a → €b (±n%)".
- Seen 14 or more days ago, same rent: re-listed.
- Otherwise: already reported; skip.
Within one run, the same dedupe key from a second source becomes "Also on <source>: <link>".

## 11. Risk flags

"possible scam – verify before paying anything" when the difference is ≤ −35%, or `payment_before_viewing` or `owner_abroad`; cap the fit score at 40 and rank last in the tier. "well above market" at ≥ +25%. "good value" at ≤ −10% when no other risk flag. "bathrooms not stated". "rent range – lower figure used".

## 14. Health (first run of each day)

- A source with no alert email for `silence_hours` (default 48): warn.
- Any unreadable emails in the last 24 runs: warn.
Record `checked: <warnings or no warnings>` in the run log's `health` column.
