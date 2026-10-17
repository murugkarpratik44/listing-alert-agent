#!/usr/bin/env python3
"""Checks every pack: paths in pack.yaml exist, fixtures are marked synthetic,
expected extraction JSON matches schemas/listing.schema.json, benchmark columns are right.

Usage: python tools/check_packs.py [plugin_dir]
"""
import csv
import json
import sys
from pathlib import Path

import yaml

try:
    import jsonschema
except ImportError:  # optional locally, installed in CI
    jsonschema = None

BENCH_COLS = {"location", "property_type", "bedrooms", "value", "n_periods"}


def check_pack(pack_dir: Path, listing_schema: dict) -> list[str]:
    problems = []
    is_template = pack_dir.name == "_template"
    pack = yaml.safe_load((pack_dir / "pack.yaml").read_text(encoding="utf-8"))
    for key in ("id", "title", "domain", "country", "currency", "sources"):
        if key not in pack:
            problems.append(f"missing '{key}'")
    if not is_template and pack.get("id") != pack_dir.name:
        problems.append(f"id '{pack.get('id')}' does not match folder name")
    paths = []
    for s in pack.get("sources") or []:
        paths += [s.get("alert_setup"), s.get("parser")]
        if not s.get("senders"):
            problems.append(f"source {s.get('id')}: no senders")
        if not is_template and not s.get("terms_checked"):
            problems.append(f"source {s.get('id')}: terms_checked missing")
    paths.append((pack.get("places") or {}).get("gazetteer"))
    paths += [v for v in (pack.get("notes") or {}).values()]
    bench = pack.get("benchmark") or {}
    if bench.get("file") and not is_template:
        paths.append(bench["file"])
        path = pack_dir / bench["file"]
        if path.exists():
            with open(path, encoding="utf-8", newline="") as fh:
                cols = set(csv.DictReader(fh).fieldnames or [])
            if not BENCH_COLS <= cols:
                problems.append(f"benchmark columns missing: {sorted(BENCH_COLS - cols)}")
        for key in ("source", "licence", "checked"):
            if not bench.get(key):
                problems.append(f"benchmark.{key} missing")
    for rel in filter(None, paths):
        if not (pack_dir / rel).exists():
            problems.append(f"path in pack.yaml does not exist: {rel}")
    fixtures = pack_dir / "fixtures"
    for f in fixtures.glob("*.txt"):
        if not f.read_text(encoding="utf-8").startswith("SYNTHETIC TEST EMAIL"):
            problems.append(f"fixture not marked synthetic: {f.name}")
    expected = fixtures / "expected-extraction.json"
    if expected.exists():
        data = json.loads(expected.read_text(encoding="utf-8"))
        for name, listings in data.items():
            if not (fixtures / name).exists():
                problems.append(f"expected-extraction refers to missing fixture {name}")
            if jsonschema is not None:
                try:
                    jsonschema.validate(listings, listing_schema)
                except jsonschema.ValidationError as e:
                    problems.append(f"{name}: {e.message}")
    elif not is_template:
        problems.append("fixtures/expected-extraction.json missing")
    return problems


def main(argv):
    root = Path(argv[0] if argv else "listing-alert-agent")
    schema = json.loads((root / "schemas" / "listing.schema.json").read_text(encoding="utf-8"))
    total = 0
    for pack_dir in sorted((root / "packs").iterdir()):
        if not (pack_dir / "pack.yaml").exists():
            continue
        problems = check_pack(pack_dir, schema)
        total += len(problems)
        print(f"{pack_dir.name}: " + ("OK" if not problems else ""))
        for p in problems:
            print("  PROBLEM:", p)
    if jsonschema is None:
        print("note: jsonschema not installed; schema checks skipped")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
