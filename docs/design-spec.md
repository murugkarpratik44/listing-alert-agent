# listing-alert-agent – Design Specification

| Item | Value |
|---|---|
| Status | Approved 2026-10-17; amended in Phase 2 (section 22) |
| Author | Pratik Murugkar (`murugkarpratik44`), drafted with Claude |
| Date | 2026-10-17 |
| Licence | MIT |
| Repository | `github.com/murugkarpratik44/listing-alert-agent` (public) |

---

## 1. Summary

`listing-alert-agent` is a Claude plugin that turns the alert emails people already receive from listing sites (rentals, homes for sale, jobs, cars and so on) into **ranked, explained, map-accurate decisions**, without ever visiting or scraping those sites.

A guided setup asks what the user is looking for, which places matter to them and how they travel, what they can spend and what rules out a listing. From then on, a scheduled run reads only the new alert emails, scores each listing, and sends one clear alert: what fits, why, how far it is by road or transit from the places that matter, how it compares with the local market, and what to do next.

It works in Claude Chat, Cowork and Claude Code. It ships with an **Ireland rentals** pack as the worked example and a **generic pack template** so anyone can add a country or use case.

---

## 2. Goals and non-goals

### Goals

1. A first-time user goes from install to a working, tested alert in about 15 minutes, by answering questions, not editing files.
2. Every alert answers: *Does it fit? Why? How far is it, really? Is it good value? What should I do now?*
3. Distances and travel times come from road and transit networks, with a stated confidence level, not straight lines.
4. No automated access to listing sites. Email is the only listing input.
5. Safe by default against prompt injection, data leaks and accidental emails to other people.
6. Low upkeep: schema-validated config, tested email parsers, a `doctor` command, CI evals and a monthly self-check.
7. Passes Anthropic plugin directory validation and review at launch.

### Non-goals (v1)

- Scraping, crawling or calling listing-site APIs.
- Applying for, booking or paying for anything on the user's behalf.
- Legal, financial or tenancy advice. Country notes are factual, sourced and dated.
- A hosted web service. Everything runs inside the user's own Claude account and repositories.

---

## 3. Users and surfaces

| User | Typical surface | Needs |
|---|---|---|
| Non-technical renter or buyer | Chat or Cowork in the Claude app | Guided setup, plain-English alerts, no files to edit |
| Technical user | Claude Code | Full control, local runs, CLI install, version pinning |
| Contributor | Claude Code + GitHub | Clear pack interface, fixtures, tests, CI |

### 3.1 Capability by surface

Facts from Anthropic's plugin platform-support page (checked 2026-10-17): skills and commands load in Chat, Cowork and Claude Code; agents and hooks load only in Cowork and Claude Code.

| Capability | Chat | Cowork | Claude Code | Design response |
|---|---|---|---|---|
| Setup wizard (skill) | Yes | Yes | Yes | Core feature on every surface |
| Run alerts on demand (skill) | Yes | Yes | Yes | Same skill everywhere |
| Scheduled runs | Via routines created from Claude Code or the web | Desktop scheduled tasks or routines | Routines (`/schedule`) or Desktop scheduled tasks | Setup generates the routine prompt and walks the user through creating it |
| Gmail access | Gmail connector | Gmail connector | Gmail connector | Required connector |
| State storage | GitHub connector (v0.1); Google Drive (v0.2) | Same, or local folder | Same, or local folder | Storage adapter (section 9) |
| Network for travel-time calculation | Limited | Depends on device allowlist | Full on the user's machine | Travel times calculated once at setup and cached; Google Maps links always |
| Python helper scripts | Code execution where available | Yes | Yes | Scripts do the arithmetic; instructions give a fallback without them |
| Subagent (`agents/`) | Ignored | Yes | Yes | Optional; nothing depends on it |

### 3.2 Scheduling facts that shape the design

From the Claude Code routines documentation (checked 2026-10-17):

- Routines run in Anthropic's cloud, at most **once an hour**, and are a research preview.
- The default cloud environment allows only a list of approved domains. Connector traffic (Gmail, GitHub) is not affected.
- Runs act as the user: emails and commits appear as theirs.

