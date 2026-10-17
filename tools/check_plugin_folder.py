#!/usr/bin/env python3
"""Pre-submission checks for the plugin folder (Anthropic plugin directory rules, checked 2026-10-17).

- README.md of at least 40 words and a LICENSE file
- at most 512 files, each under 256 KiB
- only text, image and font files; no .DS_Store or other junk
- no obvious secrets (API keys, tokens, private keys)
- no personal data from the author's own setup: terms listed one per line in tools/personal-terms.txt
  (git-ignored, so the list itself is never published) or in LAA_PERSONAL_TERMS (separated by ';').
  Checked in the plugin folder and in every other text file git tracks (docs, README, media notes).
- runtime-manifest.txt lists every file the scheduled runs need (use --write to regenerate)

Usage: python tools/check_plugin_folder.py [plugin_dir] [--write]
"""
import re
import sys
from pathlib import Path

MAX_FILES = 512
MAX_BYTES = 256 * 1024
TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".py", ".sh", ".toml", ".html", ".css", ".js"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
FONT_EXT = {".woff", ".woff2", ".ttf", ".otf"}
ALLOWED_NAMES = {"LICENSE"}
JUNK = {".DS_Store", "Thumbs.db", "__pycache__"}
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}", r"ghp_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}", r"AKIA[0-9A-Z]{16}",
    r"AIza[0-9A-Za-z_\-]{35}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"5b3ce3597851110001cf6248[0-9a-f]{20,}",  # openrouteservice key prefix
]
import os
import subprocess

TERMS_FILE = Path(__file__).with_name("personal-terms.txt")


def personal_terms() -> list[str]:
    """Personal details that must never ship, as lower-case substrings. Kept outside git."""
    terms = []
    if TERMS_FILE.exists():
        terms += [ln.strip() for ln in TERMS_FILE.read_text(encoding="utf-8").splitlines()
                  if ln.strip() and not ln.lstrip().startswith("#")]
    terms += [t.strip() for t in os.environ.get("LAA_PERSONAL_TERMS", "").split(";") if t.strip()]
    return [t.lower() for t in terms]
# Files the scheduled runs download when the plugin is not installed (see setup/references/scheduling.md).
RUNTIME_GLOBS = ["skills/run-alerts/**/*", "skills/weekly-digest/**/*", "schemas/*", "packs/**/*"]


def runtime_files(root: Path) -> list[str]:
    files = set()
    for pattern in RUNTIME_GLOBS:
        for p in root.glob(pattern):
            if p.is_file() and "__pycache__" not in p.parts:
                files.add(p.relative_to(root).as_posix())
    return sorted(files)


def main(argv):
    write = "--write" in argv
    args = [a for a in argv if not a.startswith("--")]
    root = Path(args[0] if args else "listing-alert-agent").resolve()
    problems = []
    personal = personal_terms()
    files = [p for p in root.rglob("*") if p.is_file() and "evals/results" not in p.relative_to(root).as_posix()]  # local eval output, git-ignored
    if len(files) > MAX_FILES:
        problems.append(f"{len(files)} files (limit {MAX_FILES})")
    for p in files:
        rel = p.relative_to(root).as_posix()
        if any(part in JUNK for part in p.parts):
            problems.append(f"junk file: {rel}")
            continue
        if p.stat().st_size >= MAX_BYTES:
            problems.append(f"too large ({p.stat().st_size} bytes): {rel}")
        ext = p.suffix.lower()
        if p.name not in ALLOWED_NAMES and ext not in TEXT_EXT | IMAGE_EXT | FONT_EXT:
            problems.append(f"file type not allowed: {rel}")
        if ext in TEXT_EXT or p.name in ALLOWED_NAMES:
            text = p.read_text(encoding="utf-8", errors="replace")
            for pat in SECRET_PATTERNS:
                if re.search(pat, text):
                    problems.append(f"possible secret ({pat}): {rel}")
            low = text.lower()
            for i, word in enumerate(personal, 1):
                if word in low:
                    problems.append(f"personal term #{i} found: {rel}")
    # The rest of the repository: every text file git tracks outside the plugin folder.
    repo = root.parent
    if personal:
        try:
            tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            tracked = []
        for rel in tracked:
            p = repo / rel
            if root in p.resolve().parents or not p.is_file() or p.suffix.lower() not in TEXT_EXT | {""}:
                continue
            low = p.read_text(encoding="utf-8", errors="replace").lower()
            for i, word in enumerate(personal, 1):
                if word in low:
                    problems.append(f"personal term #{i} found: {rel}")
    else:
        print("NOTE: no personal terms configured (tools/personal-terms.txt or LAA_PERSONAL_TERMS); personal-data check skipped")
    readme = root / "README.md"
    if not readme.exists() or len(readme.read_text(encoding="utf-8").split()) < 40:
        problems.append("README.md missing or under 40 words")
    if not (root / "LICENSE").exists():
        problems.append("LICENSE missing")
    manifest = root / "runtime-manifest.txt"
    expected = "\n".join(runtime_files(root)) + "\n"
    if write:
        manifest.write_text(expected, encoding="utf-8")
    elif not manifest.exists() or manifest.read_text(encoding="utf-8") != expected:
        problems.append("runtime-manifest.txt is out of date: run python tools/check_plugin_folder.py --write")
    for line in problems:
        print("PROBLEM:", line)
    print(f"{len(files)} files checked in {root.name}: " + ("OK" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
