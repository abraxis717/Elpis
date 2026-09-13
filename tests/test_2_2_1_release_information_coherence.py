from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_2_2_1_failed_local_candidate_manifest_is_preserved():
    path=ROOT/"manifests/Elpis2.2.1.RELEASE_MANIFEST.json"
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest()=="c3b31cc74e2d5e417a462f61bb20b38801674f4a47661b8da0a8ce04ead5ac16"
    payload=json.loads(path.read_text())
    assert payload["version"]=="2.2.1"
    assert payload["release_tag"]=="Elpis2.2.1"

def test_2_2_1_was_never_registered_as_publishable():
    published={x["release_tag"] for x in json.loads((ROOT/"PUBLISHED_RELEASES.json").read_text())["published_releases"]}
    assert "Elpis2.2.1" not in published
