# FAQ

## Does it check Daft.ie (or any listing site) for me?

No. It reads the alert emails the sites send to your Gmail. Listing sites' terms of use generally forbid automated access, so the plugin never visits, searches or scrapes them, and it won't if you ask. Set up saved-search alerts instead: [how-to/set-up-site-alerts.md](how-to/set-up-site-alerts.md).

## Why haven't I had an alert from one of my sites?

There may be nothing new that matches your searches. A narrow search in a quiet area can go days without a listing. Check that the site's own emails reach your Gmail (Spam too). The doctor warns when a site has been silent for 48 hours.

## How fast are alerts?

At most hourly, because that is the shortest routine interval. For instant notice, add a Gmail filter that marks the sites' own alerts as important: [how-to/gmail-filter.md](how-to/gmail-filter.md).

## How are travel times worked out?

Setup looks up each search place and each place that matters to you once, using openrouteservice.org (OpenStreetMap road data). It then stores a table of drive times. Each listing uses its area's time; the alert says "area-level" and links to Google Maps directions for the exact address. Lookups that only match a whole county, or that land on the same point as another place, are rejected rather than guessed.

## What does "Fit 72/100" mean?

A weighted score of six parts. The weights below are the defaults; you can change them in your settings.

| Part | Default weight |
|---|---|
| Budget fit | 30 |
| Travel, weighted by how often you make each trip | 30 |
| Value against the local market | 15 |
| Must-haves and nice-to-haves | 15 |
| How fresh the listing is | 5 |
| How precisely the location is known (exact, street or area) | 5 |

The alert lists the three reasons that moved each score most.

## What is in the monthly cost estimate?

Your share of the rent, plus energy, plus commute:

- **Energy:** your own bill if you gave one; otherwise an estimate from the BER rating and floor area at a sourced price.
- **Commute:** km × trips × a sourced cost per km, or your fares.

It is labelled as an estimate, and every default has a source and a date.

## Does it work outside Ireland?

The engine does. It needs a pack for your country and listing type. Ireland rentals ships today; anyone can add a pack: [how-to/write-a-pack.md](how-to/write-a-pack.md).

## What does it cost?

The plugin is free (MIT licence). Runs use your Claude plan's usage. openrouteservice has a free plan that covers setup.

## Can it contact landlords or book viewings?

No. The `viewing-pack` skill drafts an enquiry and a checklist. You send it yourself. The plugin never applies, books or pays.

## Which Claude plans and apps does it need?

- **Plan:** Pro, Max, Team or Enterprise, for scheduled runs.
- **Apps:** the Claude app and Claude Code both work. See [quickstart.md](quickstart.md).

## Can I stop it?

Turn the routines off at [claude.ai/code/routines](https://claude.ai/code/routines). Your history stays in your repository.
