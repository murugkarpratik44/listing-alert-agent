#!/usr/bin/env python3
"""Monthly maintenance check for listing-alert-agent.

Runs the local checks and lists what a person (or Claude) should verify online:
- unit, schema and pack tests; pack and plugin-folder checks
- dates in packs and docs older than 12 months ("checked", "terms_checked", "Checked ...")
- every external link in the plugin folder and docs, for a reachability check
- the benchmark table: the quarter the pack holds and the latest quarter in the CSO table (read from the
  CSO open-data API, so no web page needs to be interpreted)

Usage: python tools/maintenance_check.py [--today YYYY-MM-DD] [--offline]
Prints one JSON report. Never edits anything.
"""
import datetime as dt
import json
import re
import os
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE_PATTERNS = [
    re.compile(r"(?:checked|terms_checked|checked on|Checked)[:\s]+(\d{4}-\d{2}-\d{2})"),
    re.compile(r"Status: .*?(\d{4}-\d{2}-\d{2})"),
]
URL = re.compile(r"https?://[^\s\"'<>`\]]+")
# Never fetched by maintenance: listing sites (their terms forbid automated access), templates, schema ids.
SKIP_HOSTS = ("daft.ie", "myhome.ie", "rent.ie", "property.ie", "donedeal.ie")


def clean_url(u: str) -> str | None:
    u = u.rstrip(".,;:")
    while u.endswith(")") and u.count(")") > u.count("("):
        u = u[:-1]
    host = re.sub(r"^https?://", "", u).split("/")[0].lower()
    if any(host == h or host.endswith("." + h) for h in SKIP_HOSTS):
        return None
    if "example" in u or "{" in u or "<" in u or u.endswith(("=", "&", "/listing-alert-agent/")) or "/schemas/" in u:
        return None
    return u


CSO_API = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{table}/JSON-stat/2.0/en"


def cso_latest_quarter(table: str = "RIQ02") -> dict:
    """Latest quarter and update date of a CSO table, from its JSON-stat metadata. Never raises."""
    try:
        ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE"))
        req = urllib.request.Request(CSO_API.format(table=table), headers={"User-Agent": "listing-alert-agent maintenance check"})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            data = json.load(r)
        time_dim = next(k for k in data["id"] if k.startswith("TLIST"))
        cat = data["dimension"][time_dim]["category"]
        last = cat["index"][-1]
        return {"latest": cat.get("label", {}).get(last, last), "table_updated": data.get("updated"), "error": None}
    except Exception as exc:  # network, proxy or format change: report, do not fail the check
        return {"latest": None, "table_updated": None, "error": f"{type(exc).__name__}: {exc}"[:200]}


def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    return {"command": " ".join(cmd), "ok": p.returncode == 0, "tail": tail}


def main(argv):
    today = dt.date.fromisoformat(argv[argv.index("--today") + 1]) if "--today" in argv else dt.date.today()
    checks = [
        run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"]),
        run([sys.executable, "-B", "tools/check_packs.py"]),
        run([sys.executable, "-B", "tools/check_plugin_folder.py"]),
    ]
    stale, links = [], {}
    files = [p for p in (ROOT / "listing-alert-agent").rglob("*") if p.suffix in {".md", ".yaml", ".yml", ".json"}]
    files += list((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(ROOT).as_posix()
        for pat in DATE_PATTERNS:
            for m in pat.finditer(text):
                d = dt.date.fromisoformat(m.group(1))
                if (today - d).days > 365:
                    stale.append({"file": rel, "date": m.group(1), "age_days": (today - d).days})
        for raw in URL.findall(text):
            u = clean_url(raw)
            if u:
                links.setdefault(u, []).append(rel)
    bench = ROOT / "listing-alert-agent" / "packs" / "ie-rentals" / "benchmark" / "README.md"
    bench_note = re.search(r"Data to ([^.\n]+)", bench.read_text(encoding="utf-8")).group(1) if bench.exists() else None
    cso = {"latest": None, "table_updated": None, "error": "skipped (--offline)"} if "--offline" in argv else cso_latest_quarter()
    held = (bench_note or "").replace(" ", "")
    report = {
        "date": today.isoformat(),
        "checks": checks,
        "all_checks_ok": all(c["ok"] for c in checks),
        "stale_dates": stale,
        "links_to_verify": sorted(links),
        "link_sources": links,
        "benchmark": {"pack": "ie-rentals", "table": "CSO RIQ02", "holds": bench_note,
                      "latest_in_table": cso["latest"], "table_updated": cso["table_updated"],
                      "update_due": (cso["latest"] is not None and cso["latest"] > held) if held else None,
                      "error": cso["error"],
                      "note": "Only RIQ02 counts. RTB Rent Index reports use a different, standardised measure; do not mix them."},
    }
    print(json.dumps(report, indent=2))
    return 0 if report["all_checks_ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
