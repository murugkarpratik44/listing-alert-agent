"""Unit and end-to-end tests for the listing-alert-agent engine (laa.py).

Run from the repository root:
    python -m unittest discover -s tests -v
All data is synthetic.
"""
import contextlib
import csv
import io
import datetime as dt
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "listing-alert-agent"
sys.dont_write_bytecode = True  # keep the plugin folder free of .pyc files
sys.path.insert(0, str(PLUGIN / "skills" / "run-alerts" / "scripts"))

import laa  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
PACK = PLUGIN / "packs" / "ie-rentals"
NOW = dt.datetime.fromisoformat("2026-10-17T09:00:00+01:00")


def fresh_state() -> laa.State:
    tmp = Path(tempfile.mkdtemp(prefix="laa-test-"))
    shutil.copytree(FIXTURES / "state", tmp / "state")
    return laa.State(tmp / "state")


def run1():
    return json.loads((FIXTURES / "extracted-run1.json").read_text(encoding="utf-8"))


class RentAndUrls(unittest.TestCase):
    def test_weekly_to_monthly(self):
        self.assertEqual(laa.monthly_rent(400, "week"), 1733)  # 400 x 52 / 12 = 1733.33
        self.assertEqual(laa.monthly_rent(530, "weekly"), 2297)
        self.assertEqual(laa.monthly_rent(1500, "month"), 1500)
        self.assertEqual(laa.monthly_rent(24000, "year"), 2000)
        self.assertIsNone(laa.monthly_rent(None, "month"))

    def test_canonical_url_unwraps_tracking_and_drops_utm(self):
        wrapped = run1()[0]["url"]
        self.assertEqual(laa.canonical_url(wrapped),
                         "https://www.myhome.ie/rentals/brochure/1-example-court-maynooth/9000001")
        self.assertEqual(laa.canonical_url("https://WWW.daft.ie/x?utm_source=a&id=3#frag"),
                         "https://www.daft.ie/x?id=3")

    def test_dedupe_key_ignores_apartment_and_county_words(self):
        a = laa.dedupe_key("Apartment 1, Example Court, Maynooth, Co. Kildare", 2)
        b = laa.dedupe_key("1 Example Court, Maynooth, Co. Kildare", 2)
        self.assertEqual(a, b)
        self.assertNotEqual(a, laa.dedupe_key("1 Example Court, Maynooth, Co. Kildare", 1))

    def test_maps_links_are_encoded(self):
        link = laa.maps_directions_link("1 Main St, Naas", "Office & Co, Galway", "transit")
        self.assertTrue(link.startswith("https://www.google.com/maps/dir/?api=1&origin=1+Main+St%2C+Naas"))
        self.assertIn("destination=Office+%26+Co%2C+Galway", link)
        self.assertIn("travelmode=transit", link)
        self.assertIn("travelmode=driving", laa.maps_directions_link("a", "b", "teleport"))
        self.assertLess(len(link), 2048)


class Places(unittest.TestCase):
    def setUp(self):
        self.index = laa.place_index(fresh_state())

    def test_postal_district_whole_word(self):
        self.assertEqual(laa.match_place("Flat 2, Blanchardstown, Dublin 15", self.index)["place"], "Dublin 15")
        self.assertIsNone(laa.match_place("Flat 2, Dublin 1", self.index))

    def test_street_name_is_not_a_town(self):
        self.assertIsNone(laa.match_place("4 Naas Road, Clondalkin", self.index))
        self.assertEqual(laa.match_place("4 Dublin Road, Naas, Co. Kildare", self.index)["place"], "Naas")


