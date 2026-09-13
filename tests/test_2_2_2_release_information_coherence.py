from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_2_2_2_manifest_is_preserved_as_immutable_release_payload():
    path=ROOT/"manifests/Elpis2.2.2.RELEASE_MANIFEST.json"
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest()=="57934169b83ac1a64c1b1b47cfccbd087753c308e44f5bbef9e2c78d88c7211f"
    payload=json.loads(path.read_text())
    assert payload["version"]=="2.2.2"
    assert payload["release_tag"]=="Elpis2.2.2"

def test_2_2_2_is_materialized_in_publication_registry():
    data=json.loads((ROOT/"PUBLISHED_RELEASES.json").read_text())
    entry={x["release_tag"]:x for x in data["published_releases"]}["Elpis2.2.2"]
    assert entry["peeled_commit"]=="65bf1f14105ae0c1f6c376896506fc72d06d83b0"
    assert entry["manifest_sha256"]=="57934169b83ac1a64c1b1b47cfccbd087753c308e44f5bbef9e2c78d88c7211f"