Consequences: (1) hourly is the fastest cadence; instant notice comes from the sites' own alert emails plus a Gmail filter; (2) anything needing the open internet (geocoding, routing, benchmark downloads) happens during setup, when the user is present, and is cached in the user's state repository.

---

## 4. Principles

1. **Email-only input.** The agent reads alerts the user subscribed to. It never fetches listing pages. Links are for the user to open.
2. **Explain every number.** Scores, distances and value judgements come with the reason and the source.
3. **Accuracy with stated confidence.** Each distance or time says whether it is exact-address, street-level or area-level, and how it was obtained.
4. **Ask, don't assume.** The wizard asks for anything that changes a result; defaults are shown and confirmed.
5. **Config as data.** User answers live in schema-validated YAML, not prose, so runs are repeatable and diffs readable.
6. **Deterministic where it matters.** Arithmetic (rent conversion, scoring, distance lookup, deduplication) runs in small Python scripts with tests; Claude handles reading emails and writing explanations.
7. **Safe by default.** Allowed senders only, alerts only to the user, email content treated as data.
8. **Packs, not forks.** Country and use-case knowledge lives in packs with a fixed interface.

---

## 5. Architecture

```text
 Listing sites ──(user's saved-search alerts)──► Gmail inbox
                                                     │
                       ┌─────────────────────────────┘
                       ▼
 ┌──────────────────────────── listing-alert-agent plugin ────────────────────────────┐
 │ setup ─► profile.yaml, sources.yaml, places.yaml, travel-cache.csv, routine prompt  │
 │ run-alerts:                                                                         │
 │   1 fetch (allowed senders, unprocessed label)                                      │
 │   2 parse (pack parser notes)  3 normalise (listing schema)                         │
 │   4 locate (place match / cache)  5 travel times (cache + confidence)               │
 │   6 deal-breakers  7 budget tier  8 market benchmark  9 score + reasons             │
 │   10 duplicates / price change / re-list  11 risk flags                             │
 │   12 render alert email + one-line notification  13 update state  14 health checks  │
 │ weekly-digest · compare · viewing-pack · tune · doctor                              │
 └─────────────────────────────────────────────────────────────────────────────────────┘
                       │                                  │
                       ▼                                  ▼
            User's private state repo           Gmail (alert to self) + phone push
            (config, cache, listings, logs)      (+ optional dashboard page)
```

### 5.1 Repository layout (public repo)

The plugin lives in a subfolder so videos and images for the README stay outside it (the directory only allows text, images and fonts under 256 KiB in the plugin folder, at most 512 files).

```text
listing-alert-agent/                      repo root = marketplace
├── .claude-plugin/marketplace.json       marketplace: one plugin, source "./listing-alert-agent"
├── listing-alert-agent/                  THE PLUGIN FOLDER
│   ├── .claude-plugin/plugin.json
│   ├── README.md                         ≥ 40 words; what it runs, sends and fetches
│   ├── LICENSE                           MIT
│   ├── skills/
│   │   ├── setup/            SKILL.md + references/ + scripts/
│   │   ├── run-alerts/       SKILL.md + references/ + scripts/
│   │   ├── weekly-digest/    SKILL.md
│   │   ├── compare/          SKILL.md
│   │   ├── viewing-pack/     SKILL.md
│   │   ├── tune/             SKILL.md
│   │   └── doctor/           SKILL.md
│   ├── agents/alert-runner.md            optional restricted subagent (Cowork, Code)
│   ├── packs/
│   │   ├── _template/                    generic pack to copy
│   │   └── ie-rentals/                   Ireland rentals worked example
│   ├── schemas/                          profile, sources, places, listing JSON schemas
│   └── evals/                            plugin eval cases (claude plugin eval)
├── docs/                                 design spec, quick starts, how-tos, security, FAQ
├── media/                                infographic, demo GIF, video (outside plugin)
├── tests/                                synthetic alert emails + expected results
├── tools/                                repo-only scripts (fixture checks, release notes)
├── .github/                              workflows, issue and PR templates
├── CONTRIBUTING.md · SECURITY.md · CODE_OF_CONDUCT.md · CHANGELOG.md
└── README.md                             project front page
```

A second public repository, `listing-alert-agent-state-template`, is the "Use this template" starting point for each user's **private** state repository (section 9).

### 5.2 Plugin manifest (draft)

