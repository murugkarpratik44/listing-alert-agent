# Privacy

## Who holds your data

**You do.** Your settings, listing history, run log and decisions are kept in storage you own:

- a private GitHub repository;
- a Google Drive folder;
- or a folder on your computer.

The plugin's author receives nothing. There is no server, analytics or telemetry.

## What is stored

| File | Holds |
|---|---|
| `config/profile.yaml` | Your requirements, budget, areas, the places that matter to you (with coordinates), notification times, your email address |
| `config/places.yaml` | Search places and their coordinates |
| `data/listings.csv` | One row per alerted listing: price, size, area, link, scores, travel time, market comparison. No contact details. |
| `data/run-log.csv` | One row per run: counts and health notes |
| `data/feedback.csv` | Your verdicts and statuses ("not for me – too far", "viewing") |
| `data/travel-cache.csv` | Drive times between your search places and your important places |

## What is never stored

- Names, phone numbers or email addresses of landlords, agents or sellers.
- API keys or tokens.
- The full text of your emails. Only the extracted listing facts are kept.

## Who sees what

| Party | Sees |
|---|---|
| **Anthropic (Claude)** | The emails and files the plugin reads during a run, under your Claude plan's terms |
| **openrouteservice.org (HeiGIT)** | During setup only, and only if you give a key: your search place names and the coordinates of the places that matter to you, to calculate drive times. Its [restrictions](https://openrouteservice.org/restrictions/) page lists the request limits. |
| **Google Maps** | Nothing, unless you open a directions link yourself |
| **Listing sites** | Nothing new. The plugin never contacts them. |

## Your dashboard

The optional dashboard is a page in your claude.ai account. It is private until you share it. It shows the same listing facts as `listings.csv`, plus your statuses, and nothing else.

## Removing your data

- Delete your state repository or folder.
- Delete the routines at [claude.ai/code/routines](https://claude.ai/code/routines).
- Delete the dashboard from your artifacts.
- Optionally, remove the two Gmail labels.

The plugin keeps no other copy.