class Benchmark(unittest.TestCase):
    def setUp(self):
        self.rows, self.meta = laa.load_benchmark(PACK, fresh_state())

    def test_pack_metadata(self):
        self.assertIn("RTB", self.meta["source"])
        self.assertGreater(len(self.rows), 300)

    def test_specific_location_and_type(self):
        b = laa.benchmark_lookup(self.rows, "1 Example Court, Maynooth, Co. Kildare", "Kildare", 2, "Apartment")
        self.assertEqual((b["location"], b["property_type"]), ("Maynooth, Kildare", "Apartment"))

    def test_thin_data_falls_back_to_county(self):
        # Leixlip 1-bed has only one quarter of data, so the county row is used
        b = laa.benchmark_lookup(self.rows, "9 Fable Square, Leixlip, Co. Kildare", "Kildare", 1, "Apartment")
        self.assertEqual(b["location"], "Kildare")

    def test_county_named_like_town(self):
        b = laa.benchmark_lookup(self.rows, "1 Main St, Kildare, Co. Kildare", "Kildare", 2, "House")
        self.assertEqual(b["location"], "Kildare Town")
        b = laa.benchmark_lookup(self.rows, "5 Dublin Road, Naas, Co. Kildare", "", 2, "House")
        self.assertEqual(b["location"], "Naas, Kildare")


class BudgetTiers(unittest.TestCase):
    def setUp(self):
        self.profile = fresh_state().profile

    def test_occupancy_rules(self):
        self.assertEqual(laa.occupancy(self.profile, 2, 2), 2)
        self.assertEqual(laa.occupancy(self.profile, 2, 1), 1)
        self.assertEqual(laa.occupancy(self.profile, 2, None), 1)
        self.assertEqual(laa.occupancy(self.profile, 1, 1), 1)

    def test_tiers(self):
        self.assertEqual(laa.tier_for(2200, 2, self.profile), ("act_now", 2200))
        self.assertEqual(laa.tier_for(1210, 1, self.profile)[0], "stretch")
        self.assertEqual(laa.tier_for(1211, 1, self.profile)[0], "over_budget")


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.state = fresh_state()
        self.out = laa.process(self.state, run1(), PACK, NOW)
        self.by_url = {r["listing_url"]: r for r in self.out["results"]}

    def test_buckets_and_exclusions(self):
        buckets = sorted((r["bucket"], r.get("address")) for r in self.out["results"])
        self.assertEqual([b for b, _ in buckets],
                         ["act_now", "act_now", "check_location", "over_budget", "stretch"])
        reasons = " | ".join(e["reason"] for e in self.out["excluded"])
        self.assertIn("outside search areas (Newbridge)", reasons)
        self.assertIn("type 'Studio' excluded", reasons)
        self.assertIn("deal-breaker: ground floor", reasons)

    def test_shared_two_bed_uses_two_budgets_and_merges_sources(self):
        r = self.by_url["https://www.myhome.ie/rentals/brochure/1-example-court-maynooth/9000001"]
        self.assertEqual((r["tier"], r["people"], r["per_person"]), ("act_now", 2, 1050))
        self.assertEqual(r["also_on"][0]["source"], "Daft.ie")
        self.assertEqual(r["area_id"], "near-work")

    def test_weekly_rent_and_region_area(self):
        r = self.by_url["https://www.myhome.ie/rentals/brochure/22-demo-street-dublin-8/9000005"]
        self.assertEqual((r["rent_monthly"], r["tier"], r["area_id"]), (2297, "over_budget", "dublin"))

    def test_scam_flag(self):
        r = self.by_url["https://www.daft.ie/for-rent/apartment-9-fable-square-leixlip/9000007"]
        self.assertTrue(any("possible scam" in f for f in r["flags"]))
        self.assertLessEqual(r["benchmark_pct"], -35)
        self.assertLessEqual(r["fit_score"], laa.SCAM_SCORE_CAP)
        self.assertNotIn("good value", r["flags"])
        act_now = [x for x in self.out["results"] if x["tier"] == "act_now"]
        self.assertIs(act_now[-1], r)  # ranked after listings without risk flags

    def test_rent_not_stated_goes_to_check(self):
        item = dict(run1()[2], rent_amount=None, url="https://www.daft.ie/x/1")
        out = laa.process(fresh_state(), [item], PACK, NOW)
        self.assertEqual(out["results"][0]["bucket"], "check_location")
        self.assertIn("rent not stated", out["results"][0]["flags"])

    def test_ordering_and_score_range(self):
        tiers = [r["tier"] for r in self.out["results"]]
        self.assertEqual(tiers, sorted(tiers, key=lambda t: laa.TIER_ORDER.index(t)))
        for r in self.out["results"]:
            self.assertTrue(0 <= r["fit_score"] <= 100)
            self.assertTrue(r["reasons"])

    def test_rendered_email(self):
        email = laa.render_alert(self.out, self.state)
        self.assertTrue(email["send"])
        self.assertTrue(email["push"])
        self.assertTrue(email["subject"].startswith("Listing alert – 5 new (2 act now)"))
        body = email["body"]
        for heading in ("ACT NOW", "STRETCH", "OVER BUDGET", "CHECK LOCATION"):
            self.assertIn(heading, body)
        self.assertIn("€2,100 a month (€1,050 each)", body)
        self.assertIn("Also on Daft.ie", body)
        self.assertIn("https://www.google.com/maps/dir/?api=1", body)
        self.assertNotIn("**", body)  # plain text, no Markdown
        self.assertNotIn("utm_", body)

    def test_quiet_hours_suppress_push(self):
        late = dt.datetime.fromisoformat("2026-10-17T23:30:00+01:00")
        out = laa.process(fresh_state(), run1(), PACK, late)
        self.assertFalse(laa.render_alert(out, self.state)["push"])


