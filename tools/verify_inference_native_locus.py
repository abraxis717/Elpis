#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools/inference_native_locus_v1.json"
SCHEMA = "elpis.inference-native-locus.v1"

PROVIDER = ("tests/test_inference_file_assets_r0.py",)
LOCUS = (
    "tests/test_inference_file_assets_r0.py",
    "tests/test_inference_rows_r0.py",
    "tests/test_inference_experts_r0.py",
    "tests/test_inference_neural_r0.py",
    "tests/test_inference_prefetch_r0.py",
    "tests/test_inference_runtime_r3.py",
    "tests/test_inference_speculative_r0.py",
    "runtime/R3/tests/",
)


def digest_lines(values):
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def selected_sources():
    result = set()
    for rel in LOCUS:
        path = ROOT / rel
        if path.is_dir():
            result.update(p for p in path.rglob("*.py") if p.is_file())
        else:
            result.add(path)
    conftest = ROOT / "tests/conftest.py"
    if conftest.is_file():
        result.add(conftest)
    return tuple(sorted(result))


def source_digests():
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in selected_sources()
    }


def collect(paths):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    collector = r"""
import json
import pytest
import sys

class Collector:
    def __init__(self):
        self.nodeids = ()

    def pytest_collection_finish(self, session):
        self.nodeids = tuple(item.nodeid for item in session.items)

plugin = Collector()
rc = pytest.main(
    ["--collect-only", "-q", "-p", "no:cacheprovider", *sys.argv[1:]],
    plugins=[plugin],
)
print("__ELPIS_NATIVE_NODEIDS__=" + json.dumps(list(plugin.nodeids)))
raise SystemExit(int(rc))
"""
    proc = subprocess.run(
        [sys.executable, "-c", collector, *paths],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode:
        raise SystemExit("NATIVE_LOCUS_COLLECTION_NONPASS:\n" + proc.stdout)
    prefix = "__ELPIS_NATIVE_NODEIDS__="
    records = [
        line[len(prefix):]
        for line in proc.stdout.splitlines()
        if line.startswith(prefix)
    ]
    if len(records) != 1:
        raise SystemExit(
            "NATIVE_LOCUS_COLLECTION_PROTOCOL_NONPASS:\n" + proc.stdout
        )
    try:
        nodeids = tuple(json.loads(records[0]))
    except (ValueError, TypeError) as exc:
        raise SystemExit(
            "NATIVE_LOCUS_COLLECTION_JSON_NONPASS:" + repr(exc)
        ) from exc
    if not nodeids or any(type(nodeid) is not str or "::" not in nodeid for nodeid in nodeids):
        raise SystemExit("NATIVE_LOCUS_COLLECTION_EMPTY_OR_INVALID")
    if len(nodeids) != len(set(nodeids)):
        raise SystemExit("NATIVE_LOCUS_COLLECTION_DUPLICATE_NODEID")
    return nodeids


def snapshot():
    provider = collect(PROVIDER)
    locus = collect(LOCUS)
    return {
        "schema": SCHEMA,
        "provider": {
            "paths": list(PROVIDER),
            "count": len(provider),
            "nodeids": list(provider),
            "nodeids_sha256": digest_lines(provider),
        },
        "locus": {
            "paths": list(LOCUS),
            "count": len(locus),
            "nodeids": list(locus),
            "nodeids_sha256": digest_lines(locus),
        },
        "sources": source_digests(),
    }


def errors(expected, observed):
    result = []
    if expected.get("schema") != SCHEMA:
        result.append("NATIVE_LOCUS_SCHEMA_INVALID")
    for name in ("provider", "locus"):
        a, b = expected.get(name), observed.get(name)
        if not isinstance(a, dict):
            result.append("NATIVE_LOCUS_SECTION_INVALID:" + name)
            continue
        for field in ("paths", "count", "nodeids", "nodeids_sha256"):
            if a.get(field) != b.get(field):
                result.append("NATIVE_LOCUS_MISMATCH:" + name + ":" + field)
    if expected.get("sources") != observed.get("sources"):
        result.append("NATIVE_LOCUS_TEST_SOURCE_DIGEST_MISMATCH")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    observed = snapshot()
    if args.write:
        MANIFEST.write_text(
            json.dumps(observed, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "WROTE_NATIVE_LOCUS "
            f"provider={observed['provider']['count']} "
            f"locus={observed['locus']['count']}"
        )
        return 0
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = errors(expected, observed)
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print(
        "PASS_NATIVE_LOCUS_EXACT "
        f"provider={observed['provider']['count']} "
        f"locus={observed['locus']['count']} "
        f"nodeids_sha256={observed['locus']['nodeids_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
