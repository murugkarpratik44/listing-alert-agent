# Setup questionnaire

Ask one block at a time. Defaults are shown in brackets; offer them, never apply them silently. Map each answer to the config field shown.

## Block 1 – Goal

| Question | Field | Notes |
|---|---|---|
| What are you looking for: a place to rent, a home to buy, a job, a car, something else? | `goal.type` | v0.1 packs cover rentals; other types use the template rules |
| Which country? | `goal.country`, `goal.currency` | Picks the pack |
| By when do you need it? | `goal.move_by` | Used to stress urgency in the digest |
| Which email address should alerts go to? [the connected Gmail address] | `owner.email` | Only recipient for alerts |
| What time zone are you in? [from the email account or device] | `owner.timezone` | For quiet hours and the digest |

## Block 2 – The thing

| Question | Field |
|---|---|
| What types? (apartment, house, duplex…) Any to rule out? (rooms in shared houses, studios…) | `criteria.property_types`, `criteria.exclude_types` |
| How many bedrooms? Minimum bathrooms? | `criteria.bedrooms`, `criteria.min_bathrooms` |
| Must-haves: anything that rules a place out if missing? (own bathroom, pets allowed…) | `criteria.must_haves` |
| Nice-to-haves? (parking, balcony, garden…) | `criteria.nice_to_haves` |
| Deal-breakers: anything that rules a place out if present? (ground floor, no lift above 3rd floor…) | `criteria.deal_breakers` |

Keep must-haves, nice-to-haves and deal-breakers as short phrases that would appear in a listing. Explain that the plugin only counts them when the alert email actually mentions them.

## Block 3 – Places that matter

For each place (work, college, family, gym, school run):

| Question | Field (`places.yaml` anchor) |
|---|---|
| What do you call it? | `label` |
| Where is it? (address, postcode or landmark) | `address` |
| How often do you go? (days a week) | `trips_per_week` |
| How do you usually travel? (drive, public transport, cycle, walk) | `modes` |
| What is the longest trip you would accept, door to door? | `max_minutes` |
| How important is being close to it? (high, medium, low) | `importance` |

Then: confirm the pin with a Google Maps search link (`https://www.google.com/maps/search/?api=1&query=<address>`).

## Block 4 – Search areas

| Question | Field |
|---|---|
| Should I watch anywhere within your travel limit of <place>? | `areas[]` type `travel_time` |
| Any other areas, such as a county or city for a different lifestyle or hybrid work? | `areas[]` type `region`, `match` words |
| Which area matters most? | `priority` (1 = first) |
| For each region area: would you travel from there less often (for example weekly for hybrid work)? What is the longest trip you'd accept from there? | `anchor_limits` (per anchor, minutes) |
| Anything you want shown on every listing in that area, such as a train option? (Check the timetable together first.) | `commute_note` |

## Block 5 – Money

| Question | Field |
|---|---|
| Is the budget for you alone, or shared? | `budget.model` (`total` or `per_person`) |
| Monthly budget (per person if shared)? | `budget.amount` |
| How far over would you still want to hear about? [10%] | `budget.stretch_pct` |
| If shared: in which homes would you share, and with how many people? (for example "2-bed with 2 bathrooms: two of us; otherwise just me") | `budget.occupancy_rules` |
| Does your budget include bills? | `budget.bills_included` |
| For the monthly cost estimate: what do you pay a month for electricity and heating now, if you know? (Used as your energy cost; saves guessing from the BER.) | `costs.energy_monthly_eur` (number or [low, high]) |
| Otherwise: what do you pay per kWh for heating? (If unsure, I'll use the pack's sourced average, for Ireland SEAI's gas price, and say so.) | `costs.energy_eur_per_kwh` |
| If you drive: what does a km cost you? (If unsure, I'll use the pack's sourced rate, for Ireland the civil service mileage rate.) | `costs.car_eur_per_km` |
| If you take public transport to a place: what is your return fare? | `costs.transit_return_fare.<place id>` |
| For areas you'd travel from less often (for example weekly for hybrid work): how many trips a week from there? | `areas[].anchor_trips` |

## Block 6 – Alerts

| Question | Field |
|---|---|
| Which listings deserve a phone notification? [within budget only] | `alerts.push_tiers` |
| Quiet hours for phone notifications? [23:00–07:00] | `alerts.quiet_hours` |
| Weekly summary: which day and time? [Sunday 10:00] | `alerts.digest` |
| Anyone else who should get the weekly summary (not the alerts)? [no one] | `alerts.digest_cc` |
| What matters most: price, travel, value, features? | `weights` (adjust from the default 30/30/15/15/5/5; keep the total at 100) |

## Block 7 – Sources

Offer the pack's sources. For each one the user picks, give the saved-search steps from the pack. Ask the user to tell you when each is done.

## Block 8 – Storage

| Question | Field |
|---|---|
| Where should your settings and history live: a private GitHub repository (recommended, full history), a Google Drive folder (no GitHub needed), or a folder on this computer (runs only while it is on)? | `storage.type` |
| GitHub: the repository name. Drive: the folder name [Listing alerts]. Local: the folder. | `storage.repository` / `storage.drive_folder` / `storage.local_path` |

Details and limits of each option: `storage.md`.

---

## SETUP-SUMMARY.md template

```markdown
# My listing alerts

Set up <date> with listing-alert-agent <version>.

**Looking for:** <type>, <bedrooms> bedrooms, in <country>, by <move_by>.
**Budget:** <plain-English budget and sharing rules>. Stretch: up to <n>% over.
**Places that matter:** <label> (<address>, <max> min by <mode>, <importance>); …
**Watching:** <areas in priority order>.
**Must-haves:** … **Nice-to-haves:** … **Deal-breakers:** …
**Sources:** <site> (<sender>); …
**Alerts:** checked every hour; phone notifications for <tiers>, not between <quiet hours>. Weekly summary <day> <time>.
**Travel times:** <method>, calculated <date>, area-level.

To change anything, tell Claude what you want changed. To check everything is working, ask Claude to run the listing-alert-agent doctor.
```
