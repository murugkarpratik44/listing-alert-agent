#!/usr/bin/env python3
"""listing-alert-agent engine.

Deterministic steps of the alert pipeline: normalising listings, matching places,
travel-time lookup, filters, budget tiers, market benchmark, fit score, history
(duplicates, price changes, re-lists), risk flags, alert rendering, weekly digest,
health checks and the setup-time travel cache.

Claude reads the alert emails and writes the extracted listings to a JSON file;
this script does the arithmetic so results are repeatable and testable.

Standard library only, plus PyYAML for config files (`pip install pyyaml`).

Usage:
  python laa.py validate     <state_dir>
  python laa.py process      <state_dir> <extracted.json> [--pack-dir DIR] [--now ISO]
                             [--emails-read N] [--not-parsed N] [--senders a;b] [--write]
  python laa.py digest       <state_dir> [--end YYYY-MM-DD] [--pack-dir DIR]
  python laa.py doctor       <state_dir>
  python laa.py travel-cache <state_dir> [--dry-run]      (needs ORS_API_KEY)
  python laa.py links        --origin TEXT --destination TEXT [--mode driving]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import fnmatch
import html
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

VERSION = "0.3.0"
TRAVEL_MODES = {"driving", "walking", "bicycling", "transit"}
ORS_PROFILES = {"driving": "driving-car", "walking": "foot-walking", "bicycling": "cycling-regular"}
LISTING_FIELDS = [
    "first_reported_at", "event", "area_id", "area_label", "source", "listing_url", "address",
    "place", "bedrooms", "bathrooms", "property_type", "rent_monthly", "currency", "tier",
    "people", "per_person", "fit_score", "benchmark_value", "benchmark_pct", "travel_summary",
    "confidence", "flags", "dedupe_key", "cost_monthly", "floor_area_m2", "energy_rating",
]
RUN_LOG_FIELDS = [
    "run_at", "alert_emails_read", "listings_extracted", "new_listings_reported",
    "emails_not_parsed", "alert_senders", "health", "status",
]
TIER_ORDER = ["act_now", "stretch", "over_budget"]
TIER_LABEL = {"act_now": "ACT NOW", "stretch": "STRETCH", "over_budget": "OVER BUDGET"}
STOPWORDS = {"apartment", "apt", "unit", "co", "county", "the"}
SCAM_SCORE_CAP = 40
STREET_WORDS = {"road", "rd", "street", "st", "avenue", "ave", "lane", "row", "quay", "terrace", "drive"}


# ----------------------------------------------------------------------------- io
def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required: pip install pyyaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def append_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    """Append rows. If the file's header lacks columns added in a newer version, the file is
    rewritten once with the new header (existing rows keep their values; new columns are blank)."""
    new = not path.exists() or path.stat().st_size == 0
    if not new:
        with open(path, encoding="utf-8", newline="") as fh:
            header = next(csv.reader(fh), [])
        if any(f not in header for f in fields):
            old = read_csv(path)
            merged = header + [f for f in fields if f not in header]
            with open(path, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=merged, extrasaction="ignore")
                w.writeheader()
                w.writerows(old)
            fields = merged
        else:
            fields = header
    with open(path, "a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


class State:
    """The user's state folder (a private repository created from the template)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.profile = load_yaml(self.root / "config" / "profile.yaml")
        self.sources = load_yaml(self.root / "config" / "sources.yaml")
        self.places = load_yaml(self.root / "config" / "places.yaml")
        self.travel = read_csv(self.root / "data" / "travel-cache.csv")
        self.listings_path = self.root / "data" / "listings.csv"
        self.run_log_path = self.root / "data" / "run-log.csv"

    @property
    def currency_symbol(self) -> str:
        cur = (self.profile.get("goal") or {}).get("currency", "EUR")
        return {"EUR": "€", "GBP": "£", "USD": "$"}.get(cur, cur + " ")


# ------------------------------------------------------------------------ helpers
def money(value: float | int | None, symbol: str = "€") -> str:
    if value is None or value == "":
        return "n/a"
    return f"{symbol}{int(round(float(value))):,}"


def monthly_rent(amount, period: str | None) -> int | None:
    """Convert a rent to a monthly figure. Weekly × 52 / 12, rounded to the nearest unit."""
    if amount in (None, ""):
        return None
    amount = float(amount)
    period = (period or "month").lower()
    if period.startswith("week"):
        return int(round(amount * 52 / 12))
    if period.startswith("year") or period.startswith("annum"):
        return int(round(amount / 12))
    return int(round(amount))


def canonical_url(url: str | None) -> str:
    """Strip tracking wrappers and utm parameters so the same listing compares equal."""
    if not url:
        return ""
    url = url.strip()
    # Amazon SES / awstrack style wrapper: .../L0/https:%2F%2Fwww.site.ie%2F.../1/...
    m = re.search(r"/L\d/(https?:%2F%2F[^/]+(?:%2F[^/]*)*)", url)
    if m:
        url = urllib.parse.unquote(m.group(1))
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, urllib.parse.urlencode(query), ""))


def dedupe_key(address: str | None, bedrooms) -> str:
    text = (address or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w for w in text.split() if w not in STOPWORDS]
    return " ".join(words) + f"|{bedrooms if bedrooms not in (None, '') else '?'}"


def maps_search_link(query: str) -> str:
    return "https://www.google.com/maps/search/?" + urllib.parse.urlencode({"api": 1, "query": query})


def maps_directions_link(origin: str, destination: str, mode: str = "driving") -> str:
    mode = mode if mode in TRAVEL_MODES else "driving"
    params = {"api": 1, "origin": origin, "destination": destination, "travelmode": mode}
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)


def parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compare_text(pct: float, against: str) -> str:
    if abs(pct) < 3:
        return f"in line with {against}"
    return f"{abs(pct):.0f}% {'below' if pct < 0 else 'above'} {against}"


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def lerp_score(value: float, points: list[tuple[float, float]]) -> float:
    """Piecewise-linear score through (x, score) points sorted by x."""
    if value <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return points[-1][1]


# -------------------------------------------------------------------- place model
def place_index(state: State) -> dict[str, dict]:
    """Places known to the travel cache, keyed by lower-case name, with anchor times."""
    index: dict[str, dict] = {}
    for row in state.travel:
        name = (row.get("place") or "").strip()
        if not name:
            continue
        entry = index.setdefault(name.lower(), {"place": name, "region": row.get("region", ""), "times": {}})
        try:
            minutes = float(row["minutes"])
        except (KeyError, TypeError, ValueError):
            continue
        key = (row.get("anchor_id", ""), row.get("mode", "driving"))
        entry["times"][key] = {
            "minutes": minutes,
            "km": float(row["km"]) if row.get("km") not in (None, "") else None,
            "method": row.get("method", ""),
            "confidence": row.get("confidence", "area"),
        }
    return index


def match_place(address: str, index: dict[str, dict]) -> dict | None:
    """Most specific place whose name appears as whole words in the address (longest name wins)."""
    addr = " " + re.sub(r"[^\w\s]", " ", (address or "").lower()) + " "
    addr = re.sub(r"\s+", " ", addr)
    best = None
    for name, entry in index.items():
        token = re.sub(r"\s+", " ", " " + re.sub(r"[^\w\s]", " ", name) + " ")
        for m in re.finditer(re.escape(token), addr):
            following = addr[m.end():].split(" ", 1)[0]
            if following in STREET_WORDS:  # "Naas Road" is a street, not the town of Naas
                continue
            if best is None or len(name) > len(best["place"]):
                best = entry
            break
    return best


# --------------------------------------------------------------------------- costs
def load_cost_defaults(pack_dir: Path | None) -> dict:
    if not pack_dir or not (pack_dir / "pack.yaml").exists():
        return {}
    rel = (load_yaml(pack_dir / "pack.yaml").get("notes") or {}).get("costs")
    return load_yaml(pack_dir / rel) if rel and (pack_dir / rel).exists() else {}


def cost_inputs(profile: dict, defaults: dict) -> dict:
    """User values from profile.costs, falling back to the pack's sourced defaults."""
    user = profile.get("costs") or {}
    energy = defaults.get("energy") or {}
    commute = defaults.get("commute") or {}
    out = {}
    if user.get("energy_eur_per_kwh") is not None:
        out["energy_price"], out["energy_source"] = float(user["energy_eur_per_kwh"]), "your price"
    elif energy.get("price_eur_per_kwh") is not None:
        out["energy_price"], out["energy_source"] = float(energy["price_eur_per_kwh"]), energy.get("source", "pack default")
    if user.get("car_eur_per_km") is not None:
        out["car_price"], out["car_source"] = float(user["car_eur_per_km"]), "your cost"
    elif commute.get("car_eur_per_km") is not None:
        out["car_price"], out["car_source"] = float(commute["car_eur_per_km"]), commute.get("source", "pack default")
    out["transit_fares"] = user.get("transit_return_fare") or {}
    monthly = user.get("energy_monthly_eur")
    if monthly is not None:  # the user's own bill (their share), a number or [low, high]
        lo, hi = (monthly, monthly) if not isinstance(monthly, (list, tuple)) else (monthly[0], monthly[-1])
        out["energy_monthly"] = (float(lo), float(hi))
    out["bands"] = {**((defaults.get("ber_bands") or {}).get("simplified_scale") or {}),
                    **((defaults.get("ber_bands") or {}).get("previous_scale") or {})}  # previous scale wins on F and G
    return out


def ber_midpoint(rating: str | None, bands: dict) -> float | None:
    if not rating:
        return None
    m = re.search(r"\b([A-G][0-3]?)\b", str(rating).upper().replace("BER", " "))
    if not m or m.group(1) not in bands:
        return None
    lo, hi = bands[m.group(1)]
    return (float(lo) + float(hi)) / 2


def estimate_cost(rec: dict, raw: dict, area: dict | None, place: dict | None, state: State, inputs: dict) -> dict | None:
    """Rough monthly cost to the user: share of rent + share of energy + their commute. Labelled an estimate."""
    rent = rec.get("rent_monthly")
    if not rent:
        return None
    people = rec.get("people") or 1
    parts, notes, missing = {"rent": rent / people}, [], []
    mid = ber_midpoint(raw.get("energy_rating"), inputs.get("bands") or {})
    area_m2 = raw.get("floor_area_m2")
    if inputs.get("energy_monthly"):
        lo, hi = inputs["energy_monthly"]
        parts["energy"] = (lo + hi) / 2
        notes.append(f"energy from your own bill (€{lo:.0f}{'' if lo == hi else f'–{hi:.0f}'} a month)"
                     + (f"; this home's BER is {raw.get('energy_rating')}" if raw.get("energy_rating") else ""))
    elif mid is not None and area_m2 and inputs.get("energy_price") is not None:
        parts["energy"] = mid * float(area_m2) * inputs["energy_price"] / 12 / people
        notes.append(f"energy from BER {raw.get('energy_rating')} × {float(area_m2):.0f} m² at €{inputs['energy_price']:.2f}/kWh ({inputs['energy_source']})")
    else:
        missing.append("energy (needs BER and floor area in the alert)")
    commute = 0.0
    for anchor in (state.places.get("anchors") or []):
        mode = (anchor.get("modes") or ["driving"])[0]
        trips = anchor_trips(anchor, area) or 0
        t = place["times"].get((anchor["id"], mode)) if place else None
        if not trips:
            continue
        if mode == "driving" and t and t.get("km") and inputs.get("car_price") is not None:
            commute += t["km"] * 2 * trips * 52 / 12 * inputs["car_price"]
            notes.append(f"{anchor.get('label')}: {t['km']:.0f} km each way × {trips:g} trip{'' if trips == 1 else 's'} a week at €{inputs['car_price']:.2f}/km ({inputs['car_source']})")
        elif mode == "transit" and anchor["id"] in inputs.get("transit_fares", {}):
            commute += float(inputs["transit_fares"][anchor["id"]]) * trips * 52 / 12
            notes.append(f"{anchor.get('label')}: return fare × {trips:g} trip{'' if trips == 1 else 's'} a week (your fare)")
        else:
            missing.append(f"commute to {anchor.get('label')}")
    if commute:
        parts["commute"] = commute
    return {"total": round(sum(parts.values())), "parts": {k: round(v) for k, v in parts.items()},
            "notes": notes, "missing": missing}


