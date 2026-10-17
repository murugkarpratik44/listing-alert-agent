"""Schema, pack-fixture and state-template tests. All data is synthetic."""
import json
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "listing-alert-agent"
sys.dont_write_bytecode = True
sys.path.insert(0, str(PLUGIN / "skills" / "run-alerts" / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import laa  # noqa: E402
import check_packs  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None

SCHEMAS = PLUGIN / "schemas"
STATE = ROOT / "tests" / "fixtures" / "state"
PACK = PLUGIN / "packs" / "ie-rentals"


def schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


@unittest.skipIf(jsonschema is None, "jsonschema not installed")
class Schemas(unittest.TestCase):
    def test_schemas_are_valid(self):
        for p in SCHEMAS.glob("*.json"):
            jsonschema.Draft202012Validator.check_schema(json.loads(p.read_text(encoding="utf-8")))

    def test_fixture_state_matches_schemas(self):
        for name in ("profile", "sources", "places"):
            data = yaml.safe_load((STATE / "config" / f"{name}.yaml").read_text(encoding="utf-8"))
            jsonschema.validate(data, schema(name))

    def test_extracted_fixture_matches_listing_schema(self):
        data = json.loads((ROOT / "tests" / "fixtures" / "extracted-run1.json").read_text(encoding="utf-8"))
        jsonschema.validate(data, schema("listing"))

    def test_bad_profile_rejected(self):
        data = yaml.safe_load((STATE / "config" / "profile.yaml").read_text(encoding="utf-8"))
        data["budget"]["model"] = "per_room"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(data, schema("profile"))


class Packs(unittest.TestCase):
    def test_all_packs_pass_checks(self):
        listing = schema("listing")
        for pack_dir in (PLUGIN / "packs").iterdir():
            if (pack_dir / "pack.yaml").exists():
                self.assertEqual(check_packs.check_pack(pack_dir, listing), [], pack_dir.name)

    def test_pack_fixture_inbox_end_to_end(self):
        """Expected extraction from the synthetic emails -> engine -> alert text."""
        import shutil
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="laa-pack-")) / "state"
        shutil.copytree(STATE, tmp)
        expected = json.loads((PACK / "fixtures" / "expected-extraction.json").read_text(encoding="utf-8"))
        listings = [x for items in expected.values() for x in items]
        now = laa.parse_dt("2026-10-17T09:00:00+01:00")
        out = laa.process(laa.State(tmp), listings, PACK, now)
        email = laa.render_alert(out, laa.State(tmp))
        self.assertEqual(len(out["results"]), 4)
        self.assertIn("possible scam", email["body"])
        self.assertIn("€2,297", email["body"])  # 530 a week -> monthly
        self.assertIn("Market averages: RTB", email["body"])


class StateTemplate(unittest.TestCase):
    TEMPLATE = ROOT.parent / "listing-alert-agent-state-template"

    @unittest.skipUnless((ROOT.parent / "listing-alert-agent-state-template").exists(), "template repo not checked out")
    def test_template_validates_and_headers_match(self):
        state = laa.State(self.TEMPLATE)
        self.assertEqual(laa.validate(state), [])
        header = (self.TEMPLATE / "data" / "listings.csv").read_text(encoding="utf-8").strip().split(",")
        self.assertEqual(header, laa.LISTING_FIELDS)
        header = (self.TEMPLATE / "data" / "run-log.csv").read_text(encoding="utf-8").strip().split(",")
        self.assertEqual(header, laa.RUN_LOG_FIELDS)


if __name__ == "__main__":
    unittest.main()