```json
{
  "name": "listing-alert-agent",
  "displayName": "Listing Alert Agent",
  "version": "0.1.0",
  "description": "Turns listing-site alert emails into ranked, explained, map-accurate alerts. Email-only: never scrapes.",
  "author": { "name": "Pratik Murugkar", "url": "https://github.com/murugkarpratik44" },
  "homepage": "https://github.com/murugkarpratik44/listing-alert-agent",
  "repository": "https://github.com/murugkarpratik44/listing-alert-agent",
  "license": "MIT",
  "keywords": ["alerts", "rentals", "property", "jobs", "gmail", "decision-support"]
}
```

Components use the standard layout (`skills/`, `agents/`), so no component paths are declared. No hooks, no MCP servers and no `bin/` in v0.1: this keeps the plugin installable on every surface and simplifies directory review.

---

## 6. Skills and commands

All commands are skills (the documented recommendation for new plugins), invoked as `/listing-alert-agent:<name>` or picked up automatically from the description.

| Skill | Purpose | Writes |
|---|---|---|
| `setup` | Guided interview; creates config, travel cache and routine prompt; runs a dry run on sample emails | State repo, Gmail labels |
| `run-alerts` | One alert run (manual or scheduled) | Listings, run log, labels; sends one email |
| `weekly-digest` | Market and pipeline summary | Sends one email |
| `compare` | Side-by-side comparison of 2–5 listings, with a recommendation and trade-offs | Nothing (or shortlist status) |
| `viewing-pack` | Draft enquiry, questions to ask, documents to prepare, red-flag checklist for one listing | Nothing |
| `tune` | Turns feedback ("too far", "no parking") into proposed rule changes; applies only after confirmation | Profile |
| `doctor` | Checks connectors, labels, config validity, parser health, schedule and recent runs; explains fixes | Nothing |

Each `SKILL.md` stays under 500 lines and loads detail from `references/` only when needed.

---

## 7. Setup wizard

### 7.1 Interview

Asked one block at a time, with sensible defaults shown for confirmation. The full question bank is in `skills/setup/references/questionnaire.md`; the pack supplies country-specific options.

| Block | Questions | Example answer |
|---|---|---|
| 1. Goal | What are you looking for? (rent, buy, job, car, other) · Country · By when? | Rent, Ireland, by 1 December |
| 2. The thing | Types and sizes · must-haves · nice-to-haves · deal-breakers | 1–2 bed apartment or house; must have own bathroom each; nice: parking; never: ground floor |
| 3. Places that matter | Each place: name, address or Eircode/postcode, how often, how you travel, longest trip you'd accept, importance | Office, Galway city, 5 days, car, 35 min, high; Partner's work, Ennis, 3 days, car, 45 min, medium |
| 4. Search areas | Areas to watch, or "anywhere within my travel limits" | Within limits, plus Sligo town for hybrid weeks |
| 5. Money | Budget model: alone or sharing; per-person rules; bills included or not; stretch tolerance | €1,000 each, max 2 people, no shared bedroom, stretch 10% |
| 6. Alerts | Instant phone alerts for which tier · digest timing · quiet hours · share digest with someone | Act-now only; Sunday 10:00; 23:00–07:00 quiet |
| 7. Sources | Pack suggests main sites; user confirms which they use; guided alert setup per site | Daft.ie, MyHome.ie |
| 8. Storage | GitHub (v0.1) or Google Drive (v0.2) · create from template | Private repo from template |

### 7.2 What setup produces

1. `config/profile.yaml`, `config/sources.yaml`, `config/places.yaml`, all validated against `schemas/`.
2. `data/travel-cache.csv`: travel times from every place in the search areas to every important place, per mode (section 8).
3. Gmail label `Listing Alerts/Processed`; recommended Gmail filter text for instant alerts.
4. Routine prompts for `run-alerts` (hourly, quiet hours respected) and `weekly-digest`, with step-by-step instructions to create them on the user's surface.
5. **Dry run** on the pack's synthetic sample emails, so the user sees a real alert in their inbox before going live.
6. A one-page setup summary in plain English, saved as `SETUP-SUMMARY.md` in the state repo.

---

## 8. Geography and travel model

### 8.1 What the user sees on every listing