# ---------------------------------------------------------------------- benchmark
def load_benchmark(pack_dir: Path | None, state: State) -> tuple[list[dict], dict]:
    """Benchmark rows and metadata from the pack (or a copy in the state folder)."""
    meta = {}
    candidates = []
    if pack_dir:
        pack = load_yaml(pack_dir / "pack.yaml") if (pack_dir / "pack.yaml").exists() else {}
        meta = pack.get("benchmark") or {}
        if meta.get("file"):
            candidates.append(pack_dir / meta["file"])
    candidates.append(state.root / "data" / "benchmark" / "benchmark.csv")
    for path in candidates:
        if path.exists():
            return read_csv(path), meta
    return [], meta


def benchmark_lookup(rows: list[dict], address: str, region: str, bedrooms, property_type: str | None) -> dict | None:
    """Most specific location row for the bedrooms and property type, with fallbacks.

    Rows: location, property_type, bedrooms, value, n_periods. A location like
    "Newbridge, Kildare" matches when its first part appears in the address.
    """
    if not rows or bedrooms in (None, ""):
        return None
    try:
        beds = int(bedrooms)
    except (TypeError, ValueError):
        return None
    want_type = "Apartment" if (property_type or "").lower().startswith(("apartment", "flat")) else "All property types"
    addr = " " + re.sub(r"[^\w\s]", " ", (address or "").lower()) + " "
    addr = re.sub(r"\s+", " ", addr)

    def ok(row) -> bool:
        try:
            return int(row["bedrooms"]) == beds and float(row["value"]) > 0 and int(row.get("n_periods") or 0) >= 2
        except (KeyError, TypeError, ValueError):
            return False

    def first_part(loc: str) -> str:
        return re.sub(r"\s+", " ", " " + re.sub(r"[^\w\s]", " ", loc.split(",")[0].lower()) + " ")

    # address parts other than the last one (the last is usually the county)
    addr_inner_parts = {first_part(p) for p in (address or "").split(",")[:-1]}
    specific, county = [], []  # (rank tuple, row); lower rank is better
    for row in rows:
        if not ok(row):
            continue
        loc = row["location"]
        low = loc.lower()
        type_rank = 0 if row["property_type"] == want_type else 1
        if low.endswith(" town"):
            # "Kildare Town" means the town itself, not the county of the same name
            town = first_part(loc[:-5])
            if (town.strip() + " town") in addr or town in addr_inner_parts:
                specific.append(((-len(town), type_rank), row))
        elif "," in loc or re.search(r"\bdublin \d", low):
            fp = first_part(loc)
            if fp.strip() and fp in addr:
                specific.append(((-len(fp), type_rank), row))
        else:
            token = " " + re.sub(r"[^\w\s]", " ", low) + " "
            if region and low == region.lower():
                county.append(((0, 0, type_rank), row))
            elif token in addr:
                # counties usually come last in an address: prefer the latest mention
                county.append(((1, -addr.rindex(token), type_rank), row))
    for pool in (specific, county):
        if pool:
            pool.sort(key=lambda x: x[0])
            best = pool[0][1]
            return {"location": best["location"], "property_type": best["property_type"], "value": float(best["value"])}
    return None


# ----------------------------------------------------------------------- pipeline
def occupancy(profile: dict, bedrooms, bathrooms) -> int:
    budget = profile.get("budget") or {}
    if budget.get("model", "total") != "per_person":
        return 1
    for rule in budget.get("occupancy_rules") or []:
        cond = rule.get("when") or {}
        if "bedrooms" in cond and str(cond["bedrooms"]) != str(bedrooms):
            continue
        if "min_bathrooms" in cond:
            if bathrooms in (None, "") or float(bathrooms) < float(cond["min_bathrooms"]):
                continue
        return int(rule.get("people", 1))
    return 1


def tier_for(rent: int | None, people: int, profile: dict) -> tuple[str, float]:
    budget = profile.get("budget") or {}
    amount = float(budget.get("amount", 0))
    limit = amount * people if budget.get("model") == "per_person" else amount
    stretch = limit * (1 + float(budget.get("stretch_pct", 10)) / 100)
    if rent is None:
        return "check", limit
    if rent <= limit:
        return "act_now", limit
    if rent <= stretch:
        return "stretch", limit
    return "over_budget", limit


def assign_area(listing: dict, place: dict | None, profile: dict) -> tuple[dict | None, list[dict]]:
    """First area (by priority) the listing falls in, plus travel facts used to decide."""
    travel_facts = []
    for area in sorted(profile.get("areas") or [], key=lambda a: a.get("priority", 99)):
        if area.get("type") == "travel_time":
            if not place:
                continue
            key = (area.get("anchor"), area.get("mode", "driving"))
            t = place["times"].get(key)
            if t and t["minutes"] <= float(area.get("max_minutes", 0)):
                return area, travel_facts
        else:
            words = [w.lower() for w in area.get("match") or []]
            text = ((listing.get("address") or "") + " " + (place or {}).get("region", "")).lower()
            if any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words):
                return area, travel_facts
    return None, travel_facts


def anchor_trips(anchor: dict, area: dict | None) -> float | None:
    """Trips a week to this anchor from a listing in `area` (area override, else the anchor's own)."""
    override = ((area or {}).get("anchor_trips") or {}).get(anchor.get("id"))
    value = override if override is not None else anchor.get("trips_per_week")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def travel_items(listing: dict, place: dict | None, state: State) -> list[dict]:
    """One dict per important place: label, mode, minutes, km, confidence, directions link."""
    items = []
    for anchor in (state.places.get("anchors") or []):
        mode = (anchor.get("modes") or ["driving"])[0]
        # Coordinates, when known, beat an address the map may resolve wrongly (business parks often do)
        if anchor.get("lat") is not None and anchor.get("lon") is not None:
            dest = f"{float(anchor['lat']):.5f},{float(anchor['lon']):.5f}"
        else:
            dest = anchor.get("address") or anchor.get("label")
        t = place["times"].get((anchor["id"], mode)) if place else None
        items.append({
            "anchor_id": anchor["id"], "label": anchor.get("label", anchor["id"]), "mode": mode,
            "minutes": t["minutes"] if t else None, "km": t.get("km") if t else None,
            "confidence": t["confidence"] if t else None,
            "link": maps_directions_link(listing.get("address") or "", dest, mode),
        })
    return items


def travel_lines(listing: dict, place: dict | None, state: State,
                 area: dict | None = None) -> tuple[list[str], list[float], str]:
    """Human travel lines per anchor, the travel score inputs and the overall confidence.

    An area may override an anchor's limit with `anchor_limits: {<anchor id>: <minutes or null>}`,
    for example a longer limit for a weekly-commute area. null means "do not score travel to it".
    """
    lines, ratios = [], []
    overrides = (area or {}).get("anchor_limits") or {}
    confidence = "area" if place else "unknown"
    for anchor in (state.places.get("anchors") or []):
        modes = anchor.get("modes") or ["driving"]
        mode = modes[0]
        # Coordinates, when known, beat an address the map may resolve wrongly (business parks often do)
        if anchor.get("lat") is not None and anchor.get("lon") is not None:
            dest = f"{float(anchor['lat']):.5f},{float(anchor['lon']):.5f}"
        else:
            dest = anchor.get("address") or anchor.get("label")
        link = maps_directions_link(listing.get("address") or "", dest, mode)
        t = place["times"].get((anchor["id"], mode)) if place else None
        if t:  # keep in step with travel_items()
            km = f", {t['km']:.0f} km" if t.get("km") else ""
            lines.append(f"{anchor.get('label', anchor['id'])}: {t['minutes']:.0f} min {mode}{km} ({t['confidence']}-level) – directions: {link}")
            if anchor["id"] in overrides:
                limit = overrides[anchor["id"]]
            else:
                limit = anchor.get("max_minutes") or 60
            if limit is not None:
                weight = {"high": 3, "medium": 2, "low": 1}.get(str(anchor.get("importance", "medium")), 2)
                trips = anchor_trips(anchor, area)
                if trips:  # places you travel to more often count for more (half-trip resolution)
                    weight *= max(1, round(trips * 2))
                ratios.extend([t["minutes"] / float(limit)] * weight)
            confidence = t["confidence"] or confidence
        else:
            lines.append(f"{anchor.get('label', anchor['id'])}: time not cached – directions: {link}")
    return lines, ratios, confidence


def score_listing(rent, limit, stretch_pct, ratios, bench_pct, features_ok, nice_hits, nice_total,
                  age_hours, confidence, weights) -> tuple[int, list[tuple[float, str]]]:
    parts = {}
    if rent is not None and limit:
        frac = rent / limit
        stretch = 1 + stretch_pct / 100
        parts["budget"] = lerp_score(frac, [(0.85, 100), (1.0, 50), (stretch, 0)])
    else:
        parts["budget"] = 50
    if ratios:
        parts["travel"] = statistics.mean(lerp_score(r, [(0.5, 100), (1.0, 0)]) for r in ratios)
    else:
        parts["travel"] = 50
    parts["value"] = 50 if bench_pct is None else lerp_score(bench_pct, [(-15, 100), (0, 50), (25, 0)])
    # features_ok: True = must-haves met, None = not stated in the email, False = confirmed missing
    feat = {True: 60, None: 30, False: 0}[features_ok]
    if nice_total:
        feat += 40 * nice_hits / nice_total
    else:
        feat += 40 if features_ok else 0
    parts["features"] = feat
    parts["freshness"] = 100 if age_hours is None else lerp_score(age_hours, [(6, 100), (72, 0)])
    parts["confidence"] = {"exact": 100, "street": 80, "area": 60}.get(confidence, 30)
    total_w = sum(weights.values()) or 1
    score = sum(parts[k] * weights.get(k, 0) for k in parts) / total_w
    contributions = [((parts[k] - 50) * weights.get(k, 0) / total_w, k) for k in parts]
    return int(round(clamp(score))), contributions


def risk_flags(listing: dict, bench_pct, baths_known: bool) -> list[str]:
    flags = []
    tf = listing.get("text_flags") or {}
    if (bench_pct is not None and bench_pct <= -35) or tf.get("payment_before_viewing") or tf.get("owner_abroad"):
        flags.append("possible scam – verify before paying anything")
    if bench_pct is not None and bench_pct >= 25:
        flags.append("well above market")
    elif bench_pct is not None and bench_pct <= -10 and not flags:
        flags.append("good value")
    if not baths_known:
        flags.append("bathrooms not stated")
    if listing.get("rent_is_range"):
        flags.append("rent range – lower figure used")
    return flags


