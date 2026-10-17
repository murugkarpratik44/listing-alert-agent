# Alert email format

Each alert is sent with two bodies, both written by the engine and sent unchanged:

- **HTML** (`email.html`), what most people see. Email-safe: tables and inline styles only, 600 px wide and readable on a phone, no images, no scripts, no web fonts. Layout:
  - header band with the run time and number of new listings, then coloured count chips (act now green, stretch amber, price changes blue, over budget and check location grey);
  - one card per act-now, stretch and price-change listing: price (and cost each when shared), fit score badge, address, beds, baths, type and area, reason chips (green helps the score, red hurts it), a facts table (travel per important place with a directions link, commute note, market comparison coloured green below and red above average, other sources), flag chips, and buttons: View listing, Directions, Map;
  - compact rows for over budget (with the amount over) and check location;
  - red boxes for emails that could not be read and setup warnings;
  - a small footer with data credits.
  All text from emails is HTML-escaped.
- **Plain text** (`email.body`), the fallback below. No Markdown, because many phone mail apps show it literally.

## Plain-text layout

```
<summary line: N listings: 2 act now (area), 1 stretch (area), 1 over budget (area), 1 to check.>

ACT NOW
1. €2,100 a month (€1,050 each) · 2 bed / 2 bath · Apartment · Fit 63/100
   Apartment 1, Example Court, Maynooth, Co. Kildare · Within 30 min of work
   Why: 4 min to Work · 22% above area average · €100 under budget
   Work: 4 min driving, 2 km (area-level) – directions: <Google Maps directions link>
   Family: 48 min driving, 62 km (area-level) – directions: <link>
   Commute: <area commute note, if set>
   Monthly cost (estimate): ≈ €1,175 for you (rent €925 + energy €60 + commute €190); not included: <anything missing>
   Market: average agreed rent €1,715 (Maynooth, Kildare, apartment) – listing is 22% above that
   Flags: <risk and data flags, if any>
   MyHome.ie: <listing link, tracking removed>
   Also on Daft.ie: <link>
   Map: <Google Maps search link>

STRETCH
...

PRICE CHANGES AND RE-LISTS
...

OVER BUDGET
- €2,297 · 2 bed / 1 bath · 22 Demo Street, Dublin 8 · <link>

CHECK LOCATION
- €1,000 · 4 Nowhere Place, Ballyexample · <link>

COULD NOT READ
- <Gmail link>

HEALTH
- No alert emails from Daft.ie for 50 hours (limit 48). Check the saved search is still on.

Market averages: <source> (<licence>). Travel times: <method credit>.
```

## Rules

- Sections appear only when they have content. Order: act now, stretch, price changes and re-lists, over budget, check location, could not read, health.
- Within a tier: listings without risk flags first, then by fit score, highest first.
- "Act now": within budget. "Stretch": up to `stretch_pct` over. "Over budget": one line each.
- "(€x each)" appears when the occupancy rules share the rent between people.
- Travel lines say how the time was measured: `area-level` means from the town or district centre. The directions link gives the exact trip.
- Subject: `Listing alert – <n> new (<a> act now) · <dd Mon HH:MM>`.
- Notification line (phone): `<a> act now, <s> stretch – <areas>. Details emailed.` Pushed only for tiers in `alerts.push_tiers` and outside quiet hours.