- **Travel line per important place:** "Office: 22 min drive (area-level) · Partner: 41 min drive (area-level)".
- **One-tap directions:** a Google Maps directions link from the listing address to each place, in the right travel mode. Format (no API key needed): `https://www.google.com/maps/dir/?api=1&origin=<listing>&destination=<place>&travelmode=driving|transit|walking|bicycling`, URL-encoded, under 2,048 characters.
- **Map link:** `https://www.google.com/maps/search/?api=1&query=<address>`.
- **Confidence label:** exact address · street · area (town/district centroid) · estimated.

### 8.2 How times are calculated

| Step | When | Method |
|---|---|---|
| Geocode important places | Setup | OpenRouteService geocoding with the user's free API key; user confirms each pin on a map link |
| Build the place list for search areas | Setup | Pack gazetteer (e.g. Irish towns, Dublin postal districts) + user additions |
| Travel-time matrix | Setup, then refreshed monthly by the digest | OpenRouteService Matrix API: up to 3,500 origin × destination pairs per request (e.g. 50 × 50), driving, cycling and walking profiles |
| Transit times | Setup (optional) | OpenRouteService has no public-transport routing. Default: transit shown as a Google Maps link plus any pack rail notes. Optional: Google Routes API with the user's own key |
| Listing → place match | Every run | Match the listing address to the most specific place in the cache (street > district > town > county); attach cached times with the matching confidence |
| Exact-address times | Every run, only if allowed | Optional: if the user's cloud environment allows the routing domain and holds an API credential, geocode the listing and call the matrix for that one point |
| Search areas by travel time | Setup | OpenRouteService isochrones (driving range limit 1 hour) turn "within 35 min drive" into an area; places inside it become the watch list |

Rules:
- The OpenRouteService key is requested at setup and stored only as the user's routine/environment credential or Claude Code `userConfig` with `sensitive: true`. It is never written to any repository.
- Nominatim is **not** used: its usage policy forbids systematic and LLM-generated generic use.
- Straight-line distance is shown only as a labelled fallback when no routing data exists.
- Attribution: "Routing © openrouteservice.org by HeiGIT | Map data © OpenStreetMap contributors" in the digest footer and README.

---

## 9. State storage

### 9.1 Adapter

| Adapter | Release | For | Notes |
|---|---|---|---|
| GitHub private repo | v0.1 | All surfaces | Created by the user from `listing-alert-agent-state-template`; the GitHub connector cannot create repositories, so setup gives one-click instructions |
| Google Drive folder (Sheets for listings) | v0.2 | Non-technical users | Uses the Drive connector |
| Local folder | v0.2 | Claude Code, Cowork on device | No scheduling in the cloud; uses Desktop scheduled tasks |

### 9.2 State files

```text
config/profile.yaml       goal, criteria, budget model, alert preferences
config/sources.yaml       sources, allowed sender addresses, pack id
config/places.yaml        important places with coordinates, modes, limits, weights
data/travel-cache.csv     place_id, anchor_id, mode, minutes, km, method, confidence, computed_at
data/listings.csv         one row per reported listing event (new, price change, re-list)
data/run-log.csv          one row per run
data/feedback.csv         user verdicts and reasons (for tune)
data/benchmark/           pack benchmark files copied at setup, with source and date
SETUP-SUMMARY.md          plain-English summary of the user's setup
```

`listings.csv` stores listing facts only. Names, phone numbers and email addresses of landlords, agents or sellers are never stored.

---

## 10. The run pipeline

| Step | Detail | Done by |
|---|---|---|
| 1 Fetch | Gmail search limited to `sources.yaml` sender addresses and not yet labelled; 7-day window | Claude + Gmail |
| 2 Parse | Pack parser notes per sender describe where each field sits; Claude extracts to JSON | Claude |
| 3 Normalise | Validate against `listing.schema.json`; convert rent periods; flag missing fields | Script |
| 4 Locate | Match to place hierarchy; record confidence | Script |
| 5 Travel | Look up cached times per important place and mode | Script |
| 6 Deal-breakers | Hard filters from profile; excluded listings logged with reason | Script |
| 7 Budget tier | Budget model → act now / stretch / over budget; per-person cost where sharing | Script |
| 8 Benchmark | Pack benchmark lookup (e.g. RTB average rent by area, type, bedrooms) | Script |
| 9 Score | Fit score 0–100 with top three reasons (section 11) | Script + Claude wording |
| 10 History | Duplicate, price change, re-list detection | Script |
| 11 Risk flags | Possible-scam and data-quality flags (section 12.3) | Script |
| 12 Render | Alert email (plain text) + one-line phone notification | Script template + Claude |
| 13 Save | Label emails; append listings and run log; commit | Claude + connectors |
| 14 Health | Once a day: source silence, parse failures, config drift | Script |