def process(state: State, extracted: list[dict], pack_dir: Path | None, now: dt.datetime) -> dict:
    profile = state.profile
    crit = profile.get("criteria") or {}
    weights = profile.get("weights") or {"budget": 30, "travel": 30, "value": 15, "features": 15, "freshness": 5, "confidence": 5}
    stretch_pct = float((profile.get("budget") or {}).get("stretch_pct", 10))
    sym = state.currency_symbol
    index = place_index(state)
    bench_rows, bench_meta = load_benchmark(pack_dir, state)
    costs_in = cost_inputs(profile, load_cost_defaults(pack_dir))
    history = read_csv(state.listings_path)
    by_url = {}
    by_key = {}
    for row in history:
        if row.get("listing_url"):
            by_url[row["listing_url"]] = row
        if row.get("dedupe_key"):
            by_key[row["dedupe_key"]] = row

    results, excluded, seen_in_run = [], [], {}
    for raw in extracted:
        item = dict(raw)
        item["listing_url"] = canonical_url(raw.get("url"))
        item["rent_monthly"] = monthly_rent(raw.get("rent_amount"), raw.get("rent_period"))
        beds = raw.get("bedrooms")
        baths = raw.get("bathrooms")
        ptype = (raw.get("property_type") or "").lower()

        def exclude(reason):
            excluded.append({"address": raw.get("address"), "url": item["listing_url"], "reason": reason})

        if any(x.lower() in ptype for x in crit.get("exclude_types") or []):
            exclude(f"type '{raw.get('property_type')}' excluded")
            continue
        wanted_types = [t.lower() for t in crit.get("property_types") or []]
        if wanted_types and ptype and not any(t in ptype for t in wanted_types):
            exclude(f"type '{raw.get('property_type')}' not wanted")
            continue
        if crit.get("bedrooms") and beds not in (None, "") and int(beds) not in [int(b) for b in crit["bedrooms"]]:
            exclude(f"{beds} bedrooms not wanted")
            continue
        if baths not in (None, "") and float(baths) < float(crit.get("min_bathrooms", 0)):
            exclude(f"{baths} bathrooms below minimum")
            continue
        if raw.get("matched_deal_breakers"):
            exclude("deal-breaker: " + ", ".join(raw["matched_deal_breakers"]))
            continue
        missing_must = [m for m in crit.get("must_haves") or [] if m not in (raw.get("matched_must_haves") or [])]
        if missing_must and raw.get("must_haves_confirmed_absent"):
            exclude("missing must-have: " + ", ".join(missing_must))
            continue

        place = match_place(raw.get("address") or "", index)
        area, _ = assign_area(raw, place, profile)
        if area is None:
            if place is None and not raw.get("address"):
                item["bucket"] = "check_location"
            elif place is None:
                item["bucket"] = "check_location"
            else:
                exclude(f"outside search areas ({place['place']})")
                continue
        lines, ratios, conf = travel_lines(raw, place, state, area)
        people = occupancy(profile, beds, baths)
        tier, limit = tier_for(item["rent_monthly"], people, profile)
        bench = benchmark_lookup(bench_rows, raw.get("address") or "", (place or {}).get("region", ""), beds, raw.get("property_type"))
        bench_pct = None
        if bench and item["rent_monthly"]:
            bench_pct = round((item["rent_monthly"] - bench["value"]) / bench["value"] * 100)
        nice = crit.get("nice_to_haves") or []
        nice_hits = len([n for n in nice if n in (raw.get("matched_nice_to_haves") or [])])
        received = parse_dt(raw.get("received_at"))
        age_h = (now - received).total_seconds() / 3600 if received else None
        must_state = True if not missing_must else None
        score, contrib = score_listing(item["rent_monthly"], limit, stretch_pct, ratios, bench_pct,
                                       must_state, nice_hits, len(nice), age_h, conf, weights)
        flags = risk_flags(raw, bench_pct, baths not in (None, ""))
        key = dedupe_key(raw.get("address"), beds)

        # history
        prev = by_url.get(item["listing_url"]) or by_key.get(key)
        event = "new"
        if prev:
            prev_rent = int(float(prev.get("rent_monthly") or 0)) if prev.get("rent_monthly") else None
            last = parse_dt(prev.get("first_reported_at"))
            if prev_rent and item["rent_monthly"] and prev_rent != item["rent_monthly"]:
                event = "price_change"
                change = (item["rent_monthly"] - prev_rent) / prev_rent * 100
                flags.insert(0, f"price change {money(prev_rent, sym)} → {money(item['rent_monthly'], sym)} ({change:+.0f}%)")
            elif last and (now - last).days >= 14:
                event = "relisted"
                flags.insert(0, "re-listed")
            else:
                continue
        # duplicates within this run (same property from two sources)
        if key in seen_in_run:
            other = seen_in_run[key]
            known = {other["listing_url"]} | {o["url"] for o in other["also_on"]}
            if item["listing_url"] not in known:
                other["also_on"].append({"source": raw.get("source"), "url": item["listing_url"]})
            continue

        reasons, tones = [], []
        for c, k in sorted(contrib, key=lambda x: -abs(x[0]))[:3]:
            before = len(reasons)
            if k == "budget" and item["rent_monthly"] is not None:
                diff = limit - item["rent_monthly"]
                reasons.append(f"{money(abs(diff), sym)} {'under' if diff >= 0 else 'over'} budget")
            elif k == "travel" and ratios and place:
                a = (state.places.get("anchors") or [{}])[0]
                t = place["times"].get((a.get("id"), (a.get("modes") or ["driving"])[0]))
                if t:
                    reasons.append(f"{t['minutes']:.0f} min to {a.get('label', a.get('id'))}")
            elif k == "value" and bench_pct is not None:
                reasons.append(compare_text(bench_pct, "area average"))
            elif k == "features" and nice:
                reasons.append(f"{nice_hits}/{len(nice)} nice-to-haves")
            elif k == "freshness" and age_h is not None:
                reasons.append(f"listed {age_h:.0f} h ago")
            elif k == "confidence":
                reasons.append(f"location {conf}-level")
            if len(reasons) > before:
                tones.append("good" if c > 0 else "bad" if c < 0 else "neutral")

        risky = any(f.startswith("possible scam") for f in flags)
        if risky:  # never let a likely scam top the list
            score = min(score, SCAM_SCORE_CAP)
            reasons.insert(0, "score capped until verified")
            tones.insert(0, "bad")
        if tier == "check":
            item["bucket"] = "check_location"
            flags.append("rent not stated")

        rec = {
            **item,
            "event": event,
            "risky": risky,
            "bucket": item.get("bucket") or tier,
            "tier": tier,
            "area_id": (area or {}).get("id", ""),
            "area_label": (area or {}).get("label", "Check location"),
            "area_priority": (area or {}).get("priority", 99),
            "place": (place or {}).get("place", ""),
            "people": people,
            "budget_limit": limit,
            "per_person": round(item["rent_monthly"] / people) if (item["rent_monthly"] and people > 1) else None,
            "fit_score": score,
            "reasons": reasons,
            "reason_tones": tones,
            "travel_lines": lines,
            "travel": travel_items(raw, place, state),
            "commute_note": (area or {}).get("commute_note", ""),
            "_cost_ctx": (raw, area, place),
            "confidence": conf,
            "benchmark": bench,
            "benchmark_pct": bench_pct,
            "flags": flags,
            "dedupe_key": key,
            "map_link": maps_search_link(raw.get("address") or ""),
            "also_on": [],
        }
        raw_c, area_c, place_c = rec.pop("_cost_ctx")
        rec["cost"] = estimate_cost(rec, raw_c, area_c, place_c, state, costs_in)
        seen_in_run[key] = rec
        results.append(rec)

    results.sort(key=lambda r: (TIER_ORDER.index(r["tier"]) if r["tier"] in TIER_ORDER else 9,
                                r["risky"], -r["fit_score"], r["area_priority"]))
    return {"results": results, "excluded": excluded, "benchmark_meta": bench_meta,
            "now": local_now(profile, now).isoformat(timespec="seconds")}


# ---------------------------------------------------------------------- rendering
def render_alert(out: dict, state: State, not_parsed: list[str] | None = None, health: list[str] | None = None) -> dict:
    sym = state.currency_symbol
    res = out["results"]
    counts = {t: [r for r in res if r["bucket"] == t] for t in TIER_ORDER + ["check_location"]}
    changes = [r for r in res if r["event"] in ("price_change", "relisted")]
    n_new = len([r for r in res if r["event"] == "new"])
    now = local_now(state.profile, parse_dt(out["now"]) or dt.datetime.now(dt.timezone.utc))

    def areas_of(items):
        seen = []
        for r in items:
            if r["area_label"] not in seen:
                seen.append(r["area_label"])
        return ", ".join(seen)

    summary_bits = []
    for t, label in (("act_now", "act now"), ("stretch", "stretch"), ("over_budget", "over budget")):
        items = counts[t]
        if items:
            summary_bits.append(f"{len(items)} {label} ({areas_of(items)})")
    if counts["check_location"]:
        summary_bits.append(f"{len(counts['check_location'])} to check")
    summary = f"{len(res)} listing{'s' if len(res) != 1 else ''}: " + ", ".join(summary_bits) + "." if res else "No new matching listings."

    lines = [summary, ""]

    def block(r, n):
        beds = r.get("bedrooms") if r.get("bedrooms") not in (None, "") else "?"
        baths = r.get("bathrooms") if r.get("bathrooms") not in (None, "") else "?"
        head = f"{n}. {money(r['rent_monthly'], sym)} a month"
        if r.get("per_person"):
            head += f" ({money(r['per_person'], sym)} each)"
        head += f" · {beds} bed / {baths} bath · {r.get('property_type') or 'type n/a'} · Fit {r['fit_score']}/100"
        out_lines = [head, f"   {r.get('address') or 'Address not given'} · {r['area_label']}"]
        if r["reasons"]:
            out_lines.append("   Why: " + " · ".join(r["reasons"]))
        for tl in r["travel_lines"]:
            out_lines.append("   " + tl)
        if r.get("commute_note"):
            out_lines.append("   Commute: " + r["commute_note"])
        if r.get("cost"):
            out_lines.append("   Monthly cost (estimate): " + cost_text(r["cost"], sym))
        if r["benchmark"]:
            b = r["benchmark"]
            pct = r["benchmark_pct"]
            out_lines.append(f"   Market: average agreed rent {money(b['value'], sym)} ({b['location']}, {b['property_type'].lower()}) – listing is {compare_text(pct, 'that')}")
        if r["flags"]:
            out_lines.append("   Flags: " + "; ".join(r["flags"]))
        out_lines.append(f"   {r.get('source', 'Source')}: {r['listing_url']}")
        for o in r["also_on"]:
            out_lines.append(f"   Also on {o['source']}: {o['url']}")
        out_lines.append(f"   Map: {r['map_link']}")
        return out_lines

    for t in ("act_now", "stretch"):
        items = [r for r in counts[t] if r["event"] == "new"]
        if items:
            lines.append(TIER_LABEL[t])
            for i, r in enumerate(items, 1):
                lines.extend(block(r, i))
                lines.append("")
    if changes:
        lines.append("PRICE CHANGES AND RE-LISTS")
        for i, r in enumerate(changes, 1):
            lines.extend(block(r, i))
            lines.append("")
    over = [r for r in counts["over_budget"] if r["event"] == "new"]
    if over:
        lines.append("OVER BUDGET")
        for r in over:
            lines.append(f"- {money(r['rent_monthly'], sym)} · {r.get('bedrooms', '?')} bed / {r.get('bathrooms', '?')} bath · {r.get('address')} · {r['listing_url']}")
        lines.append("")
    chk = [r for r in counts["check_location"] if r["event"] == "new"]
    if chk:
        lines.append("CHECK LOCATION")
        for r in chk:
            lines.append(f"- {money(r['rent_monthly'], sym)} · {r.get('address') or 'no address'} · {r['listing_url']}")
        lines.append("")
    if not_parsed:
        lines.append("COULD NOT READ")
        lines.extend(f"- {x}" for x in not_parsed)
        lines.append("")
    if health:
        lines.append("HEALTH")
        lines.extend(f"- {h}" for h in health)
        lines.append("")
    meta = out.get("benchmark_meta") or {}
    if meta.get("source"):
        lines.append(f"Market averages: {meta['source']} ({meta.get('licence', '')}). Travel times: {travel_credit(state)}.")
    act = len(counts["act_now"])
    subject = f"Listing alert – {n_new} new ({act} act now) · {now:%d %b %H:%M}"
    if act:
        note = f"{act} act now"
        if counts["stretch"]:
            note += f", {len(counts['stretch'])} stretch"
        note += f" – {areas_of(counts['act_now'] + counts['stretch'])}. Details emailed."
    elif res:
        note = f"{len(res)} new listing{'s' if len(res) != 1 else ''}, none within budget. Details emailed."
    else:
        note = "No new matching listings."
    should_send = bool(res or not_parsed or health)
    alerts_cfg = state.profile.get("alerts") or {}
    push_tiers = alerts_cfg.get("push_tiers") or ["act_now"]
    push_worthy = any(r["bucket"] in push_tiers for r in res) or bool(health)
    push = push_worthy and not in_quiet_hours(state.profile, local_now(state.profile, now))
    html_body = render_alert_html(out, state, counts, changes, now, not_parsed or [], health or [])
    return {"subject": subject, "body": "\n".join(lines).rstrip() + "\n", "html": html_body,
            "notification": note, "send": should_send, "push": push}


# ------------------------------------------------------------------ html email
# Email-safe HTML: tables and inline styles only (Gmail strips <style> in some clients), 600px wide,
# system fonts, no images or scripts. The plain-text body is always sent alongside as a fallback.
C = {
    "page": "#f3f4f6", "card": "#ffffff", "ink": "#1f2937", "muted": "#6b7280", "line": "#e5e7eb",
    "head": "#1e293b", "accent": "#1d4ed8",
    "green": "#047857", "green_bg": "#ecfdf5", "amber": "#b45309", "amber_bg": "#fffbeb",
    "red": "#b91c1c", "red_bg": "#fef2f2", "blue": "#1d4ed8", "blue_bg": "#eff6ff",
    "grey": "#4b5563", "grey_bg": "#f3f4f6",
}
TIER_STYLE = {
    "act_now": ("Act now", C["green"], C["green_bg"]),
    "stretch": ("Stretch", C["amber"], C["amber_bg"]),
    "changes": ("Price changes and re-lists", C["blue"], C["blue_bg"]),
    "over_budget": ("Over budget", C["grey"], C["grey_bg"]),
    "check_location": ("Check location", C["grey"], C["grey_bg"]),
}
FONT = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _pill(text: str, fg: str, bg: str, size: int = 12) -> str:
    return (f'<span style="display:inline-block;margin:0 6px 6px 0;padding:3px 10px;border-radius:999px;'
            f'background:{bg};color:{fg};font-size:{size}px;font-weight:600;line-height:18px;">{_e(text)}</span>')


