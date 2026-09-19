#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_NAME = "PUBLICATION_ASSERTIONS.json"
LEGACY_NAME = "PUBLISHED_RELEASES.json"
FAILED_NAME = "FAILED_RELEASES.json"
SCHEMA = "elpis.publication-assertions.v2"
LEGACY_SCHEMA = "elpis.published-releases.v1"
RELEASE_IDENTITY_AUTHORITY = "annotated-ref:refs/tags/Elpis<semver>"
PUBLICATION_FACT_AUTHORITY = "explicit-observation-receipts"
TAG_RE = re.compile(r"^Elpis(\d+)\.(\d+)\.(\d+)$")
HEX_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DIST_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

REQUIRED_ACTIONS = {
    "tag_ci": ("CI", "push"),
    "tag_reference_runtime": ("reference-runtime", "push"),
    "tag_component_attribution": ("Component attribution", "push"),
    "tag_platform_matrix": ("platform-matrix", "push"),
    "release_event_ci": ("CI", "release"),
    "pypi_publish": ("pypi-publish", "release"),
}
ENTRY_KEYS = {
    "github_actions",
    "github_release",
    "manifest_path",
    "manifest_sha256",
    "peeled_commit",
    "peeled_object_type",
    "pypi",
    "release_tag",
    "tag_object",
    "tag_object_type",
    "version",
}
TOP_LEVEL_KEYS = {
    "legacy_publication_history",
    "publication_assertions",
    "publication_fact_authority",
    "release_identity_authority",
    "schema",
}


class PublicationAuthorityError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PublicationAuthorityError(f"READ_FAILED:{path}:{exc}") from exc


def _git(root: Path, *args: str, text: bool = True) -> str | bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if proc.returncode:
        stderr = proc.stderr.strip() if text else proc.stderr.decode(errors="replace").strip()
        raise PublicationAuthorityError(
            "GIT_AUTHORITY_UNAVAILABLE:" + " ".join(args) + ":" + stderr
        )
    return proc.stdout.strip() if text else proc.stdout


