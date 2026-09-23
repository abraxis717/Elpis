from __future__ import annotations

import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_top_level_apache_license_is_standard_tracked_copy():
    top = (ROOT / "LICENSE").read_bytes()
    retained = (
        ROOT / "components/InferenceInfrastructure/licenses/Apache-2.0.txt"
    ).read_bytes()
    assert top == retained
    text = top.decode("utf-8")
    assert "Apache License" in text
    assert "Version 2.0, January 2004" in text


def test_repo_is_the_attribution_anchor():
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "https://github.com/abraxis717/Elpis" in notice
    assert "the attribution and provenance reference for the project" in notice
    assert "This NOTICE is informational and does not modify the Apache License." in notice

    # No extra personal-name/trademark policy was introduced as a licensing layer.
    assert "Joe Alpharius" not in notice
    assert not (ROOT / "TRADEMARKS.md").exists()
    assert not (ROOT / "PROVENANCE.md").exists()


def test_pep639_metadata_and_citation_are_apache_2():
    root_meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    needle = tomllib.loads(
        (ROOT / "drivers/needle3/pyproject.toml").read_text(encoding="utf-8")
    )
    assert root_meta["project"]["license"] == "Apache-2.0"
    assert root_meta["project"]["license-files"] == ["LICENSE", "NOTICE"]
    assert needle["project"]["license"] == "Apache-2.0"

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "license: Apache-2.0" in citation
    assert 'repository-code: "https://github.com/abraxis717/Elpis"' in citation
    assert "cite the canonical Elpis repository" in citation


def test_research_references_bind_quadratic_and_dynamical_context():
    refs = (ROOT / "RESEARCH_REFERENCES.md").read_text(encoding="utf-8")
    assert "arXiv:2608.13335" in refs
    assert "Neural Quadratic Forms" in refs
    assert "collective/order-parameter" in refs
    assert "arXiv:2609.04963" in refs
    assert "Fractal basins trap latent reasoning" in refs
    assert "not software-code provenance" in refs


def test_license_map_and_review_distinguish_first_and_third_party():
    mapping = json.loads(
        (ROOT / "manifests/FILE_LICENSE_MAP.json").read_text(encoding="utf-8")
    )
    review = json.loads(
        (ROOT / "manifests/LICENSE_REVIEW.json").read_text(encoding="utf-8")
    )
    assert mapping["schema"] == "elpis.public.file_licensemap.v2"
    assert mapping["default_license"] == "Apache-2.0"
    assert mapping["default_copyright"] == "Elpis Contributors"
    exceptions = {row["path_prefix"]: row for row in mapping["exceptions"]}
    assert exceptions["src/elpis_reference/vendor/"]["license"] == "UPSTREAM_FILE_SPECIFIC"

    assert review["schema"] == "elpis.public.licensereview.v2"
    assert review["top_level_license"] == "Apache-2.0"
    assert review["canonical_repository"] == "https://github.com/abraxis717/Elpis"
    assert review["third_party_material_present"] is True


def test_samsung_vendor_header_matches_retained_mit_license():
    vendor_init = (
        ROOT / "src/elpis_reference/vendor/__init__.py"
    ).read_text(encoding="utf-8")
    retained = (
        ROOT / "LICENSES/Samsung-TinyRecursiveModels-MIT.txt"
    ).read_text(encoding="utf-8")
    assert "License: MIT." in vendor_init
    assert "MIT License" in retained
    assert "Samsung Electronics Co., Ltd." in retained


def test_readme_keeps_open_source_use_broad_and_repo_attribution_simple():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## 15. Licensing", 1)[1]
    assert "Apache License 2.0" in section
    assert "https://github.com/abraxis717/Elpis" in section
    assert "CITATION.cff" in section
    assert "NOTICE" in section
    assert "RESEARCH_REFERENCES.md" in section
    for forbidden in ("noncommercial", "no commercial", "bad faith", "trademark"):
        assert forbidden not in section.lower()