def _button(text: str, href: str, primary: bool = False) -> str:
    if primary:
        style = f"background:{C['accent']};color:#ffffff;border:1px solid {C['accent']};"
    else:
        style = f"background:#ffffff;color:{C['accent']};border:1px solid #c7d2fe;"
    return (f'<a href="{_e(href)}" style="display:inline-block;margin:0 8px 8px 0;padding:9px 14px;border-radius:8px;'
            f'{style}font-size:13px;font-weight:600;text-decoration:none;">{_e(text)}</a>')


def _flag_style(flag: str) -> tuple[str, str]:
    f = flag.lower()
    if "scam" in f or "well above" in f:
        return C["red"], C["red_bg"]
    if "good value" in f:
        return C["green"], C["green_bg"]
    if "price change" in f or "re-listed" in f:
        return C["blue"], C["blue_bg"]
    return C["amber"], C["amber_bg"]


def _fit_badge(score: int) -> str:
    fg, bg = (C["green"], C["green_bg"]) if score >= 70 else (C["amber"], C["amber_bg"]) if score >= 50 else (C["grey"], C["grey_bg"])
    return (f'<td align="right" valign="top" style="width:72px;">'
            f'<div style="display:inline-block;min-width:56px;padding:6px 8px;border-radius:10px;background:{bg};text-align:center;">'
            f'<div style="font-size:20px;font-weight:700;color:{fg};line-height:22px;">{score}</div>'
            f'<div style="font-size:10px;font-weight:600;color:{fg};letter-spacing:.5px;">FIT /100</div></div></td>')


def _fact_row(label: str, value_html: str) -> str:
    return (f'<tr><td valign="top" style="padding:6px 12px 6px 0;width:92px;font-size:12px;color:{C["muted"]};'
            f'text-transform:uppercase;letter-spacing:.4px;">{_e(label)}</td>'
            f'<td valign="top" style="padding:6px 0;font-size:14px;color:{C["ink"]};">{value_html}</td></tr>')


def _section_heading(key: str, count: int) -> str:
    label, fg, bg = TIER_STYLE[key]
    return (f'<tr><td style="padding:24px 24px 8px;">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td style="width:4px;background:{fg};border-radius:2px;">&nbsp;</td>'
            f'<td style="padding-left:10px;font-size:13px;font-weight:700;color:{fg};text-transform:uppercase;letter-spacing:.8px;">'
            f'{_e(label)} <span style="color:{C["muted"]};font-weight:600;">· {count}</span></td></tr></table></td></tr>')


def _listing_card(r: dict, sym: str) -> str:
    beds = r.get("bedrooms") if r.get("bedrooms") not in (None, "") else "?"
    baths = r.get("bathrooms") if r.get("bathrooms") not in (None, "") else "?"
    price = f'<span style="font-size:24px;font-weight:700;color:{C["ink"]};">{_e(money(r["rent_monthly"], sym))}</span>' \
            f'<span style="font-size:14px;color:{C["muted"]};"> /month</span>'
    if r.get("per_person"):
        price += f'<div style="font-size:13px;color:{C["muted"]};margin-top:2px;">{_e(money(r["per_person"], sym))} each for {r["people"]} people</div>'
    meta = " · ".join(_e(x) for x in (f"{beds} bed", f"{baths} bath", r.get("property_type") or "Type n/a", r["area_label"]))
    parts = [
        f'<tr><td style="padding:0 24px 14px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{C["card"]};border:1px solid {C["line"]};border-radius:12px;"><tr><td style="padding:16px 18px;">',
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td valign="top">{price}</td>{_fit_badge(r["fit_score"])}</tr></table>',
        f'<div style="margin-top:10px;font-size:15px;font-weight:600;color:{C["ink"]};">{_e(r.get("address") or "Address not given")}</div>',
        f'<div style="margin-top:2px;font-size:13px;color:{C["muted"]};">{meta}</div>',
    ]
    if r["reasons"]:
        tone_style = {"good": (C["green"], C["green_bg"]), "bad": (C["red"], C["red_bg"])}
        tones = r.get("reason_tones") or []
        pills = [_pill(("+ " if tone == "good" else "− " if tone == "bad" else "") + x,
                       *tone_style.get(tone, (C["grey"], C["grey_bg"])))
                 for x, tone in zip(r["reasons"], tones + ["neutral"] * len(r["reasons"]))]
        parts.append('<div style="margin-top:12px;">' + "".join(pills) + "</div>")
    rows = []
    for t in r.get("travel") or []:
        if t["minutes"] is not None:
            km = f' · {t["km"]:.0f} km' if t.get("km") else ""
            val = (f'<b>{t["minutes"]:.0f} min</b> {_e(t["mode"])}{_e(km)} '
                   f'<span style="color:{C["muted"]};font-size:12px;">({_e(t["confidence"])}-level)</span> '
                   f'· <a href="{_e(t["link"])}" style="color:{C["accent"]};text-decoration:none;">directions</a>')
        else:
            val = f'<span style="color:{C["muted"]};">time not cached</span> · <a href="{_e(t["link"])}" style="color:{C["accent"]};text-decoration:none;">directions</a>'
        rows.append(_fact_row(t["label"], val))
    if r.get("commute_note"):
        rows.append(_fact_row("Commute", f'<span style="color:{C["muted"]};">{_e(r["commute_note"])}</span>'))
    if r.get("cost"):
        c = r["cost"]
        detail = " + ".join(f"{k} {money(v, sym)}" for k, v in c["parts"].items())
        extra = ("<br>" + _e("Not included: " + ", ".join(c["missing"]))) if c["missing"] else ""
        rows.append(_fact_row("Your cost", f'<b>≈ {_e(money(c["total"], sym))} a month</b> '
                              f'<span style="color:{C["muted"]};font-size:12px;">(estimate: {_e(detail)}){extra}</span>'))
    if r["benchmark"]:
        b, pct = r["benchmark"], r["benchmark_pct"]
        colour = C["green"] if pct <= -3 else C["red"] if pct >= 3 else C["muted"]
        rows.append(_fact_row("Market", f'{_e(money(b["value"], sym))} average agreed rent '
                              f'<span style="color:{C["muted"]};font-size:12px;">({_e(b["location"])}, {_e(b["property_type"].lower())})</span>'
                              f'<br><b style="color:{colour};">{_e(compare_text(pct, "that average").capitalize())}</b>'))
    for o in r["also_on"]:
        rows.append(_fact_row("Also on", f'<a href="{_e(o["url"])}" style="color:{C["accent"]};text-decoration:none;">{_e(o["source"])}</a>'))
    if rows:
        parts.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                     f'style="margin-top:12px;border-top:1px solid {C["line"]};">' + "".join(rows) + "</table>")
    if r["flags"]:
        parts.append('<div style="margin-top:10px;">' + "".join(_pill(f, *_flag_style(f)) for f in r["flags"]) + "</div>")
    first_dir = next((t["link"] for t in (r.get("travel") or [])), None)
    buttons = _button(f'View on {r.get("source") or "site"}', r["listing_url"], primary=True)
    if first_dir:
        buttons += _button("Directions", first_dir)
    buttons += _button("Map", r["map_link"])
    parts.append(f'<div style="margin-top:14px;">{buttons}</div>')
    parts.append("</td></tr></table></td></tr>")
    return "".join(parts)


def _compact_rows(items: list[dict], sym: str) -> str:
    rows = []
    for r in items:
        beds = r.get("bedrooms") if r.get("bedrooms") not in (None, "") else "?"
        baths = r.get("bathrooms") if r.get("bathrooms") not in (None, "") else "?"
        rows.append(
            f'<tr><td style="padding:10px 0;border-bottom:1px solid {C["line"]};font-size:14px;font-weight:700;color:{C["ink"]};white-space:nowrap;" valign="top">{_e(money(r["rent_monthly"], sym))}</td>'
            f'<td style="padding:10px 0 10px 14px;border-bottom:1px solid {C["line"]};font-size:13px;color:{C["ink"]};" valign="top">'
            f'<a href="{_e(r["listing_url"])}" style="color:{C["accent"]};text-decoration:none;font-weight:600;">{_e(r.get("address") or "Address not given")}</a>'
            f'<div style="color:{C["muted"]};font-size:12px;margin-top:2px;">{_e(beds)} bed · {_e(baths)} bath · {_e(r.get("property_type") or "type n/a")} · {_e(r.get("source") or "")}'
            + (f' · <span style="color:{C["red"]};">{_e(money(r["rent_monthly"] - r["budget_limit"], sym))} over budget</span>'
               if r.get("tier") == "over_budget" and r.get("rent_monthly") and r.get("budget_limit") else "")
            + '</div></td></tr>')
    return (f'<tr><td style="padding:0 24px 8px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{C["card"]};border:1px solid {C["line"]};border-radius:12px;"><tr><td style="padding:4px 18px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">' + "".join(rows) + "</table></td></tr></table></td></tr>")


def _notice_box(title: str, items: list[str], linkify: bool = False) -> str:
    lis = []
    for x in items:
        if linkify and x.startswith("http"):
            lis.append(f'<li style="margin:4px 0;"><a href="{_e(x)}" style="color:{C["red"]};">Open the email in Gmail</a></li>')
        else:
            lis.append(f'<li style="margin:4px 0;">{_e(x)}</li>')
    return (f'<tr><td style="padding:16px 24px 0;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{C["red_bg"]};border:1px solid #fecaca;border-radius:12px;"><tr><td style="padding:12px 18px;color:{C["red"]};font-size:13px;">'
            f'<b style="text-transform:uppercase;letter-spacing:.6px;">{_e(title)}</b><ul style="margin:6px 0 0;padding-left:18px;">{"".join(lis)}</ul>'
            "</td></tr></table></td></tr>")


def render_alert_html(out: dict, state: State, counts: dict, changes: list, now: dt.datetime,
                      not_parsed: list[str], health: list[str]) -> str:
    sym = state.currency_symbol
    res = out["results"]
    chips = []
    for key, n in (("act_now", len(counts["act_now"])), ("stretch", len(counts["stretch"])),
                   ("changes", len(changes)), ("over_budget", len(counts["over_budget"])),
                   ("check_location", len(counts["check_location"]))):
        if n:
            label, fg, bg = TIER_STYLE[key]
            chips.append(_pill(f"{n} {label.lower() if key != 'changes' else 'price change' + ('s' if n > 1 else '')}", fg, bg, 13))
    if not res:
        chips.append(_pill("No new matching listings", C["grey"], C["grey_bg"], 13))
    owner = (state.profile.get("owner") or {}).get("name")
    greeting = f"Hi {_e(owner)}, here" if owner else "Here"
    body = [
        f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="color-scheme" content="light only"><title>Listing alert</title></head>'
        f'<body style="margin:0;padding:0;background:{C["page"]};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{C["page"]};{FONT}">'
        f'<tr><td align="center" style="padding:20px 10px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#fafafa;border-radius:14px;overflow:hidden;border:1px solid {C["line"]};">',
        f'<tr><td style="background:{C["head"]};padding:20px 24px;">'
        f'<div style="font-size:12px;color:#cbd5e1;letter-spacing:.8px;text-transform:uppercase;">Listing alert · {_e(f"{now:%a %d %b, %H:%M}")}</div>'
        f'<div style="font-size:20px;font-weight:700;color:#ffffff;margin-top:4px;">{len(res)} new listing{"s" if len(res) != 1 else ""} for you</div></td></tr>',
        f'<tr><td style="padding:16px 24px 0;font-size:14px;color:{C["ink"]};">{greeting} is what arrived since the last check, ranked by fit.'
        f'<div style="margin-top:10px;">{"".join(chips)}</div></td></tr>',
    ]
    for key in ("act_now", "stretch"):
        items = [r for r in counts[key] if r["event"] == "new"]
        if items:
            body.append(_section_heading(key, len(items)))
            body.extend(_listing_card(r, sym) for r in items)
    if changes:
        body.append(_section_heading("changes", len(changes)))
        body.extend(_listing_card(r, sym) for r in changes)
    for key in ("over_budget", "check_location"):
        items = [r for r in counts[key] if r["event"] == "new"]
        if items:
            body.append(_section_heading(key, len(items)))
            body.append(_compact_rows(items, sym))
    if not_parsed:
        body.append(_notice_box("Could not read", not_parsed, linkify=True))
    if health:
        body.append(_notice_box("Check your setup", health))
    meta = out.get("benchmark_meta") or {}
    credits = []
    if meta.get("source"):
        credits.append(f'Market averages: {_e(meta["source"])} ({_e(meta.get("licence", ""))}).')
    credits.append(f"Travel times: {_e(travel_credit(state))}. Times are area-level and off-peak; use the directions links for the exact trip.")
    body.append(
        f'<tr><td style="padding:20px 24px 24px;font-size:11px;line-height:16px;color:{C["muted"]};">'
        + " ".join(credits)
        + "<br>Sent by listing-alert-agent from your own saved-search alerts. Listing sites are never visited automatically.</td></tr>")
    body.append("</table></td></tr></table></body></html>")
    return "".join(body)