def _semver_key(tag: str) -> tuple[int, int, int]:
    match = TAG_RE.fullmatch(tag)
    if match is None:
        raise PublicationAuthorityError(f"INVALID_RELEASE_TAG:{tag}")
    return tuple(int(x) for x in match.groups())


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _load_json_bytes(data: bytes, *, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationAuthorityError(f"INVALID_JSON:{label}:{exc}") from exc


def _legacy_identity(root: Path) -> dict[str, str]:
    path = root / LEGACY_NAME
    raw = _read_bytes(path)
    payload = _load_json_bytes(raw, label=LEGACY_NAME)
    if not isinstance(payload, dict) or payload.get("schema") != LEGACY_SCHEMA:
        raise PublicationAuthorityError("INVALID_LEGACY_PUBLICATION_SCHEMA")
    return {
        "path": LEGACY_NAME,
        "schema": LEGACY_SCHEMA,
        "sha256": _sha256(raw),
    }



def _legacy_records(root: Path) -> list[dict[str, Any]]:
    raw = _read_bytes(root / LEGACY_NAME)
    payload = _load_json_bytes(raw, label=LEGACY_NAME)
    if not isinstance(payload, dict) or payload.get("schema") != LEGACY_SCHEMA:
        raise PublicationAuthorityError("INVALID_LEGACY_PUBLICATION_SCHEMA")
    rows = payload.get("published_releases")
    if not isinstance(rows, list):
        raise PublicationAuthorityError("INVALID_LEGACY_PUBLICATION_RECORDS")
    result: list[dict[str, Any]] = []
    previous: tuple[int, int, int] | None = None
    seen_tags: set[str] = set()
    seen_versions: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise PublicationAuthorityError(f"INVALID_LEGACY_PUBLICATION_RECORD:{index}")
        tag = row.get("release_tag")
        version = row.get("version")
        if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
            raise PublicationAuthorityError(f"INVALID_LEGACY_PUBLICATION_TAG:{index}")
        if version != tag.removeprefix("Elpis"):
            raise PublicationAuthorityError(f"LEGACY_PUBLICATION_VERSION_MISMATCH:{tag}")
        if tag in seen_tags or version in seen_versions:
            raise PublicationAuthorityError(f"LEGACY_PUBLICATION_DUPLICATE:{tag}")
        key = _semver_key(tag)
        if previous is not None and key <= previous:
            raise PublicationAuthorityError(f"LEGACY_PUBLICATION_ORDER_INVALID:{tag}")
        previous = key
        seen_tags.add(tag)
        seen_versions.add(version)
        result.append(row)
    return result

def _failed_tags(root: Path) -> set[str]:
    raw = _read_bytes(root / FAILED_NAME)
    payload = _load_json_bytes(raw, label=FAILED_NAME)
    if not isinstance(payload, dict) or payload.get("schema") != "elpis.failed-releases.v1":
        raise PublicationAuthorityError("INVALID_FAILED_RELEASES_SCHEMA")
    rows = payload.get("failed_releases")
    if not isinstance(rows, list):
        raise PublicationAuthorityError("INVALID_FAILED_RELEASES_RECORDS")
    result: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise PublicationAuthorityError(f"INVALID_FAILED_RELEASE_RECORD:{index}")
        tag = row.get("release_tag")
        if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
            raise PublicationAuthorityError(f"INVALID_FAILED_RELEASE_TAG:{index}")
        if tag in result:
            raise PublicationAuthorityError(f"DUPLICATE_FAILED_RELEASE:{tag}")
        result.add(tag)
    return result


def _tag_identity(root: Path, tag: str) -> dict[str, str]:
    _semver_key(tag)
    ref = f"refs/tags/{tag}"
    tag_object = str(_git(root, "rev-parse", "--verify", ref))
    if not HEX_RE.fullmatch(tag_object):
        raise PublicationAuthorityError(f"TAG_OBJECT_ID_INVALID:{tag}")
    tag_type = str(_git(root, "cat-file", "-t", tag_object))
    if tag_type != "tag":
        raise PublicationAuthorityError(f"ANNOTATED_TAG_REQUIRED:{tag}:{tag_type}")
    peeled = str(_git(root, "rev-parse", "--verify", f"{ref}^{{commit}}"))
    if not HEX_RE.fullmatch(peeled):
        raise PublicationAuthorityError(f"PEELED_COMMIT_ID_INVALID:{tag}")
    peeled_type = str(_git(root, "cat-file", "-t", peeled))
    if peeled_type != "commit":
        raise PublicationAuthorityError(f"PEELED_COMMIT_TYPE_INVALID:{tag}:{peeled_type}")
    return {
        "tag_object": tag_object,
        "tag_object_type": tag_type,
        "peeled_commit": peeled,
        "peeled_object_type": peeled_type,
    }


def _manifest_identity(root: Path, tag: str, peeled: str) -> dict[str, str]:
    rel = f"manifests/{tag}.RELEASE_MANIFEST.json"
    tagged = bytes(_git(root, "show", f"{peeled}:{rel}", text=False))
    payload = _load_json_bytes(tagged, label=f"{peeled}:{rel}")
    version = tag.removeprefix("Elpis")
    if not isinstance(payload, dict):
        raise PublicationAuthorityError(f"TAGGED_MANIFEST_NOT_OBJECT:{tag}")
    if payload.get("release_tag") != tag or payload.get("version") != version:
        raise PublicationAuthorityError(f"TAGGED_MANIFEST_IDENTITY_MISMATCH:{tag}")

    checkout = root / rel
    checkout_bytes = _read_bytes(checkout)
    if checkout_bytes != tagged:
        raise PublicationAuthorityError(f"CHECKOUT_MANIFEST_DIFFERS_FROM_TAGGED_BYTES:{tag}")

    return {
        "manifest_path": rel,
        "manifest_sha256": _sha256(tagged),
    }


def _validate_action(name: str, value: Any, *, peeled: str) -> dict[str, Any]:
    if name not in REQUIRED_ACTIONS:
        raise PublicationAuthorityError(f"UNEXPECTED_ACTION_WITNESS:{name}")
    if not isinstance(value, dict):
        raise PublicationAuthorityError(f"ACTION_WITNESS_NOT_OBJECT:{name}")
    if set(value) != {"conclusion", "event", "head_sha", "run_id", "workflow"}:
        raise PublicationAuthorityError(f"ACTION_WITNESS_FIELDS_INVALID:{name}")
    workflow, event = REQUIRED_ACTIONS[name]
    if value.get("workflow") != workflow:
        raise PublicationAuthorityError(f"ACTION_WORKFLOW_MISMATCH:{name}")
    if value.get("event") != event:
        raise PublicationAuthorityError(f"ACTION_EVENT_MISMATCH:{name}")
    if value.get("head_sha") != peeled:
        raise PublicationAuthorityError(f"ACTION_HEAD_SHA_MISMATCH:{name}")
    if value.get("conclusion") != "success":
        raise PublicationAuthorityError(f"ACTION_NOT_SUCCESS:{name}")
    run_id = value.get("run_id")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise PublicationAuthorityError(f"ACTION_RUN_ID_INVALID:{name}")
    return dict(value)


def _validate_external_receipt(receipt: Any, *, tag: str, peeled: str) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise PublicationAuthorityError("PUBLICATION_RECEIPT_NOT_OBJECT")
    if set(receipt) != {"github_actions", "github_release", "pypi", "release_tag"}:
        raise PublicationAuthorityError("PUBLICATION_RECEIPT_FIELDS_INVALID")
    if receipt.get("release_tag") != tag:
        raise PublicationAuthorityError("PUBLICATION_RECEIPT_TAG_MISMATCH")

    gh = receipt.get("github_release")
    if not isinstance(gh, dict) or set(gh) != {
        "published_at", "release_id", "repository", "tag_name"
    }:
        raise PublicationAuthorityError("GITHUB_RELEASE_WITNESS_FIELDS_INVALID")
    if gh.get("repository") != "abraxis717/Elpis":
        raise PublicationAuthorityError("GITHUB_RELEASE_REPOSITORY_MISMATCH")
    if gh.get("tag_name") != tag:
        raise PublicationAuthorityError("GITHUB_RELEASE_TAG_MISMATCH")
    if not isinstance(gh.get("release_id"), int) or isinstance(gh.get("release_id"), bool) or gh["release_id"] <= 0:
        raise PublicationAuthorityError("GITHUB_RELEASE_ID_INVALID")
    if not isinstance(gh.get("published_at"), str) or not gh["published_at"]:
        raise PublicationAuthorityError("GITHUB_RELEASE_PUBLISHED_AT_INVALID")

    actions = receipt.get("github_actions")
    if not isinstance(actions, dict) or set(actions) != set(REQUIRED_ACTIONS):
        raise PublicationAuthorityError("GITHUB_ACTION_WITNESS_SET_INVALID")
    clean_actions = {
        name: _validate_action(name, actions[name], peeled=peeled)
        for name in sorted(actions)
    }
    ids = [item["run_id"] for item in clean_actions.values()]
    if len(ids) != len(set(ids)):
        raise PublicationAuthorityError("GITHUB_ACTION_RUN_ID_DUPLICATE")

    pypi = receipt.get("pypi")
    if not isinstance(pypi, dict) or set(pypi) != {"files", "project", "version"}:
        raise PublicationAuthorityError("PYPI_WITNESS_FIELDS_INVALID")
    if pypi.get("project") != "elpisai":
        raise PublicationAuthorityError("PYPI_PROJECT_MISMATCH")
    if pypi.get("version") != tag.removeprefix("Elpis"):
        raise PublicationAuthorityError("PYPI_VERSION_MISMATCH")
    files = pypi.get("files")
    if not isinstance(files, list) or len(files) != 2:
        raise PublicationAuthorityError("PYPI_EXPECTED_EXACT_WHEEL_AND_SDIST")
    clean_files: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    types: set[str] = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {
            "filename", "packagetype", "sha256", "upload_time_iso_8601", "yanked"
        }:
            raise PublicationAuthorityError(f"PYPI_FILE_FIELDS_INVALID:{index}")
        filename = item.get("filename")
        package_type = item.get("packagetype")
        digest = item.get("sha256")
        uploaded = item.get("upload_time_iso_8601")
        yanked = item.get("yanked")
        if not isinstance(filename, str) or not filename or filename in seen_names:
            raise PublicationAuthorityError(f"PYPI_FILENAME_INVALID:{index}")
        if package_type not in {"bdist_wheel", "sdist"}:
            raise PublicationAuthorityError(f"PYPI_PACKAGE_TYPE_INVALID:{filename}")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise PublicationAuthorityError(f"PYPI_SHA256_INVALID:{filename}")
        if not isinstance(uploaded, str) or not uploaded:
            raise PublicationAuthorityError(f"PYPI_UPLOAD_TIME_INVALID:{filename}")
        if yanked is not False:
            raise PublicationAuthorityError(f"PYPI_FILE_YANKED:{filename}")
        seen_names.add(filename)
        types.add(package_type)
        clean_files.append(dict(item))
    if types != {"bdist_wheel", "sdist"}:
        raise PublicationAuthorityError("PYPI_EXPECTED_WHEEL_AND_SDIST_TYPES")
    clean_files.sort(key=lambda item: item["filename"])

    return {
        "github_actions": clean_actions,
        "github_release": dict(gh),
        "pypi": {
            "files": clean_files,
            "project": "elpisai",
            "version": tag.removeprefix("Elpis"),
        },
        "release_tag": tag,
    }


def expected_entry(root: Path, tag: str, receipt: Any) -> dict[str, Any]:
    if tag in _failed_tags(root):
        raise PublicationAuthorityError(f"PUBLICATION_ASSERTION_IS_FAILED:{tag}")
    tag_id = _tag_identity(root, tag)
    manifest_id = _manifest_identity(root, tag, tag_id["peeled_commit"])
    external = _validate_external_receipt(
        receipt, tag=tag, peeled=tag_id["peeled_commit"]
    )
    return {
        "github_actions": external["github_actions"],
        "github_release": external["github_release"],
        "manifest_path": manifest_id["manifest_path"],
        "manifest_sha256": manifest_id["manifest_sha256"],
        "peeled_commit": tag_id["peeled_commit"],
        "peeled_object_type": "commit",
        "pypi": external["pypi"],
        "release_tag": tag,
        "tag_object": tag_id["tag_object"],
        "tag_object_type": "tag",
        "version": tag.removeprefix("Elpis"),
    }


def empty_registry(root: Path) -> dict[str, Any]:
    return {
        "legacy_publication_history": _legacy_identity(root),
        "publication_assertions": [],
        "publication_fact_authority": PUBLICATION_FACT_AUTHORITY,
        "release_identity_authority": RELEASE_IDENTITY_AUTHORITY,
        "schema": SCHEMA,
    }


def load_registry(root: Path, *, allow_missing: bool = False) -> dict[str, Any]:
    path = root / REGISTRY_NAME
    if not path.exists():
        if allow_missing:
            return empty_registry(root)
        raise PublicationAuthorityError(f"PUBLICATION_ASSERTIONS_MISSING:{REGISTRY_NAME}")
    payload = _load_json_bytes(_read_bytes(path), label=REGISTRY_NAME)
    if not isinstance(payload, dict):
        raise PublicationAuthorityError("PUBLICATION_ASSERTIONS_NOT_OBJECT")
    return payload


def _registry_structure_errors(root: Path, data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["PUBLICATION_ASSERTIONS_NOT_OBJECT"]
    if set(data) != TOP_LEVEL_KEYS:
        errors.append("PUBLICATION_ASSERTIONS_TOP_LEVEL_FIELDS_INVALID")
    if data.get("schema") != SCHEMA:
        errors.append("PUBLICATION_ASSERTIONS_SCHEMA_INVALID")
    if data.get("release_identity_authority") != RELEASE_IDENTITY_AUTHORITY:
        errors.append("RELEASE_IDENTITY_AUTHORITY_INVALID")
    if data.get("publication_fact_authority") != PUBLICATION_FACT_AUTHORITY:
        errors.append("PUBLICATION_FACT_AUTHORITY_INVALID")
    try:
        expected_legacy = _legacy_identity(root)
    except PublicationAuthorityError as exc:
        errors.append(str(exc))
        expected_legacy = None
    legacy = data.get("legacy_publication_history")
    if legacy != expected_legacy:
        errors.append("LEGACY_PUBLICATION_HISTORY_IDENTITY_MISMATCH")
    if not isinstance(data.get("publication_assertions"), list):
        errors.append("PUBLICATION_ASSERTIONS_RECORDS_INVALID")
    return errors


def validation_errors(root: Path, payload: Any | None = None) -> list[str]:
    try:
        data = load_registry(root) if payload is None else payload
    except PublicationAuthorityError as exc:
        return [str(exc)]

    errors = _registry_structure_errors(root, data)
    records = data.get("publication_assertions") if isinstance(data, dict) else None
    if not isinstance(records, list):
        return errors

    try:
        failed = _failed_tags(root)
    except PublicationAuthorityError as exc:
        return errors + [str(exc)]

    try:
        legacy_rows = _legacy_records(root)
    except PublicationAuthorityError as exc:
        return errors + [str(exc)]
    legacy_tags = {row["release_tag"] for row in legacy_rows}
    legacy_versions = {row["version"] for row in legacy_rows}

    seen_tags: set[str] = set()
    seen_versions: set[str] = set()
    seen_release_ids: set[int] = set()
    seen_run_ids: set[int] = set()
    previous: tuple[int, int, int] | None = (
        _semver_key(legacy_rows[-1]["release_tag"]) if legacy_rows else None
    )

    for index, item in enumerate(records):
        if not isinstance(item, dict):
            errors.append(f"PUBLICATION_ASSERTION_RECORD_INVALID:{index}")
            continue
        if set(item) != ENTRY_KEYS:
            errors.append(f"PUBLICATION_ASSERTION_FIELDS_INVALID:{index}")
            continue
        tag = item.get("release_tag")
        version = item.get("version")
        if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
            errors.append(f"PUBLICATION_ASSERTION_TAG_INVALID:{index}")
            continue
        if version != tag.removeprefix("Elpis"):
            errors.append(f"PUBLICATION_ASSERTION_VERSION_MISMATCH:{tag}")
        if tag in legacy_tags or version in legacy_versions:
            errors.append(f"PUBLICATION_ASSERTION_DUPLICATES_LEGACY:{tag}")
        if tag in seen_tags or version in seen_versions:
            errors.append(f"PUBLICATION_ASSERTION_DUPLICATE:{tag}")
        seen_tags.add(tag)
        if isinstance(version, str):
            seen_versions.add(version)
        key = _semver_key(tag)
        if previous is not None and key <= previous:
            errors.append(f"PUBLICATION_ASSERTION_ORDER_INVALID:{tag}")
        previous = key
        if tag in failed:
            errors.append(f"PUBLICATION_ASSERTION_IS_FAILED:{tag}")

        try:
            tag_id = _tag_identity(root, tag)
        except PublicationAuthorityError as exc:
            errors.append(str(exc))
            continue
        if item.get("tag_object_type") != "tag":
            errors.append(f"PUBLICATION_TAG_OBJECT_TYPE_FIELD_INVALID:{tag}")
        if item.get("tag_object") != tag_id["tag_object"]:
            errors.append(f"PUBLICATION_TAG_OBJECT_MISMATCH:{tag}")
        if item.get("peeled_object_type") != "commit":
            errors.append(f"PUBLICATION_PEELED_TYPE_FIELD_INVALID:{tag}")
        if item.get("peeled_commit") != tag_id["peeled_commit"]:
            errors.append(f"PUBLICATION_PEELED_COMMIT_MISMATCH:{tag}")

        try:
            manifest_id = _manifest_identity(root, tag, tag_id["peeled_commit"])
        except PublicationAuthorityError as exc:
            errors.append(str(exc))
            continue
        if item.get("manifest_path") != manifest_id["manifest_path"]:
            errors.append(f"PUBLICATION_MANIFEST_PATH_MISMATCH:{tag}")
        if item.get("manifest_sha256") != manifest_id["manifest_sha256"]:
            errors.append(f"PUBLICATION_TAGGED_MANIFEST_SHA256_MISMATCH:{tag}")

        receipt = {
            "github_actions": item.get("github_actions"),
            "github_release": item.get("github_release"),
            "pypi": item.get("pypi"),
            "release_tag": tag,
        }
        try:
            external = _validate_external_receipt(
                receipt, tag=tag, peeled=tag_id["peeled_commit"]
            )
        except PublicationAuthorityError as exc:
            errors.append(str(exc))
            continue
        release_id = external["github_release"]["release_id"]
        if release_id in seen_release_ids:
            errors.append(f"GITHUB_RELEASE_ID_REUSED:{release_id}")
        seen_release_ids.add(release_id)
        for name, action in external["github_actions"].items():
            run_id = action["run_id"]
            if run_id in seen_run_ids:
                errors.append(f"GITHUB_ACTION_RUN_ID_REUSED:{run_id}:{name}")
            seen_run_ids.add(run_id)

    return errors



def gitless_validation_errors(
    root: Path,
    payload: Any | None = None,
) -> list[str]:
    """Validate durable publication facts without requiring Git objects.

    This mode is for exported release trees. It proves registry structure,
    frozen-v1 binding, manifest-byte identity present in the export, receipt
    coherence, ordering, failed-release exclusion, and witness uniqueness.

    It deliberately does not claim annotated-tag/tree re-proof; Git checkouts
    use validation_errors() for that stronger proof.
    """
    try:
        data = load_registry(root) if payload is None else payload
    except PublicationAuthorityError as exc:
        return [str(exc)]

    errors = _registry_structure_errors(root, data)
    records = (
        data.get("publication_assertions")
        if isinstance(data, dict)
        else None
    )
    if not isinstance(records, list):
        return errors

    try:
        failed = _failed_tags(root)
    except PublicationAuthorityError as exc:
        return errors + [str(exc)]

    try:
        legacy_rows = _legacy_records(root)
    except PublicationAuthorityError as exc:
        return errors + [str(exc)]

    legacy_tags = {
        row["release_tag"]
        for row in legacy_rows
    }
    legacy_versions = {
        row["version"]
        for row in legacy_rows
    }

    seen_tags: set[str] = set()
    seen_versions: set[str] = set()
    seen_release_ids: set[int] = set()
    seen_run_ids: set[int] = set()

    previous: tuple[int, int, int] | None = (
        _semver_key(legacy_rows[-1]["release_tag"])
        if legacy_rows
        else None
    )

    for index, item in enumerate(records):
        if not isinstance(item, dict):
            errors.append(
                f"PUBLICATION_ASSERTION_RECORD_INVALID:{index}"
            )
            continue

        if set(item) != ENTRY_KEYS:
            errors.append(
                f"PUBLICATION_ASSERTION_FIELDS_INVALID:{index}"
            )
            continue

        tag = item.get("release_tag")
        version = item.get("version")

        if (
            not isinstance(tag, str)
            or TAG_RE.fullmatch(tag) is None
        ):
            errors.append(
                f"PUBLICATION_ASSERTION_TAG_INVALID:{index}"
            )
            continue

        if version != tag.removeprefix("Elpis"):
            errors.append(
                f"PUBLICATION_ASSERTION_VERSION_MISMATCH:{tag}"
            )

        if tag in legacy_tags or version in legacy_versions:
            errors.append(
                f"PUBLICATION_ASSERTION_DUPLICATES_LEGACY:{tag}"
            )

        if tag in seen_tags or version in seen_versions:
            errors.append(
                f"PUBLICATION_ASSERTION_DUPLICATE:{tag}"
            )

        seen_tags.add(tag)
        if isinstance(version, str):
            seen_versions.add(version)

        key = _semver_key(tag)
        if previous is not None and key <= previous:
            errors.append(
                f"PUBLICATION_ASSERTION_ORDER_INVALID:{tag}"
            )
        previous = key

        if tag in failed:
            errors.append(
                f"PUBLICATION_ASSERTION_IS_FAILED:{tag}"
            )

        tag_object = item.get("tag_object")
        if item.get("tag_object_type") != "tag":
            errors.append(
                f"PUBLICATION_TAG_OBJECT_TYPE_FIELD_INVALID:{tag}"
            )
        if (
            not isinstance(tag_object, str)
            or HEX_RE.fullmatch(tag_object) is None
        ):
            errors.append(
                f"PUBLICATION_TAG_OBJECT_ID_FIELD_INVALID:{tag}"
            )

        peeled = item.get("peeled_commit")
        if item.get("peeled_object_type") != "commit":
            errors.append(
                f"PUBLICATION_PEELED_TYPE_FIELD_INVALID:{tag}"
            )
        if (
            not isinstance(peeled, str)
            or HEX_RE.fullmatch(peeled) is None
        ):
            errors.append(
                f"PUBLICATION_PEELED_COMMIT_FIELD_INVALID:{tag}"
            )

        expected_path = (
            f"manifests/{tag}.RELEASE_MANIFEST.json"
        )

        if item.get("manifest_path") != expected_path:
            errors.append(
                f"PUBLICATION_MANIFEST_PATH_MISMATCH:{tag}"
            )
        else:
            manifest = root / expected_path

            if not manifest.is_file():
                errors.append(
                    f"PUBLICATION_MANIFEST_MISSING:{tag}"
                )
            else:
                try:
                    raw = _read_bytes(manifest)
                    manifest_payload = _load_json_bytes(
                        raw,
                        label=expected_path,
                    )
                except PublicationAuthorityError as exc:
                    errors.append(str(exc))
                else:
                    if (
                        not isinstance(manifest_payload, dict)
                        or manifest_payload.get("release_tag") != tag
                        or manifest_payload.get("version") != version
                    ):
                        errors.append(
                            "PUBLICATION_CHECKOUT_MANIFEST_"
                            f"IDENTITY_MISMATCH:{tag}"
                        )

                    digest = item.get("manifest_sha256")

                    if (
                        not isinstance(digest, str)
                        or SHA256_RE.fullmatch(digest) is None
                    ):
                        errors.append(
                            "PUBLICATION_MANIFEST_SHA256_"
                            f"FIELD_INVALID:{tag}"
                        )
                    elif digest != _sha256(raw):
                        errors.append(
                            "PUBLICATION_CHECKOUT_MANIFEST_"
                            f"SHA256_MISMATCH:{tag}"
                        )

        if (
            not isinstance(peeled, str)
            or HEX_RE.fullmatch(peeled) is None
        ):
            continue

        receipt = {
            "github_actions": item.get("github_actions"),
            "github_release": item.get("github_release"),
            "pypi": item.get("pypi"),
            "release_tag": tag,
        }

        try:
            external = _validate_external_receipt(
                receipt,
                tag=tag,
                peeled=peeled,
            )
        except PublicationAuthorityError as exc:
            errors.append(str(exc))
            continue

        release_id = external[
            "github_release"
        ]["release_id"]

        if release_id in seen_release_ids:
            errors.append(
                f"GITHUB_RELEASE_ID_REUSED:{release_id}"
            )
        seen_release_ids.add(release_id)

        for name, action in external[
            "github_actions"
        ].items():
            run_id = action["run_id"]
            if run_id in seen_run_ids:
                errors.append(
                    "GITHUB_ACTION_RUN_ID_REUSED:"
                    f"{run_id}:{name}"
                )
            seen_run_ids.add(run_id)

    return errors

@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
            temp = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        temp = None
        _fsync_directory(path.parent)
    finally:
        if temp is not None:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass


def append_receipt(root: Path, receipt_path: Path) -> dict[str, Any]:
    receipt = _load_json_bytes(_read_bytes(receipt_path), label=str(receipt_path))
    if not isinstance(receipt, dict) or not isinstance(receipt.get("release_tag"), str):
        raise PublicationAuthorityError("PUBLICATION_RECEIPT_TAG_INVALID")
    tag = receipt["release_tag"]
    _semver_key(tag)

    registry_path = root / REGISTRY_NAME
    lock_raw = Path(str(_git(root, "rev-parse", "--git-path", "elpis-publication-assertions.lock")))
    lock_path = lock_raw if lock_raw.is_absolute() else root / lock_raw
    with _exclusive_lock(lock_path):
        original_bytes = registry_path.read_bytes() if registry_path.exists() else None
        data = load_registry(root, allow_missing=True)
        pre_errors = _registry_structure_errors(root, data)
        if pre_errors:
            raise PublicationAuthorityError(
                "PUBLICATION_ASSERTIONS_PREAPPEND_NONPASS:" + "|".join(pre_errors)
            )
        full_errors = validation_errors(root, data)
        if full_errors:
            raise PublicationAuthorityError(
                "PUBLICATION_ASSERTIONS_PREAPPEND_NONPASS:" + "|".join(full_errors)
            )
        records = data["publication_assertions"]
        if any(row.get("release_tag") == tag for row in records):
            raise PublicationAuthorityError(f"PUBLICATION_ASSERTION_DUPLICATE_TAG:{tag}")
        if records and _semver_key(tag) <= _semver_key(records[-1]["release_tag"]):
            raise PublicationAuthorityError(f"PUBLICATION_ASSERTION_NOT_MONOTONIC:{tag}")

        entry = expected_entry(root, tag, receipt)
        candidate = dict(data)
        candidate["publication_assertions"] = [*records, entry]
        errors = validation_errors(root, candidate)
        if errors:
            raise PublicationAuthorityError(
                "PUBLICATION_ASSERTIONS_CANDIDATE_NONPASS:" + "|".join(errors)
            )

        current_bytes = registry_path.read_bytes() if registry_path.exists() else None
        if current_bytes != original_bytes:
            raise PublicationAuthorityError("PUBLICATION_ASSERTIONS_COMPARE_AND_SWAP_CONFLICT")
        _atomic_replace(registry_path, _pretty_bytes(candidate))
        return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--check-gitless", action="store_true")
    group.add_argument("--append-receipt", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.check or args.check_gitless:
        errors = (
            validation_errors(root)
            if args.check
            else gitless_validation_errors(root)
        )
        if errors:
            for error in errors:
                print(error)
            return 1
        count = len(
            load_registry(root)["publication_assertions"]
        )
        mode = (
            "git-bound"
            if args.check
            else "gitless-structural"
        )
        print(
            "PASS publication-assertions v2 validates "
            f"{count} explicit publication assertion(s) "
            f"mode={mode}"
        )
        return 0

    try:
        entry = append_receipt(root, args.append_receipt.resolve())
    except (OSError, PublicationAuthorityError) as exc:
        print(str(exc))
        return 1
    print("APPENDED publication assertion " + json.dumps(entry, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