class History(unittest.TestCase):
    def test_no_repeats_then_price_change_then_relist(self):
        state = fresh_state()
        out = laa.process(state, run1(), PACK, NOW)
        laa.write_results(state, out, 9, 0, "alerts@daft.ie;notifications@myhome.ie", "", "ok")

        again = laa.process(state, run1(), PACK, NOW + dt.timedelta(hours=1))
        self.assertEqual(again["results"], [])

        changed = run1()
        changed[2]["rent_amount"] = 1080  # Celbridge drops from 1,180 to 1,080
        out2 = laa.process(state, changed, PACK, NOW + dt.timedelta(hours=2))
        self.assertEqual(len(out2["results"]), 1)
        r = out2["results"][0]
        self.assertEqual((r["event"], r["tier"]), ("price_change", "act_now"))
        self.assertIn("€1,180 → €1,080 (-8%)", r["flags"][0])
        laa.write_results(state, out2, 1, 0, "alerts@daft.ie", "", "ok")

        later = laa.process(state, run1()[:1], PACK, NOW + dt.timedelta(days=15))
        self.assertEqual(later["results"][0]["event"], "relisted")

    def test_written_csvs(self):
        state = fresh_state()
        out = laa.process(state, run1(), PACK, NOW)
        laa.write_results(state, out, 9, 1, "alerts@daft.ie", "checked: no warnings", "ok")
        with open(state.listings_path, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 5)
        self.assertEqual(list(rows[0].keys()), laa.LISTING_FIELDS)
        with open(state.run_log_path, encoding="utf-8") as fh:
            log = list(csv.DictReader(fh))
        self.assertEqual(log[0]["new_listings_reported"], "5")
        self.assertEqual(log[0]["listings_extracted"], "8")