Failure handling: a parse failure never drops a listing silently; it goes to "Could not read" with the Gmail link, and the email is left unlabelled for the next run.

---

## 11. Scoring model

Fit score = weighted sum of component scores (each 0–100), shown with its top three reasons.

| Component | Default weight | Scoring |
|---|---|---|
| Budget | 30 | 100 at ≤ 85% of budget, linear to 50 at budget, to 0 at stretch limit |
| Travel | 30 | Per important place: 100 at ≤ 50% of the user's limit, linear to 0 at the limit; weighted by place importance and trips per week |
| Value vs market | 15 | 100 at ≥ 15% below benchmark, 50 at benchmark, 0 at ≥ 25% above |
| Must-haves and nice-to-haves | 15 | Must-haves met = 60; each nice-to-have adds a share of the remaining 40 |
| Freshness | 5 | Newer listings score higher (competition signal) |
| Data confidence | 5 | Exact address and complete fields score higher |

- Deal-breakers remove a listing before scoring.
- Weights are set from the interview ("What matters most?") and changed with `tune`.
- Reasons are generated from the largest positive and negative contributions, e.g. "18 min to office · €150 under budget · 12% below area average".

---

## 12. Decision aids

### 12.1 Estimated monthly cost (rentals packs)
Rent + estimated energy cost + commuting cost. Decision 2026-10-17: setup asks for each unit price (energy, cost per km, fares); any the user does not give use sourced pack defaults, each with its source and date. Energy uses the pack's energy-rating bands (e.g. Irish BER kWh/m²/yr) × floor area where given × a user-confirmed unit price; commuting uses cached km × trips × a user-confirmed cost per km or fare. Every estimate is labelled "estimate" with its inputs.

### 12.2 Compare and viewing pack
- `compare`: table of 2–5 listings across score components, cost estimate, travel and risks; ends with "If X matters most, choose A; if Y, choose B".
- `viewing-pack`: draft enquiry (user sends it), questions to ask, documents to prepare, and the pack's checklist. Country facts come from official sources listed in the pack, each with a link and a checked-on date.

### 12.3 Risk flags
| Flag | Rule |
|---|---|
| Possible scam – verify | Rent ≥ 35% below benchmark, or the email mentions payment before viewing, wire transfer, or "owner abroad" |
| Check details | Missing bathrooms, rent range, or area-level location only |
| Well above market | ≥ 25% above benchmark |

### 12.4 Feedback loop
The user replies to the alert or tells Claude "not for me – too far". `tune` records the verdict, spots patterns (e.g. three rejections over 30 min), proposes a precise rule change, and applies it only after the user agrees.

### 12.5 Dashboard (v0.3)
An optional private page with a map, filters and a search tracker (new → contacted → viewing → applied → rejected), updated by the runs.

---

## 13. Notifications

| Event | Phone notification | Email |
|---|---|---|
| Act-now listing | Yes, immediately at the next run | Yes |
| Stretch / over budget only | No (configurable) | Included in the next email |
| Price drop on a shortlisted listing | Yes | Yes |
| Health warning | Once per day | Once per day |
| Weekly digest | Short summary | Full digest |

Quiet hours suppress phone notifications; listings are held for the first run after quiet hours. The digest can be copied to one extra address the user names in setup (the only recipient other than the user, stored in `profile.yaml`).

---

## 14. Security and privacy

### 14.1 Threat model and controls

