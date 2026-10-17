# Ireland – public transport notes

Status: general guidance, 2026-10-17. Timetables change; always check the operator before relying on a time.

openrouteservice, which the plugin uses for driving, cycling and walking times, has no public-transport routing. For transit the plugin:

1. puts a Google Maps directions link with `travelmode=transit` in each alert, which opens live journey options for the exact listing address; and
2. lets the user add a short commute note per area in `config/places.yaml` (for example "Train to work about 60 min, few direct trains"), which setup writes after checking a journey planner with the user.

## Where to check times

| Need | Source |
|---|---|
| Any public transport journey in Ireland | Transport for Ireland journey planner: https://www.transportforireland.ie |
| Intercity and commuter trains, DART | Iarnród Éireann (Irish Rail): https://www.irishrail.ie |
| Luas tram | https://www.luas.ie |
| Dublin Bus | https://www.dublinbus.ie |

## Points worth asking about at setup

- How often the user travels to each important place, and at what time of day: a 25-minute off-peak drive can be 50 minutes at peak.
- Whether the user has a car. If not, set the anchor's mode to `transit` and expect fewer cached times.
- Whether a direct train matters. Commuter towns on a rail line can beat closer towns without one.