class Health(unittest.TestCase):
    def test_source_silence_and_daily_once(self):
        state = fresh_state()
        start = NOW - dt.timedelta(days=4)
        laa.append_csv(state.run_log_path, laa.RUN_LOG_FIELDS, [
            {"run_at": start.isoformat(), "alert_senders": "notifications@myhome.ie", "status": "ok"},
            {"run_at": (NOW - dt.timedelta(hours=1)).isoformat(), "alert_senders": "notifications@myhome.ie",
             "health": "checked: no warnings", "status": "ok"},
        ])
        warnings = laa.health_checks(state, NOW, [], 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("No alert emails from Daft.ie since tracking began", warnings[0])
        self.assertFalse(laa.health_due(state, NOW))  # already checked today (Dublin time)
        self.assertTrue(laa.health_due(state, NOW + dt.timedelta(days=1)))

    def test_quiet_hours_window(self):
        p = {"alerts": {"quiet_hours": {"start": "23:00", "end": "07:00"}}}
        self.assertTrue(laa.in_quiet_hours(p, dt.datetime(2026, 10, 17, 2, 0)))
        self.assertFalse(laa.in_quiet_hours(p, dt.datetime(2026, 10, 17, 7, 0)))
        self.assertFalse(laa.in_quiet_hours({}, dt.datetime(2026, 10, 17, 2, 0)))


class ValidateAndDigest(unittest.TestCase):
    def test_fixture_config_is_valid(self):
        self.assertEqual(laa.validate(fresh_state()), [])

    def test_validation_catches_bad_config(self):
        state = fresh_state()
        state.profile["owner"]["email"] = "not-an-email"
        state.profile["areas"][0]["anchor"] = "gym"
        problems = " | ".join(laa.validate(state))
        self.assertIn("owner.email", problems)
        self.assertIn("unknown anchor 'gym'", problems)

    def test_digest(self):
        state = fresh_state()
        out = laa.process(state, run1(), PACK, NOW)
        laa.write_results(state, out, 9, 0, "alerts@daft.ie", "checked: no warnings", "ok")
        d = laa.digest(state, NOW.date(), PACK)
        self.assertIn("5 new listings this week: 2 act now, 1 stretch, 1 over budget, 1 to check location.", d["body"])
        self.assertIn("Less than two weeks of data", d["body"])
        self.assertIn("BEST FIVE THIS WEEK", d["body"])
        self.assertNotIn("Warnings this week", d["body"])

    def test_doctor_reports(self):
        report = "\n".join(laa.doctor(fresh_state(), NOW))
        self.assertIn("Config: valid", report)
        self.assertIn("Travel cache: 8 places × 2 important places", report)
        self.assertIn("Runs: none yet", report)


class Cli(unittest.TestCase):
    def test_process_cli_writes_once(self):
        state = fresh_state()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = laa.main(["process", str(state.root), str(FIXTURES / "extracted-run1.json"),
                           "--pack-dir", str(PACK), "--now", NOW.isoformat(), "--emails-read", "9",
                           "--senders", "alerts@daft.ie;notifications@myhome.ie", "--write"])
        self.assertEqual(rc, 0)
        self.assertIn("ACT NOW", json.loads(buf.getvalue())["email"]["body"])
        log = laa.read_csv(state.run_log_path)
        self.assertEqual(len(log), 1)
        self.assertTrue(log[0]["health"].startswith("checked:"))


if __name__ == "__main__":
    unittest.main()


class AreaOverrides(unittest.TestCase):
    """v0.1.1: per-area anchor limits and commute notes."""

    def dublin_result(self, **area_extra):
        state = fresh_state()
        state.profile["areas"][1].update(area_extra)
        state.profile["budget"]["amount"] = 2400  # so the €2,297 Dublin listing is within budget
        item = run1()[4]  # Dublin 8: 38 min to Work (limit 30), 72 min to Family (limit 60)
        out = laa.process(state, [item], PACK, NOW)
        return out["results"][0], laa.render_alert(out, state)["body"]

    def test_longer_limit_raises_travel_score(self):
        base, _ = self.dublin_result()
        longer, _ = self.dublin_result(anchor_limits={"work": 90, "family": 120})
        self.assertGreater(longer["fit_score"], base["fit_score"])

    def test_null_limit_skips_anchor(self):
        lines, ratios, _ = laa.travel_lines(
            {"address": "22 Demo Street, Dublin 8"},
            laa.match_place("22 Demo Street, Dublin 8", laa.place_index(fresh_state())),
            fresh_state(), {"anchor_limits": {"work": None, "family": None}})
        self.assertEqual(ratios, [])
        self.assertEqual(len(lines), 2)  # still shown

    def test_commute_note_rendered(self):
        r, body = self.dublin_result(commute_note="Train to Maynooth about 35 min")
        self.assertEqual(r["commute_note"], "Train to Maynooth about 35 min")
        self.assertIn("   Commute: Train to Maynooth about 35 min", body)


class DirectionsDestination(unittest.TestCase):
    def test_anchor_coordinates_used_when_known(self):
        state = fresh_state()
        state.places["anchors"][0].update(lat=53.3811, lon=-6.5918)
        place = laa.match_place("1 Main St, Maynooth", laa.place_index(state))
        lines, _, _ = laa.travel_lines({"address": "1 Main St, Maynooth"}, place, state)
        self.assertIn("destination=53.38110%2C-6.59180", lines[0])
        self.assertIn("destination=Mullingar", lines[1])  # no coordinates: address used


class SubjectTime(unittest.TestCase):
    def test_subject_uses_owner_timezone(self):
        state = fresh_state()
        utc = dt.datetime.fromisoformat("2026-10-17T08:00:00+00:00")  # 09:00 in Dublin (IST)
        out = laa.process(state, run1()[:1], PACK, utc)
        self.assertTrue(laa.render_alert(out, state)["subject"].endswith("17 Oct 09:00"))


class HtmlEmail(unittest.TestCase):
    def setUp(self):
        self.state = fresh_state()
        items = run1()
        items[0]["address"] = "Apartment 1, <b>Example</b> Court, Maynooth, Co. Kildare"  # must be escaped
        self.out = laa.process(self.state, items, PACK, NOW)
        self.html = laa.render_alert(self.out, self.state, ["https://mail.google.com/x"], ["Daft.ie quiet for 50 hours"])["html"]

    def test_sections_and_cards(self):
        for text in ("Act now", "Stretch", "Over budget", "Check location", "Could not read", "Check your setup",
                     "FIT /100", "View on MyHome.ie", "Directions", "€1,050 each for 2 people", "over budget</span>"):
            self.assertIn(text, self.html)

    def test_escaping_and_safety(self):
        self.assertIn("&lt;b&gt;Example&lt;/b&gt;", self.html)
        self.assertNotIn("<b>Example</b>", self.html)
        self.assertNotIn("<script", self.html.lower())
        self.assertNotIn("<img", self.html.lower())

    def test_reason_tones(self):
        r = self.out["results"][0]
        self.assertEqual(len(r["reason_tones"]), len(r["reasons"]))
        scam = [x for x in self.out["results"] if x["risky"]][0]
        self.assertEqual((scam["reasons"][0], scam["reason_tones"][0]), ("score capped until verified", "bad"))


class DigestHtml(unittest.TestCase):
    def test_digest_html_insight_and_reminders(self):
        state = fresh_state()
        state.profile["alerts"]["monthly_reminders"] = ["Retry the <Rent.ie> alert"]
        out = laa.process(state, run1(), PACK, NOW)
        laa.write_results(state, out, 9, 0, "alerts@daft.ie", "checked: no warnings", "ok")
        d = laa.digest(state, dt.date(2026, 10, 3), PACK, insight="Kildare had the most affordable 1-beds.")
        self.assertIn("WHAT THIS MEANS\nKildare had the most affordable 1-beds.", d["body"])
        self.assertIn("Monthly reminder: Retry the <Rent.ie> alert", d["body"])  # day 3: first week of month
        self.assertIn("&lt;Rent.ie&gt;", d["html"])
        for text in ("Your listing week at a glance", "By area and bedrooms", "Best five this week", "Pipeline health"):
            self.assertIn(text, d["html"])


class SendersSeen(unittest.TestCase):
    def test_patterns_and_zero_email_runs_do_not_count_as_seen(self):
        state = fresh_state()
        with contextlib.redirect_stdout(io.StringIO()):
            laa.main(["process", str(state.root), str(FIXTURES / "extracted-run1.json"), "--pack-dir", str(PACK),
                      "--now", NOW.isoformat(), "--emails-read", "0", "--senders", "*@daft.ie;notifications@myhome.ie", "--write"])
        self.assertEqual(laa.read_csv(state.run_log_path)[-1]["alert_senders"], "")

    def test_run_time_stored_in_owner_timezone(self):
        out = laa.process(fresh_state(), [], PACK, dt.datetime.fromisoformat("2026-10-17T10:58:06+00:00"))
        self.assertEqual(out["now"], "2026-10-17T11:58:06+01:00")


class DoubleWriteGuard(unittest.TestCase):
    def test_second_write_within_ten_minutes_is_skipped(self):
        state = fresh_state()
        args = ["process", str(state.root), str(FIXTURES / "extracted-run1.json"), "--pack-dir", str(PACK), "--write"]
        with contextlib.redirect_stdout(io.StringIO()) as first:
            laa.main(args + ["--now", NOW.isoformat()])
        with contextlib.redirect_stdout(io.StringIO()) as second:
            laa.main(args + ["--now", (NOW + dt.timedelta(minutes=1)).isoformat()])
        self.assertEqual(json.loads(first.getvalue())["write"], "written")
        self.assertTrue(json.loads(second.getvalue())["write"].startswith("write skipped"))
        self.assertEqual(len(laa.read_csv(state.run_log_path)), 1)


class GeocodeChecks(unittest.TestCase):
    def test_coarse_and_shared_points_rejected(self):
        res = {
            "Athlone, Westmeath": {"lat": 53.43, "lon": -7.94, "layer": "locality", "label": "Athlone"},
            "Coosan, Westmeath": {"lat": 53.53, "lon": -7.41, "layer": "county", "label": "Westmeath"},
            "Dublin 1, Dublin": {"lat": 53.34, "lon": -6.29, "layer": "locality", "label": "Dublin"},
            "Dublin 2, Dublin": {"lat": 53.34, "lon": -6.29, "layer": "locality", "label": "Dublin"},
            "Nowhere, X": None,
        }
        problems = laa.check_geocodes(res)
        self.assertNotIn("Athlone, Westmeath", problems)
        self.assertIn("county", problems["Coosan, Westmeath"])
        self.assertIn("same point", problems["Dublin 1, Dublin"])
        self.assertIn("same point", problems["Dublin 2, Dublin"])
        self.assertEqual(problems["Nowhere, X"], "not found")

    def test_travel_cache_uses_cache_and_stops_on_quota(self):
        import os
        import urllib.error
        from unittest import mock
        state = fresh_state()
        state.places = {"anchors": [{"id": "work", "label": "Work", "address": "x", "lat": 53.38, "lon": -6.59, "modes": ["driving"]}],
                        "search_places": [{"name": "Maynooth", "region": "Kildare"}, {"name": "Naas", "region": "Kildare"}]}
        laa.append_csv(state.root / "data" / "geocode-cache.csv", laa.GEOCODE_FIELDS,
                       [{"query": "Maynooth, Kildare", "lat": 53.38, "lon": -6.59, "layer": "locality", "label": "Maynooth", "status": "ok"}])

        def fake(path, key, payload=None, params=None):
            if path.startswith("/geocode"):
                raise urllib.error.HTTPError(path, 403, "Quota exceeded", {}, None)
            n = len(payload["sources"])
            return {"durations": [[600.0]] * n, "distances": [[5.0]] * n}

        with mock.patch.object(laa, "ors_request", side_effect=fake), mock.patch.dict(os.environ, {"ORS_API_KEY": "test"}):
            out = laa.build_travel_cache(state)
        self.assertEqual(out["places_with_times"], 1)  # Maynooth from the cache; Naas skipped
        self.assertTrue(any("quota" in w.lower() for w in out["warnings"]))


class TripsWeighting(unittest.TestCase):
    def test_area_trip_override_changes_weighting(self):
        state = fresh_state()
        place = laa.match_place("Dublin 8", laa.place_index(state))
        _, daily, _ = laa.travel_lines({"address": "Dublin 8"}, place, state, {"id": "x"})
        _, weekly, _ = laa.travel_lines({"address": "Dublin 8"}, place, state, {"id": "x", "anchor_trips": {"work": 1}})
        self.assertEqual(len(daily), 3 * 6 + 2 * 2)   # work high x 3 trips, family medium x 1 trip
        self.assertEqual(len(weekly), 3 * 2 + 2 * 2)


class CostEstimate(unittest.TestCase):
    def test_ber_midpoints_both_scales(self):
        bands = laa.cost_inputs({}, laa.load_cost_defaults(PACK))["bands"]
        self.assertEqual(laa.ber_midpoint("B2", bands), 112.5)
        self.assertEqual(laa.ber_midpoint("BER: C", bands), 187.5)      # simplified scale
        self.assertEqual(laa.ber_midpoint("G", bands), 500.0)           # previous scale wins on G
        self.assertIsNone(laa.ber_midpoint("exempt", bands))

    def test_estimate_parts_and_sources(self):
        state = fresh_state()
        item = dict(run1()[0], energy_rating="B2", floor_area_m2=68)
        r = laa.process(state, [item], PACK, NOW)["results"][0]
        c = r["cost"]
        self.assertEqual(c["parts"]["rent"], 1050)                      # shared by 2
        self.assertEqual(c["parts"]["energy"], round(112.5 * 68 * 0.13 / 12 / 2))
        expected_commute = 1.5 * 2 * 3 * 52 / 12 * 0.3179 + 62 * 2 * 1 * 52 / 12 * 0.3179
        self.assertEqual(c["parts"]["commute"], round(expected_commute))
        self.assertTrue(any("SEAI" in n for n in c["notes"]))
        self.assertTrue(any("Revenue" in n for n in c["notes"]))
        self.assertIn("Your cost", laa.render_alert({"results": [r], "excluded": [], "benchmark_meta": {}, "now": NOW.isoformat()}, state)["html"])

    def test_user_prices_override_defaults_and_missing_reported(self):
        state = fresh_state()
        state.profile["costs"] = {"car_eur_per_km": 0.2}
        r = laa.process(state, [run1()[0]], PACK, NOW)["results"][0]   # no BER or area in this listing
        self.assertIn("energy (needs BER and floor area in the alert)", r["cost"]["missing"])
        self.assertTrue(any("your cost" in n for n in r["cost"]["notes"]))


class DecisionAids(unittest.TestCase):
    def setUp(self):
        self.state = fresh_state()
        out = laa.process(self.state, run1(), PACK, NOW)
        laa.write_results(self.state, out, 9, 0, "", "", "ok")

    def test_header_upgrade_keeps_rows(self):
        path = self.state.listings_path
        old_fields = laa.LISTING_FIELDS[:-3]
        rows = laa.read_csv(path)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=old_fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        laa.append_csv(path, laa.LISTING_FIELDS, [{"address": "new row", "cost_monthly": 1234}])
        after = laa.read_csv(path)
        self.assertEqual(len(after), len(rows) + 1)
        self.assertEqual(after[0]["address"], rows[0]["address"])
        self.assertEqual(after[-1]["cost_monthly"], "1234")

    def test_compare_picks_best_per_criterion(self):
        c = laa.compare(self.state, ["Example Court", "Sample Row", "Fable Square", "Nowhere Street"])
        self.assertEqual(len(c["listings"]), 3)
        self.assertEqual(c["not_found"], ["Nowhere Street"])
        self.assertIn("Fable Square", c["best"]["lowest_share"])
        self.assertIn("Example Court", c["best"]["shortest_trip"])   # 4 min to Work
        self.assertIn("Example Court", c["best"]["highest_fit"])

    def test_feedback_and_tune(self):
        for ref, reason in (("Sample Row", "too far"), ("Demo Street", "too far from work"),
                            ("Fable Square", "ground floor"), ("Nowhere Place", "ground floor")):
            laa.record_feedback(self.state, ref, "no", reason, NOW)
        laa.record_feedback(self.state, "Example Court", "yes", "", NOW)
        t = laa.tune_suggestions(self.state)
        self.assertEqual(t["verdicts"]["no"], 4)
        changes = " | ".join(x["change"] for x in t["suggestions"])
        self.assertIn("areas[near-work].max_minutes", changes)
        self.assertIn("criteria.deal_breakers: add 'ground floor'", changes)


class WriteIfChanged(unittest.TestCase):
    def test_quiet_run_not_written_but_daily_health_is(self):
        state = fresh_state()
        empty = Path(tempfile.mkdtemp()) / "empty.json"
        empty.write_text("[]", encoding="utf-8")
        base = ["process", str(state.root), str(empty), "--pack-dir", str(PACK), "--write", "--write-if-changed"]
        with contextlib.redirect_stdout(io.StringIO()) as first:
            laa.main(base + ["--now", NOW.isoformat()])               # first run of the day: health checked -> written
        with contextlib.redirect_stdout(io.StringIO()) as second:
            laa.main(base + ["--now", (NOW + dt.timedelta(hours=1)).isoformat()])   # quiet -> skipped
        self.assertEqual(json.loads(first.getvalue())["write"], "written")
        self.assertTrue(json.loads(second.getvalue())["write"].startswith("nothing to write"))
        self.assertEqual(len(laa.read_csv(state.run_log_path)), 1)


class DashboardData(unittest.TestCase):
    def test_latest_event_status_and_coordinates(self):
        state = fresh_state()
        out = laa.process(state, run1(), PACK, NOW)
        laa.write_results(state, out, 9, 0, "", "checked: no warnings", "ok")
        laa.record_feedback(state, "Example Court", "contacted", "emailed agent", NOW)
        laa.record_feedback(state, "Sample Row", "no", "too far", NOW)
        d = laa.dashboard_data(state, NOW)
        by = {x["address"]: x for x in d["listings"]}
        self.assertEqual(by["Apartment 1, Example Court, Maynooth, Co. Kildare"]["status"], "contacted")
        self.assertEqual(by["5 Sample Row, Celbridge, Co. Kildare"]["status"], "not_for_me")
        self.assertAlmostEqual(by["5 Sample Row, Celbridge, Co. Kildare"]["lat"], 53.34)
        self.assertIsNone(by["4 Nowhere Place, Ballyexample"]["lat"])
        self.assertEqual(len(d["runs"]), 1)
        self.assertTrue(any(p["kind"] == "search" and p["name"] == "Maynooth" for p in d["places"]))
        self.assertNotIn("phone", json.dumps(d).lower())


class EnergyBill(unittest.TestCase):
    def test_own_bill_range_used_instead_of_ber(self):
        state = fresh_state()
        state.profile["costs"] = {"energy_monthly_eur": [50, 75]}
        item = dict(run1()[0], energy_rating="B2", floor_area_m2=68)
        c = laa.process(state, [item], PACK, NOW)["results"][0]["cost"]
        self.assertEqual(c["parts"]["energy"], 62)  # midpoint 62.5, rounded half to even
        self.assertTrue(any("your own bill (€50–75 a month); this home's BER is B2" in n for n in c["notes"]))
