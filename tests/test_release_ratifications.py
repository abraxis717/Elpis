from __future__ import annotations

import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "elpis.release-ratification.v1"


def test_current_published_release_has_exact_ratification():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    rows = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text(encoding="utf-8")
    )["publication_assertions"]
    current = [row for row in rows if row.get("version") == version]
    ratification = ROOT / "RELEASE_RATIFICATIONS" / f"Elpis{version}.json"

    if not current:
        assert not ratification.exists()
        return

    assert len(current) == 1
    assert ratification.is_file()
    data = json.loads(ratification.read_text(encoding="utf-8"))
    assert data["schema"] == SCHEMA
    assert data["version"] == version
    assert data["release_tag"] == f"Elpis{version}"
    assert data["sealed_commit"] == current[0]["peeled_commit"]
    assert data["manifest_sha256"] == current[0]["manifest_sha256"]

    machine = runpy.run_path(str(ROOT / "tools/release_orchestrator.py"))
    assert data["publication_assertion_sha256"] == machine["digest"](current[0])
