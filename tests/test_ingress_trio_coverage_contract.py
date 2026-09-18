from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import shutil

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools/verify_ingress_trio_coverage.py"
COVERAGE = Path("manifests/INGRESS_TRIO_COVERAGE_R0.json")
PUBLIC = Path("manifests/PUBLIC_COMPONENT_REGISTRY.json")

BOUND_PATHS = [
    Path("components/StreamingRegexIngress/COMPONENT_MANIFEST.json"),
    Path("components/StreamingRegexIngress/QUALIFICATION_BINDING.json"),
    Path("components/StreamingRegexIngress/contracts/INCREMENTAL_V2.json"),
    Path("components/RegexHACFQueryIngress/COMPONENT_MANIFEST.json"),
    Path("components/RegexHACFQueryIngress/QUALIFICATION_BINDING.json"),
    Path("components/RegexHACFQueryIngress/BUILD_CONTRACT.json"),
    Path("components/QueryLocalProposalIngress/COMPONENT_MANIFEST.json"),
    Path("components/QueryLocalProposalIngress/QUALIFICATION_BINDING.json"),
    Path(
        "components/QueryLocalProposalIngress/contracts/"
        "QUERY_LOCAL_PROPOSAL_REGISTRY_V1.json"
    ),
]


def _ns():
    return runpy.run_path(str(VERIFY))


def _fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for rel in [COVERAGE, PUBLIC, *BOUND_PATHS]:
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    return repo


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_current_ingress_trio_coverage_verifies():
    ns = _ns()
    assert ns["verify"](ROOT) == []


def test_coverage_is_exact_three_nonpublic_runtime_zero_surfaces():
    data = _load(ROOT / COVERAGE)
    assert data["schema"] == "elpis.ingress-trio-coverage.v1"
    assert data["component_count"] == 3
    assert data["runtime_admission"] is False
    assert data["semantic_truth_authority"] is False
    assert data["execution_authority"] is False
    assert data["public_registry_admission"] is False
    assert [row["component_id"] for row in data["components"]] == [
        "StreamingRegexIngress_R1",
        "RegexHACFQueryIngress_R0",
        "QueryLocalProposalIngress_R0",
    ]


def test_bound_ingress_authority_drift_is_detected(tmp_path: Path):
    ns = _ns()
    repo = _fixture(tmp_path)
    target = repo / "components/StreamingRegexIngress/COMPONENT_MANIFEST.json"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    errors = ns["verify"](repo)
    assert (
        "BOUND_SHA256:StreamingRegexIngress_R1:component_manifest"
        in errors
    )


def test_runtime_admission_flip_is_detected_even_with_valid_coverage_self_hash(
    tmp_path: Path,
):
    ns = _ns()
    repo = _fixture(tmp_path)
    path = repo / COVERAGE
    data = _load(path)
    data["components"][1]["runtime_admission"] = True
    data["coverage_self_hash"] = ns["_self_hash"](data)
    _dump(path, data)

    errors = ns["verify"](repo)
    assert "COMPONENT_RUNTIME_ADMISSION:RegexHACFQueryIngress_R0" in errors


def test_public_registry_admission_is_detected_even_if_public_hash_is_rebound(
    tmp_path: Path,
):
    ns = _ns()
    repo = _fixture(tmp_path)

    public_path = repo / PUBLIC
    public = _load(public_path)
    public["components"][0]["component_id"] = "StreamingRegexIngress_R1"
    _dump(public_path, public)

    coverage_path = repo / COVERAGE
    coverage = _load(coverage_path)
    coverage["public_registry_sha256"] = hashlib.sha256(
        public_path.read_bytes()
    ).hexdigest()
    coverage["coverage_self_hash"] = ns["_self_hash"](coverage)
    _dump(coverage_path, coverage)

    errors = ns["verify"](repo)
    assert "PUBLIC_REGISTRY_ADMISSION:StreamingRegexIngress_R1" in errors