def cost_text(c: dict, sym: str) -> str:
    detail = " + ".join(f"{k} {money(v, sym)}" for k, v in c["parts"].items())
    text = f"≈ {money(c['total'], sym)} for you ({detail})"
    if c["missing"]:
        text += "; not included: " + ", ".join(c["missing"])
    return text


def travel_credit(state: State) -> str:
    methods = {r.get("method", "") for r in state.travel}
    if any("openrouteservice" in m for m in methods):
        return "openrouteservice.org by HeiGIT, map data © OpenStreetMap contributors"
    return "cached estimates; directions links open Google Maps"


# ------------------------------------------------------------------------- state
def write_results(state: State, out: dict, emails_read: int, not_parsed: int, senders: str, health: str, status: str) -> None:
    rows = []
    for r in out["results"]:
        rows.append({
            "first_reported_at": out["now"], "event": r["event"], "area_id": r["area_id"],
            "area_label": r["area_label"], "source": r.get("source", ""), "listing_url": r["listing_url"],
            "address": r.get("address", ""), "place": r["place"], "bedrooms": r.get("bedrooms", ""),
            "bathrooms": r.get("bathrooms", ""), "property_type": r.get("property_type", ""),
            "rent_monthly": r["rent_monthly"] or "", "currency": (state.profile.get("goal") or {}).get("currency", "EUR"),
            "tier": r["tier"], "people": r["people"], "per_person": r["per_person"] or "",
            "fit_score": r["fit_score"], "benchmark_value": (r["benchmark"] or {}).get("value", ""),
            "benchmark_pct": "" if r["benchmark_pct"] is None else r["benchmark_pct"],
            "travel_summary": " | ".join(t.split(" – directions")[0] for t in r["travel_lines"]),
            "confidence": r["confidence"], "flags": "; ".join(r["flags"]), "dedupe_key": r["dedupe_key"],
            "cost_monthly": (r.get("cost") or {}).get("total", ""), "floor_area_m2": r.get("floor_area_m2") or "",
            "energy_rating": r.get("energy_rating") or "",
        })
    append_csv(state.listings_path, LISTING_FIELDS, rows)
    append_csv(state.run_log_path, RUN_LOG_FIELDS, [{
        "run_at": out["now"], "alert_emails_read": emails_read,
        "listings_extracted": len(out["results"]) + len(out["excluded"]),
        "new_listings_reported": len(out["results"]), "emails_not_parsed": not_parsed,
        "alert_senders": senders, "health": health, "status": status,
    }])


# ------------------------------------------------------------------------ digest
def digest(state: State, end: dt.date, pack_dir: Path | None, insight: str = "") -> dict:
    rows = read_csv(state.listings_path)
    sym = state.currency_symbol

    def in_window(r, start, stop):
        d = parse_dt(r.get("first_reported_at"))
        return d is not None and start <= d.date() <= stop

    this_start = end - dt.timedelta(days=6)
    prev_start, prev_end = this_start - dt.timedelta(days=7), this_start - dt.timedelta(days=1)
    week = [r for r in rows if in_window(r, this_start, end)]
    prev = [r for r in rows if in_window(r, prev_start, prev_end)]
    first = min((parse_dt(r["first_reported_at"]).date() for r in rows if parse_dt(r.get("first_reported_at"))), default=None)
    enough_history = first is not None and first <= prev_start

    def count(rs, tier=None):
        # listings with no matched area ("check location") count only in the total, as in the alerts
        return len([r for r in rs if r.get("event") == "new"
                    and (tier is None or (r.get("tier") == tier and r.get("area_id")))])

    lines = []
    to_check = len([r for r in week if r.get("event") == "new" and not r.get("area_id")])
    headline = (f"{count(week)} new listings this week: {count(week, 'act_now')} act now, "
                f"{count(week, 'stretch')} stretch, {count(week, 'over_budget')} over budget"
                + (f", {to_check} to check location." if to_check else "."))
    if enough_history:
        headline += f" Previous week: {count(prev)} new, {count(prev, 'act_now')} act now."
    else:
        headline += " Less than two weeks of data, so no week-on-week comparison yet."
    lines += ["SUMMARY", headline, ""]
    if insight:
        lines += ["WHAT THIS MEANS", insight.strip(), ""]
    table = []

    lines.append("BY AREA AND BEDROOMS")
    lines.append(f"{'Area':<24}{'Beds':>5}{'Listings':>10}{'Median':>10}{'Lowest':>10}{'vs market':>11}")
    groups: dict[tuple, list] = {}
    for r in week:
        if r.get("event") != "new":
            continue
        groups.setdefault((r.get("area_label") or "Other", r.get("bedrooms") or "?"), []).append(r)
    for (area, beds), rs in sorted(groups.items()):
        rents = [float(r["rent_monthly"]) for r in rs if r.get("rent_monthly")]
        pcts = [float(r["benchmark_pct"]) for r in rs if r.get("benchmark_pct") not in (None, "")]
        med = money(statistics.median(rents), sym) if rents else "n/a"
        low = money(min(rents), sym) if rents else "n/a"
        vs = f"{statistics.median(pcts):+.0f}%" if pcts else "n/a"
        lines.append(f"{area[:23]:<24}{str(beds):>5}{len(rs):>10}{med:>10}{low:>10}{vs:>11}")
        table.append({"area": area, "beds": beds, "n": len(rs), "median": med, "lowest": low, "vs": vs,
                      "vs_value": statistics.median(pcts) if pcts else None})
    if not groups:
        lines.append("No listings this week.")
    lines.append("")

    best = sorted([r for r in week if r.get("tier") in ("act_now", "stretch") and r.get("event") == "new" and r.get("area_id")],
                  key=lambda r: -float(r.get("fit_score") or 0))[:5]
    lines.append("BEST FIVE THIS WEEK")
    if best:
        for i, r in enumerate(best, 1):
            lines.append(f"{i}. Fit {r['fit_score']}/100 · {money(r['rent_monthly'], sym)} · {r['bedrooms']} bed / {r['bathrooms'] or '?'} bath · {r['address']} · {r['area_label']}")
            if r.get("travel_summary"):
                lines.append(f"   {r['travel_summary']}")
            lines.append(f"   {r['listing_url']}")
    else:
        lines.append("None within budget or stretch this week.")
    lines.append("")

    changes = [r for r in week if r.get("event") in ("price_change", "relisted")]
    if changes:
        lines.append("PRICE CHANGES AND RE-LISTS")
        for r in changes:
            lines.append(f"- {r['flags'].split(';')[0]} · {r['address']} · {r['listing_url']}")
        lines.append("")

    runs = [r for r in read_csv(state.run_log_path) if in_window({"first_reported_at": r.get("run_at")}, this_start, end)]
    lines.append("PIPELINE HEALTH")
    lines.append(f"Runs: {len(runs)} · alert emails read: {sum(int(r.get('alert_emails_read') or 0) for r in runs)} · emails not read: {sum(int(r.get('emails_not_parsed') or 0) for r in runs)}")
    last_by_source: dict[str, str] = {}
    for r in rows:
        if r.get("source"):
            last_by_source[r["source"]] = max(last_by_source.get(r["source"], ""), r.get("first_reported_at", ""))
    for s in (state.sources.get("sources") or []):
        name = s.get("name") or s.get("id")
        lines.append(f"Last listing from {name}: {last_by_source.get(name, 'none yet')[:16].replace('T', ' ')}")
    warnings = [r["health"].removeprefix("checked: ") for r in runs
                if r.get("health") and r["health"] != "checked: no warnings"]
    if warnings:
        lines.append("Warnings this week: " + " | ".join(sorted(set(warnings))))
    reminders = []
    if end.day <= 7:  # first digest of the month
        reminders = ["Check each site's saved searches are still switched on."]
        reminders += [str(x) for x in ((state.profile.get("alerts") or {}).get("monthly_reminders") or [])]
        for x in reminders:
            lines.append("Monthly reminder: " + x)
    subject = f"Weekly listing summary – week ending {end:%d %b}"
    health = {
        "runs": len(runs),
        "emails_read": sum(int(r.get("alert_emails_read") or 0) for r in runs),
        "not_read": sum(int(r.get("emails_not_parsed") or 0) for r in runs),
        "last_by_source": [(s.get("name") or s.get("id"),
                            last_by_source.get(s.get("name") or s.get("id"), "none yet")[:16].replace("T", " "))
                           for s in (state.sources.get("sources") or [])],
        "warnings": sorted(set(warnings)),
    }
    data = {"end": end, "counts": {"new": count(week), "act_now": count(week, "act_now"),
                                   "stretch": count(week, "stretch"), "over_budget": count(week, "over_budget"),
                                   "to_check": to_check},
            "headline": headline, "insight": insight.strip(), "table": table, "best": best,
            "changes": changes, "health": health, "reminders": reminders}
    return {"subject": subject, "body": "\n".join(lines).rstrip() + "\n", "html": render_digest_html(data, state),
            "notification": f"Weekly summary: {count(week)} new, {count(week, 'act_now')} act now. Details emailed."}


