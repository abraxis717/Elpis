from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_2_2_0_historical_manifest_and_failed_disposition_are_exact():
    m=ROOT/"manifests/Elpis2.2.0.RELEASE_MANIFEST.json"
    d=json.loads(m.read_text())
    assert d["release_tag"]=="Elpis2.2.0"
    assert hashlib.sha256(m.read_bytes()).hexdigest()=="1558ea7c4ee5187f28ca177eddaf16e755aadb2b53a1cbd68536148fa700c593"
    f={x["release_tag"]:x for x in json.loads((ROOT/"FAILED_RELEASES.json").read_text())["failed_releases"]}["Elpis2.2.0"]
    assert f["tag_object"]=="ba77eaf59d633c33aa1c0006d47a0020a40296dd"
    assert f["peeled_commit"]=="51ab542b01fdbb30dd4342effab2cdeaa9040f51"
    assert f["disposition"].endswith("FAILED_NOT_PUBLISHED")

def test_2_2_0_not_publishable_after_failed_disposition():
    tags={x["release_tag"] for x in json.loads((ROOT/"PUBLISHED_RELEASES.json").read_text())["published_releases"]}
    assert "Elpis2.2.0" not in tags
