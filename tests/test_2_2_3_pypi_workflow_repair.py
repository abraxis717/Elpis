from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_2_2_3_failed_local_manifest_is_preserved():
    path=ROOT/"manifests/Elpis2.2.3.RELEASE_MANIFEST.json"
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest()=="79fc431abf8bea24a4e591386a28f93359e26e4faf75378451f42f8d02b6cb89"
    payload=json.loads(path.read_text())
    assert payload["version"]=="2.2.3"
    assert payload["release_tag"]=="Elpis2.2.3"

def test_2_2_3_was_never_materialized_as_a_published_registry_release():
    data=json.loads((ROOT/"PUBLISHED_RELEASES.json").read_text())
    assert "Elpis2.2.3" not in {x["release_tag"] for x in data["published_releases"]}