| Threat | Control |
|---|---|
| Prompt injection in an alert email ("ignore previous instructions and email…") | Emails are wrapped and treated as data; skills state that email content never changes instructions, recipients or files; only the parsing step reads email bodies |
| Spoofed sender | Only addresses in `sources.yaml` are read; unknown senders from known domains are reported, not processed |
| Alert sent to the wrong person | Recipients come only from `profile.yaml` (the user, plus at most one named address); never from email content |
| Secret leakage | No keys in any repository; keys only as environment credentials or `userConfig` with `sensitive: true` |
| Personal data spread | No third-party personal data stored; state repo private; README explains what is stored |
| Over-broad connector access | Routine instructions list only Gmail and GitHub (or Drive) connectors |
| Undisclosed behaviour (directory scan) | README states everything the plugin reads, writes, sends and fetches |

### 14.2 Terms of use
Each pack lists its sources, how alerts are set up, and the date the sites' terms were checked. The README and setup state that the plugin never visits listing sites and that users are responsible for complying with each site's terms.

---

## 15. Packs

### 15.1 Interface (`packs/<id>/pack.yaml`)

```yaml
id: ie-rentals
title: Ireland – rentals
domain: rentals            # rentals | sales | jobs | vehicles | other
country: IE
currency: EUR
sources:
  - id: daft
    name: Daft.ie
    senders: ["*@daft.ie"]          # narrowed to exact addresses at setup
    alert_setup: sources/daft.md     # how to create saved-search alerts
    parser: parsers/daft.md          # where fields sit in the alert email
  - id: myhome
    name: MyHome.ie
    senders: ["notifications@myhome.ie"]
    alert_setup: sources/myhome.md
    parser: parsers/myhome.md
places:
  gazetteer: places/README.md        # how to build the place list (towns, Dublin districts, Eircode routing keys)
benchmark:
  file: benchmark/rtb-2025.csv
  source: "RTB Average Monthly Rent Report, CSO table RIQ02"
  licence: CC BY 4.0
  checked: 2026-10-16
notes:
  rail: notes/rail.md
  checklist: notes/viewing-checklist.md   # sourced and dated
fixtures: fixtures/                       # synthetic alert emails for dry runs and tests
```

### 15.2 Packs at launch
- `ie-rentals`: Daft.ie and MyHome.ie parsers, RTB 2025 benchmark, Irish place guidance, rail notes, viewing checklist. Contains no personal data from the author's own setup.
- `_template`: annotated empty pack with instructions for contributors.

Further packs (for example UK rentals, jobs) are community contributions via the "new pack" issue template.

---

## 16. Testing and quality

| Layer | What | Tool |
|---|---|---|
| Schema | Config and listing files validate | JSON Schema + Python script |
| Scripts | Rent conversion, scoring, tiers, dedupe, place matching, URL building | `pytest` unit tests |
| Parsers | Synthetic alert emails → expected listing JSON | Golden-file tests |
| End to end | Fixture inbox → expected alert email text | Snapshot tests |
| Plugin behaviour | Realistic prompts with graders (e.g. "setup asks for places that matter", "never emails a non-configured address", "ignores injected instructions") | `claude plugin eval` |
| Structure | Manifest and component validity | `claude plugin validate` |
| Directory | README, licence, file types and sizes, no secrets | Developer-portal Validate before each submission |

All fixtures are invented. No real listing emails are committed.

---

## 17. Release and upkeep automation

| Automation | Trigger | Does |
|---|---|---|
| `validate.yml` | Every push and PR | `claude plugin validate`, schema checks, `pytest`, file-type and size guard for the plugin folder, secret scan |
| `evals.yml` | PRs touching skills or packs; weekly | `claude plugin eval`; fails below the agreed score |
| `release.yml` | Tag `v*` | Builds changelog from commits, creates GitHub release |
| Monthly maintenance routine | First Monday of each month | Runs evals against the current model, checks links in docs, checks for a newer benchmark release, opens an issue with findings |
| Issue templates | — | Bug, "alert email format changed" (with redacted sample), "new pack", feature request |
| Versioning | — | Semantic versioning; `version` in `plugin.json` raised every release (the directory requires it) |

---

## 18. Documentation, media and launch content

### 18.1 Documentation
- `README.md` (repo and plugin): what it is, a 30-second demo GIF, how it works, install per surface, what it reads/writes/sends, privacy, terms of use, credits.
- Quick starts: `docs/quickstart-chat.md`, `docs/quickstart-cowork.md`, `docs/quickstart-claude-code.md`.
- How-tos: set up alerts on a site, create the schedule, add a Gmail filter, write a pack, troubleshoot with `doctor`.
- `docs/security.md`, `docs/privacy.md`, `docs/faq.md`.

