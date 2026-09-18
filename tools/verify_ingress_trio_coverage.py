#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
COVERAGE_REL = Path("manifests/INGRESS_TRIO_COVERAGE_R0.json")
PUBLIC_REL = Path("manifests/PUBLIC_COMPONENT_REGISTRY.json")

EXPECTED_ORDER = [
    "StreamingRegexIngress_R1",
    "RegexHACFQueryIngress_R0",
    "QueryLocalProposalIngress_R0",
]

EXPECTED_PATHS = {
    "StreamingRegexIngress_R1": {
        "component_root": "components/StreamingRegexIngress",
        "component_manifest": "components/StreamingRegexIngress/COMPONENT_MANIFEST.json",
        "qualification_binding": "components/StreamingRegexIngress/QUALIFICATION_BINDING.json",
        "component_contract": "components/StreamingRegexIngress/contracts/INCREMENTAL_V2.json",
    },
    "RegexHACFQueryIngress_R0": {
        "component_root": "components/RegexHACFQueryIngress",
        "component_manifest": "components/RegexHACFQueryIngress/COMPONENT_MANIFEST.json",
        "qualification_binding": "components/RegexHACFQueryIngress/QUALIFICATION_BINDING.json",
        "component_contract": "components/RegexHACFQueryIngress/BUILD_CONTRACT.json",
    },
    "QueryLocalProposalIngress_R0": {
        "component_root": "components/QueryLocalProposalIngress",
        "component_manifest": "components/QueryLocalProposalIngress/COMPONENT_MANIFEST.json",
        "qualification_binding": "components/QueryLocalProposalIngress/QUALIFICATION_BINDING.json",
        "component_contract": "components/QueryLocalProposalIngress/contracts/QUERY_LOCAL_PROPOSAL_REGISTRY_V1.json",
    },
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _self_hash(value: dict[str, object]) -> str:
    return _sha_bytes(
        _canonical_bytes(
            {key: item for key, item in value.items() if key != "coverage_self_hash"}
        )
    )


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(root: Path = REPO) -> list[str]:
    root = Path(root)
    errors: list[str] = []

    try:
        coverage = _load_json(root / COVERAGE_REL)
    except Exception as exc:
        return [f"COVERAGE_LOAD:{type(exc).__name__}:{exc}"]
    try:
        public = _load_json(root / PUBLIC_REL)
    except Exception as exc:
        return [f"PUBLIC_REGISTRY_LOAD:{type(exc).__name__}:{exc}"]

    if coverage.get("schema") != "elpis.ingress-trio-coverage.v1":
        errors.append("COVERAGE_SCHEMA")
    if coverage.get("coverage_id") != "INGRESS_TRIO_COVERAGE_R0":
        errors.append("COVERAGE_ID")
    if coverage.get("runtime_admission") is not False:
        errors.append("COVERAGE_RUNTIME_ADMISSION")
    if coverage.get("semantic_truth_authority") is not False:
        errors.append("COVERAGE_SEMANTIC_AUTHORITY")
    if coverage.get("execution_authority") is not False:
        errors.append("COVERAGE_EXECUTION_AUTHORITY")
    if coverage.get("public_registry_admission") is not False:
        errors.append("COVERAGE_PUBLIC_REGISTRY_ADMISSION")
    if coverage.get("coverage_self_hash") != _self_hash(coverage):
        errors.append("COVERAGE_SELF_HASH")

    if coverage.get("public_registry_path") != str(PUBLIC_REL):
        errors.append("PUBLIC_REGISTRY_PATH")
    if coverage.get("public_registry_sha256") != _sha_path(root / PUBLIC_REL):
        errors.append("PUBLIC_REGISTRY_SHA256")
    if public.get("component_count") != 16:
        errors.append("PUBLIC_COMPONENT_COUNT")
    if public.get("runtime_admission") is not False:
        errors.append("PUBLIC_RUNTIME_ADMISSION")

    rows = coverage.get("components")
    if not isinstance(rows, list):
        return errors + ["COVERAGE_COMPONENTS"]

    ids = [
        row.get("component_id")
        for row in rows
        if isinstance(row, dict)
    ]
    if ids != EXPECTED_ORDER:
        errors.append("COMPONENT_ORDER")
    if len(ids) != len(set(ids)):
        errors.append("COMPONENT_DUPLICATE")
    if coverage.get("component_count") != len(EXPECTED_ORDER):
        errors.append("COMPONENT_COUNT")

    public_rows = public.get("components")
    if not isinstance(public_rows, list):
        errors.append("PUBLIC_COMPONENTS")
        public_rows = []
    public_ids = {
        row.get("component_id")
        for row in public_rows
        if isinstance(row, dict)
    }
    public_paths = {
        row.get("public_path")
        for row in public_rows
        if isinstance(row, dict)
    }

    for expected_id in EXPECTED_ORDER:
        if expected_id in public_ids:
            errors.append(f"PUBLIC_REGISTRY_ADMISSION:{expected_id}")
        expected_root = EXPECTED_PATHS[expected_id]["component_root"]
        if expected_root in public_paths:
            errors.append(f"PUBLIC_REGISTRY_PATH_ADMISSION:{expected_id}")

    by_id = {
        row.get("component_id"): row
        for row in rows
        if isinstance(row, dict) and row.get("component_id")
    }

    for component_id in EXPECTED_ORDER:
        row = by_id.get(component_id)
        if not isinstance(row, dict):
            errors.append(f"COMPONENT_MISSING:{component_id}")
            continue

        expected = EXPECTED_PATHS[component_id]
        if row.get("component_root") != expected["component_root"]:
            errors.append(f"COMPONENT_ROOT:{component_id}")
        if row.get("runtime_admission") is not False:
            errors.append(f"COMPONENT_RUNTIME_ADMISSION:{component_id}")
        if row.get("semantic_truth_authority") is not False:
            errors.append(f"COMPONENT_SEMANTIC_AUTHORITY:{component_id}")
        if row.get("public_registry_admission") is not False:
            errors.append(f"COMPONENT_PUBLIC_ADMISSION:{component_id}")

        bindings = row.get("bindings")
        if not isinstance(bindings, dict):
            errors.append(f"BINDINGS:{component_id}")
            continue

        loaded: dict[str, dict[str, object]] = {}
        for key in (
            "component_manifest",
            "qualification_binding",
            "component_contract",
        ):
            binding = bindings.get(key)
            if not isinstance(binding, dict):
                errors.append(f"BINDING_RECORD:{component_id}:{key}")
                continue
            path = binding.get("path")
            if path != expected[key]:
                errors.append(f"BINDING_PATH:{component_id}:{key}")
                continue
            target = root / str(path)
            if not target.is_file():
                errors.append(f"BINDING_MISSING:{component_id}:{key}")
                continue
            actual_sha = _sha_path(target)
            if binding.get("sha256") != actual_sha:
                errors.append(f"BOUND_SHA256:{component_id}:{key}")
            try:
                loaded[key] = _load_json(target)
            except Exception as exc:
                errors.append(
                    f"BOUND_JSON:{component_id}:{key}:{type(exc).__name__}"
                )

        manifest = loaded.get("component_manifest", {})
        qualification = loaded.get("qualification_binding", {})
        contract = loaded.get("component_contract", {})

        if manifest.get("component_id") != component_id:
            errors.append(f"MANIFEST_COMPONENT_ID:{component_id}")
        if manifest.get("qualification_disposition") != "QUALIFIED_SUCCESSOR_COMPONENT":
            errors.append(f"QUALIFICATION_DISPOSITION:{component_id}")
        if manifest.get("runtime_admission") is not False:
            errors.append(f"MANIFEST_RUNTIME_ADMISSION:{component_id}")
        if manifest.get("semantic_truth_authority") is not False:
            errors.append(f"MANIFEST_SEMANTIC_AUTHORITY:{component_id}")
        if qualification.get("runtime_admission") is not False:
            errors.append(f"QUALIFICATION_RUNTIME_ADMISSION:{component_id}")

        if component_id in {
            "StreamingRegexIngress_R1",
            "RegexHACFQueryIngress_R0",
        }:
            for source_name, source in (
                ("manifest", manifest),
                ("qualification", qualification),
            ):
                successor = source.get("successor_v2")
                if not isinstance(successor, dict):
                    errors.append(f"SUCCESSOR_V2:{component_id}:{source_name}")
                    continue
                if successor.get("implementation_status") != "AVAILABLE":
                    errors.append(
                        f"SUCCESSOR_V2_IMPLEMENTATION:{component_id}:{source_name}"
                    )
                if successor.get("qualification_status") != (
                    "SUCCESSOR_TESTS_PASS_HISTORICAL_MATRIX_UNAVAILABLE"
                ):
                    errors.append(
                        f"SUCCESSOR_V2_QUALIFICATION:{component_id}:{source_name}"
                    )
                for field in (
                    "runtime_admission",
                    "semantic_authority",
                    "execution_authority",
                    "admission_authority",
                ):
                    if successor.get(field) is not False:
                        errors.append(
                            f"SUCCESSOR_V2_{field.upper()}:"
                            f"{component_id}:{source_name}"
                        )

        if component_id == "StreamingRegexIngress_R1":
            if manifest.get("admission_authority") is not False:
                errors.append("STREAMING_ADMISSION_AUTHORITY")
            if manifest.get("execution_authority") is not False:
                errors.append("STREAMING_EXECUTION_AUTHORITY")
            if contract.get("implementation_status") != "AVAILABLE":
                errors.append("STREAMING_V2_CONTRACT_IMPLEMENTATION")
            if contract.get("schema") != "elpis.streaming-regex-incremental.v2.contract":
                errors.append("STREAMING_V2_CONTRACT_SCHEMA")

        elif component_id == "RegexHACFQueryIngress_R0":
            if manifest.get("execution_authority") is not False:
                errors.append("REGEX_HACF_EXECUTION_AUTHORITY")
            if contract.get("schema") != "elpis.regex-hacf-query-ingress.build-contract.v1":
                errors.append("REGEX_HACF_BUILD_SCHEMA")
            if contract.get("build_system_admission") is not True:
                errors.append("REGEX_HACF_BUILD_ADMISSION")
            if contract.get("runtime_admission") is not False:
                errors.append("REGEX_HACF_BUILD_RUNTIME_ADMISSION")
            requires = contract.get("requires")
            if not isinstance(requires, dict):
                errors.append("REGEX_HACF_REQUIRES")
            else:
                if "StreamingRegexIngress" not in requires:
                    errors.append("REGEX_HACF_REQUIRES_STREAMING")
                if "QueryLocalProposalIngress" not in requires:
                    errors.append("REGEX_HACF_REQUIRES_QUERY_LOCAL")

        elif component_id == "QueryLocalProposalIngress_R0":
            if qualification.get("verdict") != (
                "PASS_ATOMIC_QUERY_LOCAL_PROPOSAL_BATCH_INGRESS_R1"
            ):
                errors.append("QUERY_LOCAL_QUALIFICATION_VERDICT")
            if contract.get("schema") != "elpis.query-local-proposal-registry.v1":
                errors.append("QUERY_LOCAL_CONTRACT_SCHEMA")
            if contract.get("registry_scope") != "QUERY_LOCAL_OVERLAY_ONLY":
                errors.append("QUERY_LOCAL_REGISTRY_SCOPE")
            if contract.get("grid81_semantics") is not False:
                errors.append("QUERY_LOCAL_GRID81_SEMANTICS")
            if contract.get("semantic_spine_v1_mutated") is not False:
                errors.append("QUERY_LOCAL_SEMANTIC_SPINE_MUTATION")
            if contract.get("status") != "SUCCESSOR_CONTRACT_CANDIDATE_UNPROMOTED":
                errors.append("QUERY_LOCAL_CONTRACT_STATUS")

    return errors


def main() -> int:
    errors = verify(REPO)
    if errors:
        print(json.dumps(
            {
                "schema": "elpis.ingress-trio-coverage-verification.v1",
                "status": "FAIL",
                "errors": errors,
            },
            sort_keys=True,
        ))
        return 1
    print(json.dumps(
        {
            "schema": "elpis.ingress-trio-coverage-verification.v1",
            "status": "PASS",
            "component_count": 3,
            "public_registry_admission": False,
            "runtime_admission": False,
            "errors": [],
        },
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