def render_digest_html(d: dict, state: State) -> str:
    sym = state.currency_symbol
    c = d["counts"]
    chips = [_pill(f'{c["new"]} new', C["blue"], C["blue_bg"], 13)]
    for key, label in (("act_now", "act now"), ("stretch", "stretch"), ("over_budget", "over budget")):
        if c[key]:
            _, fg, bg = TIER_STYLE[key]
            chips.append(_pill(f"{c[key]} {label}", fg, bg, 13))
    if c["to_check"]:
        chips.append(_pill(f'{c["to_check"]} to check', C["grey"], C["grey_bg"], 13))

    def card(inner: str, pad: str = "16px 18px") -> str:
        return (f'<tr><td style="padding:0 24px 14px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                f'style="background:{C["card"]};border:1px solid {C["line"]};border-radius:12px;"><tr><td style="padding:{pad};">{inner}</td></tr></table></td></tr>')

    def heading(text: str, colour: str) -> str:
        return (f'<tr><td style="padding:22px 24px 8px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
                f'<td style="width:4px;background:{colour};border-radius:2px;">&nbsp;</td>'
                f'<td style="padding-left:10px;font-size:13px;font-weight:700;color:{colour};text-transform:uppercase;letter-spacing:.8px;">{_e(text)}</td>'
                "</tr></table></td></tr>")

    out = [
        f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="color-scheme" content="light only"><title>Weekly listing summary</title></head><body style="margin:0;padding:0;background:{C["page"]};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{C["page"]};{FONT}"><tr><td align="center" style="padding:20px 10px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#fafafa;border-radius:14px;overflow:hidden;border:1px solid {C["line"]};">',
        f'<tr><td style="background:{C["head"]};padding:20px 24px;"><div style="font-size:12px;color:#cbd5e1;letter-spacing:.8px;text-transform:uppercase;">'
        f'Weekly summary · week ending {_e(d["end"].strftime("%a %d %b"))}</div>'
        f'<div style="font-size:20px;font-weight:700;color:#ffffff;margin-top:4px;">Your listing week at a glance</div></td></tr>',
        f'<tr><td style="padding:16px 24px 6px;font-size:14px;color:{C["ink"]};"><div>{"".join(chips)}</div>'
        f'<div style="margin-top:6px;color:{C["muted"]};font-size:13px;">{_e(d["headline"])}</div></td></tr>',
    ]
    if d["insight"]:
        out.append(heading("What this means", C["accent"]))
        out.append(card(f'<div style="font-size:14px;line-height:21px;color:{C["ink"]};">{_e(d["insight"])}</div>'))
    out.append(heading("By area and bedrooms", C["head"]))
    if d["table"]:
        th = f'style="padding:8px 6px;font-size:11px;color:{C["muted"]};text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid {C["line"]};"'
        rows = [f'<tr><td {th}>Area</td><td {th} align="center">Beds</td><td {th} align="right">Listings</td>'
                f'<td {th} align="right">Median</td><td {th} align="right">Lowest</td><td {th} align="right">vs market</td></tr>']
        for t in d["table"]:
            v = t["vs_value"]
            colour = C["muted"] if v is None or abs(v) < 3 else (C["green"] if v < 0 else C["red"])
            td = f'style="padding:9px 6px;font-size:13px;color:{C["ink"]};border-bottom:1px solid {C["line"]};"'
            rows.append(f'<tr><td {td}>{_e(t["area"])}</td><td {td} align="center">{_e(t["beds"])}</td><td {td} align="right">{t["n"]}</td>'
                        f'<td {td} align="right"><b>{_e(t["median"])}</b></td><td {td} align="right">{_e(t["lowest"])}</td>'
                        f'<td {td} align="right"><b style="color:{colour};">{_e(t["vs"])}</b></td></tr>')
        out.append(card('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">' + "".join(rows) + "</table>", "6px 12px"))
    else:
        out.append(card(f'<div style="font-size:14px;color:{C["muted"]};">No listings this week.</div>'))
    out.append(heading("Best five this week", C["green"]))
    if d["best"]:
        items = []
        for i, r in enumerate(d["best"], 1):
            score = int(float(r.get("fit_score") or 0))
            fg, bg = (C["green"], C["green_bg"]) if score >= 70 else (C["amber"], C["amber_bg"]) if score >= 50 else (C["grey"], C["grey_bg"])
            items.append(
                f'<tr><td valign="top" style="padding:10px 10px 10px 0;border-bottom:1px solid {C["line"]};width:44px;">'
                f'<div style="width:40px;padding:5px 0;border-radius:8px;background:{bg};color:{fg};text-align:center;font-weight:700;font-size:15px;">{score}</div></td>'
                f'<td valign="top" style="padding:10px 0;border-bottom:1px solid {C["line"]};font-size:13px;color:{C["ink"]};">'
                f'<b style="font-size:15px;">{_e(money(r.get("rent_monthly"), sym))}</b> <span style="color:{C["muted"]};">· {_e(r.get("bedrooms"))} bed / {_e(r.get("bathrooms") or "?")} bath · {_e(r.get("area_label"))}</span><br>'
                f'<a href="{_e(r.get("listing_url"))}" style="color:{C["accent"]};text-decoration:none;font-weight:600;">{_e(r.get("address"))}</a>'
                + (f'<div style="color:{C["muted"]};font-size:12px;margin-top:2px;">{_e(r["travel_summary"])}</div>' if r.get("travel_summary") else "")
                + ('<div style="margin-top:6px;">' + _pill("possible scam – verify before paying anything", C["red"], C["red_bg"]) + "</div>"
                   if "possible scam" in (r.get("flags") or "") else "")
                + "</td></tr>")
        out.append(card('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">' + "".join(items) + "</table>", "4px 18px"))
    else:
        out.append(card(f'<div style="font-size:14px;color:{C["muted"]};">None within budget or stretch this week.</div>'))
    if d["changes"]:
        out.append(heading("Price changes and re-lists", C["blue"]))
        items = "".join(
            f'<li style="margin:6px 0;"><b>{_e(r["flags"].split(";")[0])}</b> · '
            f'<a href="{_e(r["listing_url"])}" style="color:{C["accent"]};text-decoration:none;">{_e(r["address"])}</a></li>'
            for r in d["changes"])
        out.append(card(f'<ul style="margin:0;padding-left:18px;font-size:13px;color:{C["ink"]};">{items}</ul>'))
    h = d["health"]
    ok = not h["warnings"] and not h["not_read"]
    out.append(heading("Pipeline health", C["green"] if ok else C["red"]))
    src = "".join(f'<tr><td style="padding:3px 12px 3px 0;font-size:13px;color:{C["muted"]};">Last listing from {_e(n)}</td>'
                  f'<td style="padding:3px 0;font-size:13px;color:{C["ink"]};">{_e(t)}</td></tr>' for n, t in h["last_by_source"])
    inner = (f'<div style="font-size:13px;color:{C["ink"]};">{h["runs"]} run{"s" if h["runs"] != 1 else ""} · {h["emails_read"]} alert email{"s" if h["emails_read"] != 1 else ""} read · '
             f'{h["not_read"]} could not be read</div>'
             f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:8px;">{src}</table>')
    if h["warnings"]:
        inner += ('<div style="margin-top:10px;">' + "".join(_pill(w, C["red"], C["red_bg"]) for w in h["warnings"]) + "</div>")
    out.append(card(inner))
    if d["reminders"]:
        out.append(card('<b style="font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:' + C["amber"] + ';">Monthly reminders</b>'
                        '<ul style="margin:6px 0 0;padding-left:18px;font-size:13px;color:' + C["ink"] + ';">'
                        + "".join(f'<li style="margin:4px 0;">{_e(x)}</li>' for x in d["reminders"]) + "</ul>"))
    out.append(f'<tr><td style="padding:8px 24px 24px;font-size:11px;line-height:16px;color:{C["muted"]};">'
               f'Market comparison uses open RTB data; travel times: {_e(travel_credit(state))}.<br>'
               "Sent by listing-alert-agent from your own saved-search alerts.</td></tr>")
    out.append("</table></td></tr></table></body></html>")
    return "".join(out)


# ------------------------------------------------------------------ decision aids
FEEDBACK_FIELDS = ["recorded_at", "listing_url", "verdict", "reason", "area_id", "rent_monthly", "per_person",
                   "bedrooms", "property_type", "tier", "fit_score", "first_minutes", "first_anchor"]


def find_listings(state: State, refs: list[str]) -> list[dict]:
    """Latest row in listings.csv for each reference (a listing link, or words from the address)."""
    rows = read_csv(state.listings_path)
    found = []
    for ref in refs:
        ref_url = canonical_url(ref) if ref.startswith("http") else ""
        words = [w for w in re.sub(r"[^\w\s]", " ", ref.lower()).split() if w]
        match = None
        for r in rows:  # later rows win
            if ref_url and r.get("listing_url") == ref_url:
                match = r
            elif not ref_url and words and all(w in (r.get("address") or "").lower() for w in words):
                match = r
        found.append(match or {"missing": ref})
    return found


def _minutes_from_summary(summary: str) -> tuple[str, float | None]:
    m = re.match(r"\s*([^:|]+):\s*([\d.]+) min", summary or "")
    return (m.group(1).strip(), float(m.group(2))) if m else ("", None)


def compare(state: State, refs: list[str]) -> dict:
    """Side-by-side facts for 2-5 listings, with the strongest option per criterion."""
    sym = state.currency_symbol
    items = find_listings(state, refs)
    rows = [r for r in items if "missing" not in r]
    table = []
    for r in rows:
        anchor, minutes = _minutes_from_summary(r.get("travel_summary", ""))
        people = int(r.get("people") or 1)
        table.append({
            "address": r.get("address"), "url": r.get("listing_url"), "source": r.get("source"),
            "rent": money(r.get("rent_monthly"), sym), "your_share": money(float(r["rent_monthly"]) / people, sym) if r.get("rent_monthly") else "n/a",
            "beds_baths": f"{r.get('bedrooms') or '?'} / {r.get('bathrooms') or '?'}", "type": r.get("property_type"),
            "area": r.get("area_label"), "tier": r.get("tier"), "fit": r.get("fit_score"),
            "travel": r.get("travel_summary", ""), "vs_market": (f"{float(r['benchmark_pct']):+.0f}%" if r.get("benchmark_pct") not in (None, "") else "n/a"),
            "cost": money(r.get("cost_monthly"), sym) if r.get("cost_monthly") else "n/a",
            "flags": r.get("flags", ""), "first_minutes": minutes, "first_anchor": anchor,
            "_rent": float(r.get("rent_monthly") or 0) / people, "_fit": float(r.get("fit_score") or 0),
            "_pct": float(r["benchmark_pct"]) if r.get("benchmark_pct") not in (None, "") else None,
            "_cost": float(r["cost_monthly"]) if r.get("cost_monthly") else None,
        })
    best = {}
    if len(table) >= 2:
        def pick(key, values):
            vals = [(v, t["address"]) for t, v in zip(table, values) if v is not None]
            if vals:
                best[key] = min(vals)[1]
        pick("lowest_share", [t["_rent"] or None for t in table])
        pick("shortest_trip", [t["first_minutes"] for t in table])
        pick("best_value_vs_market", [t["_pct"] for t in table])
        pick("lowest_estimated_cost", [t["_cost"] for t in table])
        best["highest_fit"] = max(table, key=lambda t: t["_fit"])["address"]
    for t in table:
        for k in ("_rent", "_fit", "_pct", "_cost"):
            t.pop(k)
    return {"listings": table, "best": best, "not_found": [i["missing"] for i in items if "missing" in i]}


def record_feedback(state: State, ref: str, verdict: str, reason: str, now: dt.datetime) -> dict:
    match = find_listings(state, [ref])[0]
    if "missing" in match:
        raise SystemExit(f"No reported listing matches '{ref}'.")
    anchor, minutes = _minutes_from_summary(match.get("travel_summary", ""))
    row = {"recorded_at": local_now(state.profile, now).isoformat(timespec="seconds"), "listing_url": match["listing_url"],
           "verdict": verdict, "reason": reason, "area_id": match.get("area_id", ""), "rent_monthly": match.get("rent_monthly", ""),
           "per_person": match.get("per_person", ""), "bedrooms": match.get("bedrooms", ""),
           "property_type": match.get("property_type", ""), "tier": match.get("tier", ""), "fit_score": match.get("fit_score", ""),
           "first_minutes": "" if minutes is None else minutes, "first_anchor": anchor}
    append_csv(state.root / "data" / "feedback.csv", FEEDBACK_FIELDS, [row])
    return row


def tune_suggestions(state: State) -> dict:
    """Patterns in the user's verdicts, turned into precise, optional rule changes. Nothing is applied here."""
    rows = read_csv(state.root / "data" / "feedback.csv")
    no = [r for r in rows if r.get("verdict") in ("no", "not_for_me")]
    yes = [r for r in rows if r.get("verdict") in ("yes", "maybe")]
    suggestions = []
    # 1. travel: most rejections beyond a time that accepted listings stay within
    rej_t = sorted(float(r["first_minutes"]) for r in no if r.get("first_minutes") not in (None, ""))
    acc_t = sorted(float(r["first_minutes"]) for r in yes if r.get("first_minutes") not in (None, ""))
    travel_words = ("far", "commute", "travel", "distance", "drive")
    travel_no = [r for r in no if any(w in (r.get("reason") or "").lower() for w in travel_words)]
    if len(travel_no) >= 2 and rej_t:
        cut = min(float(r["first_minutes"]) for r in travel_no if r.get("first_minutes") not in (None, ""))
        if not acc_t or max(acc_t) < cut:
            anchor = travel_no[0].get("first_anchor") or "your main place"
            areas = [a for a in (state.profile.get("areas") or []) if a.get("type") == "travel_time"]
            target = areas[0] if areas else None
            suggestions.append({
                "finding": f"{len(travel_no)} listings rejected as too far were {cut:.0f} min or more from {anchor}; "
                           f"{'none' if not acc_t else 'every'} accepted listing {'was given' if not acc_t else f'was under {max(acc_t):.0f} min'}.",
                "change": (f"areas[{target['id']}].max_minutes: {target.get('max_minutes')} -> {int(cut) - 1}" if target else
                           f"lower the travel limit for {anchor} below {cut:.0f} min"),
            })
    # 2. repeated reasons become deal-breakers or must-haves
    counts: dict[str, int] = {}
    for r in no:
        reason = (r.get("reason") or "").strip().lower()
        if reason and not any(w in reason for w in travel_words) and "price" not in reason and "expensive" not in reason:
            counts[reason] = counts.get(reason, 0) + 1
    for reason, n in sorted(counts.items(), key=lambda x: -x[1]):
        if n >= 2:
            if reason.startswith("no "):
                suggestions.append({"finding": f"'{reason}' given {n} times.", "change": f"criteria.must_haves: add '{reason[3:]}'"})
            else:
                suggestions.append({"finding": f"'{reason}' given {n} times.", "change": f"criteria.deal_breakers: add '{reason}'"})
    # 3. price: rejections for cost while within budget
    price_no = [r for r in no if any(w in (r.get("reason") or "").lower() for w in ("price", "expensive", "cost"))]
    if len(price_no) >= 2:
        shares = [float(r.get("per_person") or r.get("rent_monthly") or 0) for r in price_no]
        budget = (state.profile.get("budget") or {}).get("amount")
        suggestions.append({"finding": f"{len(price_no)} listings rejected on price; the cheapest of them cost you {money(min(shares), state.currency_symbol)}.",
                            "change": f"budget.amount: {budget} -> {int(min(shares)) - 1} (or lower stretch_pct)"})
    return {"verdicts": {"yes": len([r for r in rows if r.get('verdict') == 'yes']), "maybe": len([r for r in rows if r.get('verdict') == 'maybe']),
                         "no": len(no)}, "suggestions": suggestions,
            "note": "Suggestions only. Apply a change after the user agrees, then run validate."}


STATUS_ORDER = ["new", "shortlisted", "contacted", "viewing", "applied", "offer", "not_for_me", "rejected", "let_agreed"]
VERDICT_TO_STATUS = {"yes": "shortlisted", "maybe": "new", "no": "not_for_me"}


def dashboard_data(state: State, now: dt.datetime) -> dict:
    """Rows for the private dashboard: listings (latest event per listing, with coordinates and status),
    runs (one row per run) and the important places. Facts only; no contact details exist to export."""
    rows = read_csv(state.listings_path)
    coords = {}
    for r in state.travel:
        coords.setdefault(r.get("place"), (r.get("lat"), r.get("lon")))
    status = {}
    for f in read_csv(state.root / "data" / "feedback.csv"):
        status[f.get("listing_url")] = (VERDICT_TO_STATUS.get(f.get("verdict"), f.get("verdict")), f.get("recorded_at"), f.get("reason", ""))
    latest = {}
    for r in rows:
        key = r.get("listing_url") or r.get("dedupe_key")
        first = latest.get(key, {}).get("first_seen") or r.get("first_reported_at")
        latest[key] = {**r, "first_seen": first}
    listings = []
    index = place_index(state)
    for key, r in latest.items():
        if not r.get("place"):  # older rows (for example migrated ones) may lack the matched place
            found = match_place(r.get("address") or "", index)
            r = {**r, "place": found["place"] if found else ""}
        lat, lon = coords.get(r.get("place"), (None, None))
        st, st_at, st_reason = status.get(r.get("listing_url"), ("new", "", ""))
        anchor, minutes = _minutes_from_summary(r.get("travel_summary", ""))
        def num(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return None
        listings.append({
            "listing_url": r.get("listing_url"), "address": r.get("address"), "source": r.get("source"),
            "area": r.get("area_label") or "Check location", "place": r.get("place") or "",
            "bedrooms": num(r.get("bedrooms")), "bathrooms": num(r.get("bathrooms")), "property_type": r.get("property_type"),
            "rent": num(r.get("rent_monthly")), "your_share": num(r.get("per_person")) or num(r.get("rent_monthly")),
            "tier": r.get("tier"), "fit": num(r.get("fit_score")), "vs_market_pct": num(r.get("benchmark_pct")),
            "cost_monthly": num(r.get("cost_monthly")), "minutes": minutes, "anchor": anchor,
            "first_seen": r.get("first_seen"), "last_event": r.get("event"), "last_event_at": r.get("first_reported_at"),
            "flags": r.get("flags", ""), "status": st, "status_at": st_at, "status_note": st_reason,
            "lat": num(lat), "lon": num(lon),
        })
    listings.sort(key=lambda x: x.get("last_event_at") or "", reverse=True)
    runs = [{"run_at": r.get("run_at"), "emails_read": int(r.get("alert_emails_read") or 0),
             "reported": int(r.get("new_listings_reported") or 0), "not_read": int(r.get("emails_not_parsed") or 0),
             "health": (r.get("health") or "").removeprefix("checked: "), "status": r.get("status")}
            for r in read_csv(state.run_log_path)]
    places = [{"kind": "important", "name": a.get("label"), "region": "", "lat": a.get("lat"), "lon": a.get("lon")}
              for a in (state.places.get("anchors") or []) if a.get("lat") is not None]
    places += [{"kind": "search", "name": name, "region": "", "lat": float(lat), "lon": float(lon)}
               for name, (lat, lon) in coords.items() if lat not in (None, "")]
    return {"listings": listings, "runs": runs, "places": places,
            "generated_at": local_now(state.profile, now).isoformat(timespec="seconds")}


# ------------------------------------------------------------------------ doctor
def schema_problems(state: State) -> list[str]:
    """Full JSON Schema check when the jsonschema package is installed (optional)."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return []
    schema_dir = Path(__file__).resolve().parents[3] / "schemas"
    problems = []
    for name, data in (("profile", state.profile), ("sources", state.sources), ("places", state.places)):
        path = schema_dir / f"{name}.schema.json"
        if not path.exists():
            continue
        validator = jsonschema.Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))
        for err in validator.iter_errors(json.loads(json.dumps(data, default=str))):
            where = ".".join(str(x) for x in err.absolute_path) or "(top level)"
            problems.append(f"{name}.yaml: {where}: {err.message}")
    return problems


def validate(state: State) -> list[str]:
    problems = schema_problems(state)
    p = state.profile
    for key in ("owner", "goal", "criteria", "budget", "areas"):
        if key not in p:
            problems.append(f"profile.yaml: missing '{key}'")
    owner = p.get("owner") or {}
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", str(owner.get("email", ""))):
        problems.append("profile.yaml: owner.email is not a valid address")
    budget = p.get("budget") or {}
    if budget.get("model") not in ("total", "per_person"):
        problems.append("profile.yaml: budget.model must be 'total' or 'per_person'")
    if not isinstance(budget.get("amount"), (int, float)) or budget.get("amount", 0) <= 0:
        problems.append("profile.yaml: budget.amount must be a positive number")
    anchor_ids = {a.get("id") for a in (state.places.get("anchors") or [])}
    for area in p.get("areas") or []:
        if area.get("type") == "travel_time" and area.get("anchor") not in anchor_ids:
            problems.append(f"profile.yaml: area '{area.get('id')}' uses unknown anchor '{area.get('anchor')}'")
        if area.get("type") not in ("travel_time", "region"):
            problems.append(f"profile.yaml: area '{area.get('id')}' type must be travel_time or region")
    srcs = state.sources.get("sources") or []
    if not srcs:
        problems.append("sources.yaml: no sources listed")
    for s in srcs:
        if not s.get("senders"):
            problems.append(f"sources.yaml: source '{s.get('id')}' has no sender addresses")
    for a in state.places.get("anchors") or []:
        for m in a.get("modes") or ["driving"]:
            if m not in TRAVEL_MODES:
                problems.append(f"places.yaml: anchor '{a.get('id')}' has unknown mode '{m}'")
    return problems


def doctor(state: State, now: dt.datetime) -> list[str]:
    report = []
    problems = validate(state)
    report.append("Config: " + ("valid" if not problems else f"{len(problems)} problem(s)"))
    report.extend("  - " + x for x in problems)
    anchors = state.places.get("anchors") or []
    places = {r.get("place") for r in state.travel}
    report.append(f"Travel cache: {len(places)} places × {len(anchors)} important places ({len(state.travel)} rows)")
    if not state.travel:
        report.append("  - No travel times cached. Run setup step 'travel cache' so alerts show real travel times.")
    else:
        oldest = min((parse_dt(r.get("computed_at")) for r in state.travel if parse_dt(r.get("computed_at"))), default=None)
        if oldest and (now - oldest).days > 45:
            report.append(f"  - Travel times are {(now - oldest).days} days old; refresh monthly.")
    runs = read_csv(state.run_log_path)
    if not runs:
        report.append("Runs: none yet")
    else:
        last = parse_dt(runs[-1].get("run_at"))
        report.append(f"Runs: {len(runs)}; last {runs[-1].get('run_at')} ({runs[-1].get('status')})")
        storage = ((state.profile.get("storage") or {}).get("type") or "github")
        limit_h = 26 if storage == "drive" else 3   # Drive storage records quiet runs only once a day
        if last and (now - last).total_seconds() > limit_h * 3600:
            report.append(f"  - No run recorded in the last {limit_h} hours. Check the schedule (routine or scheduled task) is on.")
        recent = runs[-24:]
        failed = sum(int(r.get("emails_not_parsed") or 0) for r in recent)
        if failed:
            report.append(f"  - {failed} alert email(s) could not be read in the last {len(recent)} runs; the layout may have changed.")
    rows = read_csv(state.listings_path)
    for s in state.sources.get("sources") or []:
        name = s.get("name") or s.get("id")
        last = max((r.get("first_reported_at", "") for r in rows if r.get("source") == name), default="")
        report.append(f"Source {name}: last listing {last[:16].replace('T', ' ') or 'none yet'}")
    return report


def sender_matches(sender: str, patterns: list[str]) -> bool:
    sender = sender.strip().lower()
    return any(fnmatch.fnmatch(sender, p.strip().lower()) for p in patterns)


def health_due(state: State, now: dt.datetime) -> bool:
    """Health checks run once a day: on the first run of the day that has not already checked."""
    today = local_now(state.profile, now).date()
    for row in read_csv(state.run_log_path):
        when = parse_dt(row.get("run_at"))
        if when is None or not (row.get("health") or "").startswith("checked"):
            continue
        if when.tzinfo is not None:
            when = local_now(state.profile, when)
        if when.date() == today:
            return False
    return True


def health_checks(state: State, now: dt.datetime, current_senders: list[str], not_parsed_now: int) -> list[str]:
    """Source silence and parse-failure warnings, worded for the alert email."""
    warnings = []
    runs = read_csv(state.run_log_path)
    first_run = parse_dt(runs[0].get("run_at")) if runs else now
    for src in state.sources.get("sources") or []:
        patterns = src.get("senders") or []
        silence = float(src.get("silence_hours", 48))
        last = None
        if any(sender_matches(s, patterns) for s in current_senders):
            last = now
        else:
            for row in reversed(runs):
                senders = [s for s in (row.get("alert_senders") or "").split(";") if s and not any(ch in s for ch in "*?[")]
                if any(sender_matches(s, patterns) for s in senders):
                    last = parse_dt(row.get("run_at"))
                    break
        name = src.get("name") or src.get("id")
        if last is None:
            if first_run and (now - first_run).total_seconds() / 3600 >= silence:
                warnings.append(f"No alert emails from {name} since tracking began on {first_run:%d %b}. Check the saved search is on and its emails are not going to spam.")
        elif (now - last).total_seconds() / 3600 >= silence:
            warnings.append(f"No alert emails from {name} for {int((now - last).total_seconds() // 3600)} hours (limit {silence:.0f}). Check the saved search is still on.")
    recent = runs[-24:]
    failed = sum(int(r.get("emails_not_parsed") or 0) for r in recent) + not_parsed_now
    if failed:
        warnings.append(f"{failed} alert email(s) could not be read in the last day of runs. The email layout may have changed; run the doctor skill.")
    return warnings


def in_quiet_hours(profile: dict, now: dt.datetime) -> bool:
    quiet = (profile.get("alerts") or {}).get("quiet_hours") or {}
    try:
        start = dt.time.fromisoformat(quiet["start"])
        end = dt.time.fromisoformat(quiet["end"])
    except (KeyError, TypeError, ValueError):
        return False
    t = now.time().replace(tzinfo=None)
    return (start <= t or t < end) if start > end else (start <= t < end)


def local_now(profile: dict, now: dt.datetime) -> dt.datetime:
    tz_name = (profile.get("owner") or {}).get("timezone")
    if tz_name and ZoneInfo is not None:
        try:
            return now.astimezone(ZoneInfo(tz_name))
        except Exception:  # unknown zone: keep the given time
            return now
    return now


# ------------------------------------------------------------------ travel cache
def ors_request(path: str, key: str, payload: dict | None = None, params: dict | None = None) -> dict:
    url = "https://api.openrouteservice.org" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", key)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", f"listing-alert-agent/{VERSION}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


COARSE_LAYERS = {"county", "macrocounty", "region", "macroregion", "country", "dependency", "empire", "continent"}
GEOCODE_FIELDS = ["query", "lat", "lon", "layer", "label", "status", "checked_at"]


def geocode(name: str, key: str, country: str | None) -> dict | None:
    """First openrouteservice geocoding result: lat, lon, layer and label."""
    params = {"text": name, "size": 1}
    if country:
        params["boundary.country"] = country
    data = ors_request("/geocode/search", key, params=params)
    feats = data.get("features") or []
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"]
    props = feats[0].get("properties") or {}
    return {"lat": lat, "lon": lon, "layer": props.get("layer", ""), "label": props.get("label", "")}


def check_geocodes(results: dict[str, dict]) -> dict[str, str]:
    """Reject results that are too coarse or shared by several places. Returns {query: problem}."""
    problems = {}
    by_point: dict[tuple, list[str]] = {}
    for q, r in results.items():
        if not r:
            problems[q] = "not found"
            continue
        if r.get("layer") in COARSE_LAYERS:
            problems[q] = f"only matched a {r['layer']} ({r.get('label')})"
            continue
        by_point.setdefault((round(float(r["lat"]), 4), round(float(r["lon"]), 4)), []).append(q)
    for point, qs in by_point.items():
        if len(qs) > 1:
            for q in qs:
                problems[q] = f"same point as {', '.join(x for x in qs if x != q)} ({results[q].get('label')})"
    return problems


def build_travel_cache(state: State, dry_run: bool = False) -> dict:
    """Geocode (with a reusable cache), check the results, then request travel-time matrices.

    Places with explicit lat/lon in places.yaml are never geocoded. Geocodes are cached in
    data/geocode-cache.csv so a re-run spends no quota on places already found. Results that
    match only a county, or share a point with another place, are rejected and reported.
    """
    key = os.environ.get("ORS_API_KEY", "")
    if not key and not dry_run:
        raise SystemExit("Set ORS_API_KEY (free key from openrouteservice.org) to build the travel cache.")
    country = (state.profile.get("goal") or {}).get("country")
    anchors = state.places.get("anchors") or []
    search = [p if isinstance(p, dict) else {"name": p} for p in (state.places.get("search_places") or [])]
    if dry_run:
        return {"anchors": len(anchors), "places": len(search),
                "to_geocode": len([p for p in search if p.get("lat") is None]) + len([a for a in anchors if a.get("lat") is None])}
    cache_path = state.root / "data" / "geocode-cache.csv"
    cache = {r["query"]: r for r in read_csv(cache_path)}
    warnings, new_rows, results = [], [], {}
    quota_hit = False
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def lookup(query: str) -> dict | None:
        nonlocal quota_hit
        if query in cache and cache[query].get("status") == "ok":
            c = cache[query]
            return {"lat": float(c["lat"]), "lon": float(c["lon"]), "layer": c.get("layer", ""), "label": c.get("label", "")}
        if quota_hit:
            return None
        try:
            r = geocode(query, key, country)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                quota_hit = True
                warnings.append("Geocoding quota or rate limit reached; remaining places were skipped. Re-run later: found places are cached.")
                return None
            raise
        return r

    for a in anchors:
        if a.get("lat") is None:
            r = lookup(a.get("address") or a.get("label"))
            if r and r.get("layer") not in COARSE_LAYERS:
                a["lat"], a["lon"] = r["lat"], r["lon"]
                warnings.append(f"Important place '{a.get('label')}' was geocoded to {r.get('label')}. Check it on a map and write lat/lon into places.yaml.")
            else:
                warnings.append(f"Important place '{a.get('label')}' could not be placed; write lat/lon into places.yaml.")
    queries = {}
    for p in search:
        if p.get("lat") is None:
            q = p["name"] + (", " + p["region"] if p.get("region") else "")
            queries[q] = p
            results[q] = lookup(q)
    problems = check_geocodes(results)
    for q, r in results.items():
        status = "ok" if r and q not in problems else "rejected"
        if r and (q not in cache or cache[q].get("status") != status):
            new_rows.append({"query": q, "lat": r["lat"], "lon": r["lon"], "layer": r.get("layer", ""),
                             "label": r.get("label", ""), "status": status, "checked_at": stamp})
        if status == "ok":
            queries[q]["lat"], queries[q]["lon"] = r["lat"], r["lon"]
    for q, why in sorted(problems.items()):
        if not (quota_hit and why == "not found"):
            warnings.append(f"Skipped '{q}': {why}. Try a well-known neighbourhood name or write lat/lon into places.yaml.")
    if new_rows:
        merged = {**cache, **{r["query"]: r for r in new_rows}}
        with open(cache_path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=GEOCODE_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(merged.values())
    places = [p for p in search if p.get("lat") is not None]
    rows = []
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for mode in sorted({m for a in anchors for m in (a.get("modes") or ["driving"])}):
        if mode not in ORS_PROFILES:
            continue
        mode_anchors = [a for a in anchors if mode in (a.get("modes") or ["driving"]) and a.get("lat") is not None]
        for start in range(0, len(places), 45):
            chunk = places[start:start + 45]
            locs = [[p["lon"], p["lat"]] for p in chunk] + [[a["lon"], a["lat"]] for a in mode_anchors]
            payload = {"locations": locs, "sources": list(range(len(chunk))),
                       "destinations": list(range(len(chunk), len(locs))), "metrics": ["duration", "distance"], "units": "km"}
            data = ors_request(f"/v2/matrix/{ORS_PROFILES[mode]}", key, payload=payload)
            for i, p in enumerate(chunk):
                for j, a in enumerate(mode_anchors):
                    dur = data["durations"][i][j]
                    dist = data["distances"][i][j]
                    if dur is None:
                        continue
                    rows.append({"place": p["name"], "region": p.get("region", ""), "lat": p["lat"], "lon": p["lon"],
                                 "anchor_id": a["id"], "mode": mode, "minutes": round(dur / 60, 1),
                                 "km": round(dist, 1), "method": "openrouteservice matrix", "confidence": "area",
                                 "computed_at": stamp})
    if not rows:
        warnings.append("No travel times were calculated; the existing travel cache was left unchanged.")
        return {"rows": 0, "places_with_times": 0, "warnings": warnings}
    path = state.root / "data" / "travel-cache.csv"
    fields = ["place", "region", "lat", "lon", "anchor_id", "mode", "minutes", "km", "method", "confidence", "computed_at"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return {"rows": len(rows), "places_with_times": len({r["place"] for r in rows}), "warnings": warnings}


# --------------------------------------------------------------------------- cli
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="laa", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("state")
    p = sub.add_parser("process"); p.add_argument("state"); p.add_argument("extracted")
    p.add_argument("--pack-dir"); p.add_argument("--now"); p.add_argument("--emails-read", type=int, default=0)
    p.add_argument("--not-parsed", type=int, default=0); p.add_argument("--not-parsed-links", default="")
    p.add_argument("--senders", default=""); p.add_argument("--health", default=""); p.add_argument("--status", default="ok")
    p.add_argument("--write", action="store_true")
    p.add_argument("--force-write", action="store_true", help="Write even if a run was recorded in the last 10 minutes")
    p.add_argument("--write-if-changed", action="store_true",
                   help="With --write: skip writing quiet runs (used with Google Drive storage to limit file versions)")
    d = sub.add_parser("digest"); d.add_argument("state"); d.add_argument("--end"); d.add_argument("--pack-dir")
    d.add_argument("--insight", default="", help="Short plain-text paragraph written by Claude from the digest figures")
    dr = sub.add_parser("doctor"); dr.add_argument("state"); dr.add_argument("--now")
    t = sub.add_parser("travel-cache"); t.add_argument("state"); t.add_argument("--dry-run", action="store_true")
    cp = sub.add_parser("compare"); cp.add_argument("state"); cp.add_argument("refs", nargs="+", help="Listing links or address words")
    fb = sub.add_parser("feedback"); fb.add_argument("state"); fb.add_argument("ref")
    fb.add_argument("--verdict", required=True, choices=["yes", "maybe", "no", "shortlisted", "contacted", "viewing",
                                                          "applied", "offer", "not_for_me", "rejected", "let_agreed"])
    fb.add_argument("--reason", default=""); fb.add_argument("--now")
    tn = sub.add_parser("tune"); tn.add_argument("state")
    dd = sub.add_parser("dashboard-data"); dd.add_argument("state"); dd.add_argument("--out", required=True, help="Folder for listings.json, runs.json, places.json")
    lk = sub.add_parser("links"); lk.add_argument("--origin", required=True); lk.add_argument("--destination", required=True)
    lk.add_argument("--mode", default="driving")
    args = ap.parse_args(argv)

    if args.cmd == "links":
        print(maps_directions_link(args.origin, args.destination, args.mode))
        return 0
    state = State(args.state)
    if args.cmd == "validate":
        problems = validate(state)
        print(json.dumps({"valid": not problems, "problems": problems}, indent=2))
        return 0 if not problems else 1
    if args.cmd == "process":
        now = parse_dt(args.now) if args.now else dt.datetime.now(dt.timezone.utc).astimezone()
        extracted = json.loads(Path(args.extracted).read_text(encoding="utf-8"))
        out = process(state, extracted, Path(args.pack_dir) if args.pack_dir else None, now)
        not_parsed = [x for x in args.not_parsed_links.split(";") if x]
        # only real addresses of emails actually read count as "seen"; patterns or configured lists do not
        senders = [x for x in args.senders.split(";") if x and not any(ch in x for ch in "*?[")] if args.emails_read else []
        health = [x for x in args.health.split(";") if x]
        health_text = "; ".join(health)
        if health_due(state, now):
            health += health_checks(state, now, senders, args.not_parsed)
            health_text = "checked: " + ("; ".join(health) if health else "no warnings")
        email = render_alert(out, state, not_parsed, health)
        write_note = ""
        changed = bool(out["results"] or not_parsed or health_text.startswith("checked"))
        if args.write and args.write_if_changed and not changed:
            write_note = "nothing to write (no listings, no unread emails, health already checked today)"
        elif args.write:
            runs = read_csv(state.run_log_path)
            last = parse_dt(runs[-1].get("run_at")) if runs else None
            if last and abs((now - last).total_seconds()) < 600 and not args.force_write:
                write_note = (f"write skipped: a run was already recorded at {runs[-1].get('run_at')} "
                              "(less than 10 minutes ago). Use --force-write only if that record was not from this run.")
            else:
                write_results(state, out, args.emails_read, args.not_parsed, ";".join(senders), health_text, args.status)
                write_note = "written"
        print(json.dumps({"email": email, "results": out["results"], "excluded": out["excluded"], "write": write_note},
                         indent=2, default=str))
        return 0
    if args.cmd == "digest":
        end = dt.date.fromisoformat(args.end) if args.end else dt.date.today() - dt.timedelta(days=1)
        print(json.dumps(digest(state, end, Path(args.pack_dir) if args.pack_dir else None, args.insight), indent=2, default=str))
        return 0
    if args.cmd == "compare":
        print(json.dumps(compare(state, args.refs), indent=2))
        return 0
    if args.cmd == "feedback":
        now = parse_dt(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
        print(json.dumps(record_feedback(state, args.ref, args.verdict, args.reason, now), indent=2))
        return 0
    if args.cmd == "dashboard-data":
        data = dashboard_data(state, dt.datetime.now(dt.timezone.utc))
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ("listings", "runs", "places"):
            (out_dir / f"{name}.json").write_text(json.dumps(data[name], indent=1, default=str), encoding="utf-8")
        print(json.dumps({k: len(v) for k, v in data.items() if isinstance(v, list)} | {"generated_at": data["generated_at"]}))
        return 0
    if args.cmd == "tune":
        print(json.dumps(tune_suggestions(state), indent=2))
        return 0
    if args.cmd == "doctor":
        now = parse_dt(args.now) if args.now else dt.datetime.now(dt.timezone.utc).astimezone()
        print("\n".join(doctor(state, now)))
        return 0
    if args.cmd == "travel-cache":
        print(json.dumps(build_travel_cache(state, args.dry_run), indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