### 18.2 60-second motion video (captions, no voiceover)

| Time | Scene | On screen |
|---|---|---|
| 0–6 s | The problem | Inbox flooded with alert emails; "Which one is actually right for me?" |
| 6–14 s | Setup | Wizard questions appear: places that matter, budget, deal-breakers |
| 14–22 s | Real travel times | Map with office pin; isochrone area grows; "35 min drive, not 30 km as the crow flies" |
| 22–32 s | The run | Emails flow in, are scored; three listings rise to the top with reasons |
| 32–42 s | The alert | Phone notification; alert email card: act now, travel times, value vs market, map link |
| 42–50 s | Decide faster | Compare table; viewing pack checklist |
| 50–56 s | Safe by design | "Email-only. No scraping. Your data stays in your account." |
| 56–60 s | Call to action | Plugin name, GitHub URL, "Works in Claude Chat, Cowork and Claude Code" |

Produced as a Motion artifact; exported file linked from the README (kept outside the plugin folder).

### 18.3 Other launch content
- Infographic v2 (generic flow, with the Ireland example) in `media/`.
- Demo GIF of a dry run.
- LinkedIn post and carousel; short "how I built it" write-up.
- Directory listing copy: one-line description, long description, screenshots.
- Launch checklist: repo public → portal Validate → fix → submit → announce.

---

## 19. Roadmap

| Version | Scope |
|---|---|
| v0.1 (Phase 2) | Setup, run-alerts, weekly-digest, doctor; GitHub storage; travel cache + Maps links; scoring; ie-rentals pack; fixtures and unit tests |
| v0.2 (Phase 3) | Compare, viewing-pack, tune, cost estimate, risk flags; Google Drive storage; local-folder storage |
| v0.3 (Phase 4) | Behaviour tests (run by hand, not in CI), release automation, monthly maintenance scheduled task (email and GitHub issue), private dashboard, listing statuses |
| v1.0 (Phases 5–6) | Docs, media, directory submission, author's own setup migrated |

---

## 20. Risks and open items

| Risk | Mitigation |
|---|---|
| Routines are a research preview; behaviour may change | Docs include Desktop scheduled tasks as fallback; `doctor` checks schedule health |
| OpenRouteService daily quotas not confirmed from the plans page | Setup uses one matrix call per mode; cache refreshed monthly; verify quota on the user's HeiGIT dashboard during setup |
| No free public-transport routing | Transit via Google Maps links and pack notes; optional Google Routes key |
| Alert email layouts change | Golden-file tests per parser; "format changed" issue template; health check |
| Directory review holds | Plugin folder text-only, no hooks or MCP in v0.1, README discloses all behaviour, scripts invoked only by skills |
| Plugin name collision in the directory | Check at portal Validate before launch; fallback name `listing-alert-agent-pm` |
| Country notes become outdated | Every note has a source link and checked date; monthly maintenance flags notes older than 12 months |

---

## 21. Sources checked for this specification (2026-10-17)

- Plugins overview: https://claude.com/docs/plugins/overview
- Plugin feature support across platforms: https://claude.com/docs/plugins/platform-support
- Plugin manifest reference: https://code.claude.com/docs/en/plugins/manifest-reference.md
- Marketplace reference: https://code.claude.com/docs/en/plugins/marketplace-reference.md
- Skills reference: https://code.claude.com/docs/en/skills.md
- Routines: https://code.claude.com/docs/en/routines.md
- Plugin evals: https://code.claude.com/docs/en/plugin-evals.md
- Publish to the directory: https://claude.com/docs/directory/publish
- Plugin pre-submission checklist: https://claude.com/docs/plugins/pre-submission-checklist
- openrouteservice API restrictions: https://openrouteservice.org/restrictions/
- Nominatim usage policy: https://operations.osmfoundation.org/policies/nominatim/
- Google Maps URLs: https://developers.google.com/maps/documentation/urls/get-started

---

## 22. Amendments made during Phase 2 (2026-10-17)

Found while building v0.1; each is reflected in the code and skills.

