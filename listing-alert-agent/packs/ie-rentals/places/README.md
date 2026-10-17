# Ireland – places guidance

Used by `setup` to build `search_places` in the user's `config/places.yaml`. Travel times are then cached from each place to each of the user's important places.

## Which places to list

| Search area type | Places to list |
|---|---|
| Within N minutes of an important place | Towns and villages inside the travel-time area. Setup proposes them; the user confirms. |
| County | The county town and the main towns where listings appear. Add more if listings keep landing in "Check location". |
| Dublin | Postal districts from `dublin-postal-districts.yaml`, plus named suburbs the user cares about. |

Region values are county names without "Co." (for example `Kildare`, `Dublin`). The engine uses the region to choose a county-level market average when no town-level figure exists.

## Matching rules the engine applies

- A place matches when its name appears as whole words in the listing address. The longest matching name wins, so "Dublin 15" beats "Dublin 1".
- A name followed by Road, Street, Avenue, Lane, Row, Quay, Terrace or Drive is treated as a street, so "Naas Road, Dublin 12" does not match the town of Naas.
- Times are area-level: measured from the place's centre, not the exact address. Alerts say so and include a directions link for the exact trip.

## Eircodes

An Eircode's first three characters are its routing key (for example `D08` covers Dublin 8). Routing keys are useful search places for areas that listings describe by Eircode. The full Eircode identifies a single address; do not store full Eircodes of other people's properties in the state repository.

## Spelling variants

Listings use English and Irish forms, with and without accents (for example Dún Laoghaire and Dun Laoghaire). Add the variants a user's listings actually use as extra entries with the same region.
