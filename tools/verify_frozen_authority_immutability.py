#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "frozen_authority_baseline_Elpis2.2.7.json"

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    frozen_root = ROOT / data["frozen_root"]
    expected = data["sha256"]

    actual_frozen = {
        p.relative_to(ROOT).as_posix()
        for p in frozen_root.rglob("*")
        if p.is_file() or p.is_symlink()
    }
    expected_frozen = {
        rel for rel in expected
        if rel == data["frozen_root"] or rel.startswith(data["frozen_root"] + "/")
    }
    if actual_frozen != expected_frozen:
        missing = sorted(expected_frozen - actual_frozen)
        extra = sorted(actual_frozen - expected_frozen)
        raise SystemExit(
            "FROZEN_AUTHORITY_PATHSET_DRIFT "
            f"missing={missing[:20]} extra={extra[:20]}"
        )

    failures = []
    for rel, want in sorted(expected.items()):
        p = ROOT / rel
        if not p.is_file():
            failures.append(f"MISSING:{rel}")
            continue
        got = digest(p)
        if got != want:
            failures.append(f"SHA256:{rel}:{got}:{want}")
    if failures:
        for item in failures:
            print(item)
        return 1
    print("PASS_FROZEN_AUTHORITY_AND_ELPIS_CANON_HOOK_IMMUTABLE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
