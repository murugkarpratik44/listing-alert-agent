# Places and travel times

Alerts show real road-network travel times from each listing's area to each place that matters, with a confidence label and a directions link. This page explains how setup builds that.

## Principles

- Travel time, not straight-line distance. A town 25 km away across a river or without a motorway can take longer than one 40 km away.
- Say how each figure was measured: `area-level` means from the town or district centre, not the exact address.
- Always give a Google Maps directions link for the exact trip; it needs no API key.
- Nominatim (OpenStreetMap's public geocoder) is **not** used: its usage policy forbids this kind of systematic use.

## 1. Confirm the important places

For each anchor, give the user a map link and ask them to confirm the pin:

`https://www.google.com/maps/search/?api=1&query=<URL-encoded address>`

If the result is wrong, ask for a more exact address, postcode or landmark.

## 2. Build the search place list

1. Start from the user's search areas.
   - Region areas (a county, a city): the main towns or districts in it. Use the pack's `places/` guidance (for Ireland, Dublin postal districts are in `dublin-postal-districts.yaml`).
   - Travel-time areas ("within 35 min drive of Work"): propose towns and villages that could plausibly fall inside the limit, generously (about 1.5 × the limit), and let the travel matrix decide.
2. Each entry: `{name: <as it appears in addresses>, region: <county or region>}`.
3. Show the list grouped by region and ask the user to add places they know listings use.

Typical size: 20–80 places. More places mean fewer listings in "Check location".

## 3. Calculate travel times

### Route A – openrouteservice (recommended)

1. The user creates a free account at https://openrouteservice.org and copies their API key. Free-plan quotas are shown on their dashboard; one setup uses a handful of requests (one geocode per place and one matrix request per 45 places per mode).
2. The key goes into an environment variable for this one command. It is **never** written to a file, a commit or the chat history if avoidable. Best: the user sets it in their own terminal or in the cloud environment's secret settings.
   ```bash
   export ORS_API_KEY=<key>      # the user runs this, or sets it in their environment settings
   python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" travel-cache <state>
   ```
3. The command geocodes anchors and places (openrouteservice geocoding, restricted to the profile's country), requests the driving, cycling or walking matrix for the anchors' modes, and writes `data/travel-cache.csv` with `method = openrouteservice matrix`, `confidence = area` and a timestamp.
4. Network: this needs `api.openrouteservice.org`. On your own computer (Claude Code or Cowork with a local folder) it normally works. In a cloud session, the environment's network setting must allow that domain; if it does not, use route B or run this one step locally.
5. Check every geocode before trusting the times. Seen in Ireland on 2026-10-17:
   - every Dublin postal district ("Dublin 8", "Dublin 15") returned the same city-centre point;
   - small townlands and suburbs (Coosan, Monksland, Horseleap) returned the county centre or the county town;
   - a business park address returned a park of the same name in another county.
   Signs: several places sharing identical coordinates, a `county` or `region` result layer, or an unexpected town in the label. Fix by geocoding a well-known neighbourhood instead (for example Blanchardstown for Dublin 15) or by writing `lat`/`lon` in `places.yaml`, then re-run. Always give important places explicit coordinates once the user has confirmed the pin.
6. Quota: on a new free account the geocoding quota ran out after about 100 requests in one day (2026-10-17); the matrix quota was separate. Geocode in batches, keep coordinates in `places.yaml` so later runs skip geocoding, and check the limits shown on the dashboard.

### Route B – manual from Google Maps (no key)

For a small list (up to about 15 places): for each place × anchor, give the user the directions link and ask for the typical time and distance, or, if you can view the page yourself, read it. Write rows with `method = manual (Google Maps)`, `confidence = area`.

### Route C – estimated (last resort)

If neither route is possible, write your best estimate only with `method = estimated` and `confidence = estimated`, tell the user plainly, and suggest running route A later. Estimated times lower the confidence part of the score and are labelled in every alert.

## Public transport

openrouteservice has no public-transport routing. For anchors whose mode is `transit`:
- the alert always includes a Google Maps link with `travelmode=transit`;
- add the pack's transport notes (for Ireland, `notes/rail.md`);
- optionally record a typical time per place after checking a journey planner with the user (route B).

## Refresh

Road times change little. `doctor` warns when the cache is older than 45 days; re-run route A when convenient. Credit in alerts and README: "Routing © openrouteservice.org by HeiGIT | Map data © OpenStreetMap contributors".
