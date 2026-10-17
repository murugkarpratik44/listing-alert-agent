# Listing Alert Agent

Listing Alert Agent turns the saved-search alert emails you already receive from listing sites into one clear, ranked alert. For each new listing it tells you whether it fits your budget, how long the trip is to the places that matter to you, how the price compares with the local market, and what to look at first. It reads email only: it never visits, searches or scrapes listing websites.

It ships with an Ireland rentals pack (Daft.ie and MyHome.ie alerts, RTB market averages) and a template for adding other countries and listing types.

## What you get

- **A guided setup** that asks what you are looking for, where you need to get to and how, what you can spend (alone or shared), and what rules a place out.
- **Hourly alerts** sorted into *act now*, *stretch* and *over budget*, each with a fit score out of 100 and the three reasons behind it.
- **Real travel times** by road from each listing's area to each important place, with Google Maps directions links for the exact trip.
- **Market comparison** against open data (for Ireland: RTB average agreed rents by area, type and bedrooms).
- **Repeat, price-change and re-list detection**, and **possible-scam flags**.
- **An estimated monthly cost** for you: your share of the rent, energy from the BER and floor area, and your commute, with sourced defaults where you give no prices.
- **Decision help**: side-by-side comparisons, viewing packs and feedback-driven tuning.
- **A weekly summary** and a **doctor** check that explains what is wrong when alerts stop.

## Install

Claude Code:

```
/plugin install listing-alert-agent --marketplace murugkarpratik44/listing-alert-agent
```

Then ask Claude: "Set up listing alerts". Claude app (Chat and Cowork) instructions are in the repository's `docs/` folder.

## Skills

| Skill | Use it to |
|---|---|
| `setup` | Set up or redo your alerts (about 15 minutes) |
| `run-alerts` | Run one alert pass now (the schedule runs it hourly) |
| `weekly-digest` | Get the weekly market and pipeline summary |
| `doctor` | Find out why alerts stopped or look wrong |
| `compare` | Put 2–5 listings side by side and get a recommendation with trade-offs |
| `viewing-pack` | Draft an enquiry (you send it), questions, documents and red flags for one listing |
| `tune` | Record "not for me – too far" verdicts and turn patterns into rule changes you approve |
| `dashboard` | Create or refresh a private dashboard: map, shortlist tracker, searchable listings table, alert runs |

## Requirements

- Claude with the **Gmail** connector, plus somewhere to keep your settings: a private GitHub repository (GitHub connector), a Google Drive folder (Google Drive connector) or a folder on your computer.
- Saved-search email alerts on the listing sites you use (setup shows you how).
- Python 3.10+ with PyYAML where Claude runs code. Without it, Claude follows the same rules by hand.
- Optional: a free openrouteservice.org API key for travel times.

## What this plugin reads, writes, sends and fetches

| | Details |
|---|---|
| Reads | Gmail messages from the alert sender addresses you configure; your own state storage; files inside this plugin |
| Writes | Your own state storage (private GitHub repository, Google Drive folder or local folder: settings, listing history, run log, your feedback); two Gmail labels: `Listing Alerts/Processed`, `Listing Alerts/Could not read`; optionally a Gmail draft of an enquiry, which you send yourself; optionally your private claude.ai dashboard page |
| Sends | Email to you only: one alert per run when there is something new, and one weekly summary (optionally copied to one address you choose) |
| Fetches | During setup only, and only if you set the `ORS_API_KEY` environment variable: the script reads that key from your environment and sends it, with the names and coordinates of your configured places, only to `api.openrouteservice.org` (geocoding and travel-time matrix). The key is never written to a file, an email or the chat. Never listing websites. |
| Optional dashboard | If you ask for one, a private page in your own claude.ai account showing listing facts, statuses and run counts from your state storage. It is refreshed by the alert run and is private until you share it. |
| Runs | `skills/run-alerts/scripts/laa.py`, a readable Python script that Claude runs for the arithmetic (rent conversion, scoring, travel lookup, duplicates, cost estimate, dashboard export). No hooks, no MCP servers, no background processes, no package installs. |
| Never | Visits, searches or scrapes listing websites; contacts landlords or agents; stores their names, phone numbers or email addresses; sends email to anyone except you. |

## Privacy and terms of use

- Your settings and history live in storage you own (private GitHub repository, Google Drive folder or local folder), not with the plugin author.
- Names, phone numbers and email addresses of landlords, agents and sellers are never stored.
- API keys are never written to files.
- Listing sites' terms generally forbid automated access to their websites. This plugin only reads alert emails sent to you. You remain responsible for using each site within its terms.

## Credits

Market data: Residential Tenancies Board / Central Statistics Office (CC BY 4.0). Routing: openrouteservice.org by HeiGIT; map data © OpenStreetMap contributors.

Licence: MIT. Source and documentation: https://github.com/murugkarpratik44/listing-alert-agent
