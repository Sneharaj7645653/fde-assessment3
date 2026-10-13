"""Verify that instructor-provided evidence files are byte-identical to the baseline.

The manifest (integrity/starter_manifest.json) records the SHA-256 of every
instructor-provided file as committed in the baseline commit (the repository
state received at handover). `protected` files are inputs/evidence and must
never change; `scaffold_code` files are starter code that the assessment allows
us to fix, so their drift is reported but not an error.

Usage:
    python scripts/check_starter_integrity.py            # verify
    python scripts/check_starter_integrity.py --generate <baseline-commit>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "integrity" / "starter_manifest.json"

PROTECTED_PREFIXES = ("data/", "mock_api/", "evals/public_cases.json", "evals/README.md", "docs/")
SOLUTION_PREFIXES = ("specs/",)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate(commit: str) -> None:
    files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], cwd=ROOT, text=True).split()
    entries = {}
    for path in files:
        if path.startswith(SOLUTION_PREFIXES) or path.startswith("integrity/"):
            continue
        blob = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
        kind = "protected" if path.startswith(PROTECTED_PREFIXES) else "scaffold_code"
        entries[path] = {"sha256": _sha(blob), "kind": kind}
    MANIFEST.write_text(json.dumps({"baseline_commit": commit, "files": entries}, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {MANIFEST.relative_to(ROOT)} with {len(entries)} files")


def verify() -> int:
    manifest = json.loads(MANIFEST.read_text())
    bad, drift = [], []
    for path, meta in manifest["files"].items():
        target = ROOT / path
        current = _sha(target.read_bytes()) if target.exists() else None
        if current == meta["sha256"]:
            continue
        state = "MISSING" if current is None else "MODIFIED"
        (bad if meta["kind"] == "protected" else drift).append(f"{state} {path}")
    print(f"Baseline commit: {manifest['baseline_commit']}")
    for line in drift:
        print(f"  scaffold code changed (allowed, documented in docs/starter_changes.md): {line}")
    for line in bad:
        print(f"  PROTECTED FILE VIOLATION: {line}", file=sys.stderr)
    protected = sum(1 for m in manifest["files"].values() if m["kind"] == "protected")
    print(f"Protected files checked: {protected}; violations: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", metavar="COMMIT")
    args = parser.parse_args()
    if args.generate:
        generate(args.generate)
    else:
        raise SystemExit(verify())
