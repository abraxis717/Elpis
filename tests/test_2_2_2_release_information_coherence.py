from __future__ import annotations
import json, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_current_release_declarations_are_222():
    assert (ROOT/"VERSION").read_text().strip()=="2.2.2"
    assert tomllib.loads((ROOT/"pyproject.toml").read_text())["project"]["version"]=="2.2.2"
    r=(ROOT/"README.md").read_text()
    assert "**Release line: Elpis2.2.2**" in r
    assert "RELEASE_NOTES/Elpis2.2.2.md" in r
    assert (ROOT/"RELEASE_NOTES/Elpis2.2.2.md").is_file()

def test_public_registry_links_and_runtime_boundary():
    r=(ROOT/"README.md").read_text()
    p=json.loads((ROOT/"manifests/PUBLIC_COMPONENT_REGISTRY.json").read_text())
    assert p["component_count"]==16
    for x in p["components"]:
        assert x["runtime_admission"] is False
        assert (ROOT/x["documentation_path"]).is_file()
        assert x["component_id"] in r
        assert x["documentation_path"] in r
        assert x["public_path"] in r

def test_writer_successors_and_internal_adoptions_are_reflected():
    r=(ROOT/"README.md").read_text()
    w=json.loads((ROOT/"manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json").read_text())
    for x in w["components"]:
        assert x["qualification_disposition"]=="QUALIFIED_LOCAL_SUCCESSOR"
        assert x["public_registry_admission"] is False
        assert x["runtime_admission"] is False
        assert x["component_id"] in r
    a=json.loads((ROOT/"manifests/ELPIS_2_2_0_ADOPTION_POLICY_R0.json").read_text())
    for x in a["candidates"]:
        assert x["disposition"]=="SHIP_INTERNAL_QUALIFIED"
        assert x["id"] in r
        assert x["source"] in r

def test_222_manifest_binds_corrective_surface():
    d=json.loads((ROOT/"manifests/Elpis2.2.2.RELEASE_MANIFEST.json").read_text())
    assert d["version"]=="2.2.2"
    assert d["release_tag"]=="Elpis2.2.2"
    paths={x["path"] for x in d["files"]}
    for p in [
        "README.md",
        "RELEASE_NOTES/Elpis2.2.2.md",
        "manifests/PUBLIC_COMPONENT_REGISTRY.json",
        "manifests/Elpis2.2.1.RELEASE_MANIFEST.json",
        "tests/test_readme_paper_r1_contract.py",
    ]:
        assert p in paths