| Section | Change | Reason |
|---|---|---|
| 8.2, 14.1 | The openrouteservice key is used only from the `ORS_API_KEY` environment variable during setup. No `userConfig` option. | Claude Code does not substitute sensitive `userConfig` values into skill content or pass them to commands Claude runs, so a sensitive option could not reach the script (plugin manifest reference, "User configuration"). |
| 3.1, 17 | Scheduled runs get the plugin files by attaching the plugin repository to the routine, or by downloading the files in `runtime-manifest.txt` from raw.githubusercontent.com. | Cloud sessions do not install plugins declared in a repository's `.claude/settings.json` (cloud environments documentation, "What carries over from your setup"). |
| 16, 17 | Tests use Python `unittest` instead of `pytest`. | `pytest` could not be installed in the build environment; `unittest` needs no install, so contributors and CI run the same command. |
| 11 | Listings flagged "possible scam" have the fit score capped at 40 and are ranked last in their tier. "Good value" is not shown alongside a risk flag. | A suspiciously cheap listing otherwise scored highest. |
| 11 | Travel score is weighted by place importance only; trips per week is recorded but not yet used. | Keep v0.1 simple; revisit with `tune` in v0.2. |
| 10 | Unreadable emails are labelled `Listing Alerts/Could not read` and reported once. | Leaving them unlabelled repeated the same warning every hour. |
| 6 | `compare`, `viewing-pack` and `tune` remain v0.2 as planned. Evals move with them. | Roadmap unchanged. |

## 23. Decisions log

| Date | Decision |
|---|---|
| 2026-10-17 | Design spec approved; directory submission at launch; openrouteservice + Google Maps links; GitHub storage in v0.1; captions-only video. |
| 2026-10-17 | Phase 2 (v0.1 core) approved, including the amendments in section 22. |
| 2026-10-17 | Google Drive and local-folder storage stay in Phase 3 (v0.2). |
| 2026-10-17 | Cost estimate inputs: asked at setup; sourced pack defaults when not given. |
| 2026-10-17 | The author's own live setup moves onto the plugin now, as the first real-world test. |
| 2026-10-17 | Cutover done: new scheduled tasks on the plugin; old tasks paused, to be deleted after 24 Oct with the author's OK. |
| 2026-10-17 | HTML alert and digest emails (plain text kept as fallback), after the author's review of the text version. |
| 2026-10-17 | Phase 3 (v0.2.0) built: compare, viewing-pack, tune, cost estimate, Drive and local storage. Drive stores CSV files with versioning rather than a live Google Sheet, because the Drive connector cannot edit file content in place. |
| 2026-10-17 | Phase 3 approved. Behaviour tests run by hand only, not in CI (each run uses Claude credentials). |
| 2026-10-17 | Monthly maintenance: one scheduled task on the 1st of each month emails the maintainer and opens a GitHub issue. Report only; it changes nothing. |
| 2026-10-17 | Private dashboard built now (Phase 4) from the Dashboard artifact type, fed by JSON files the alert run uploads, because the GitHub connector cannot read private repositories for live queries. |
| 2026-10-17 | Own energy bill can replace the BER estimate (`costs.energy_monthly_eur`). |
| 2026-10-17 | Phase 4 (v0.3.0) approved. A user's own energy bill is treated as their share, not split between occupants. Phase 5 to start. |
| 2026-10-17 | Phase 5 approved. Public launch uses a fresh history: the current files become the first commit of a new repository and the old repository is kept private as an archive. |
| 2026-10-17 | Benchmark kept at 2025 Q4: CSO table RIQ02 has no newer quarter (last updated 14 May 2026). RTB Rent Index reports use a different, standardised measure and are not mixed in. The maintenance check now reads the latest quarter from the CSO API. |
| 2026-10-17 | LinkedIn content framed as a personal project in the first person; drafts only, nothing posted without the author. |
| 2026-10-17 | Directory validation: the policy hold "Uses a credential from the user's machine" (ORS_API_KEY) is accepted and explained in the plugin README, because sensitive userConfig values cannot reach the script. Listing icon and links added before the first submission. |
| 2026-10-17 | Submitted to the plugin directory (v0.3.0, commit 7a2100f) with the GitHub push webhook. Plugin and state template repositories made public. Publishing waits for Anthropic's review. |
