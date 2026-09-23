#!/usr/bin/env python3
"""Execute the committed native inference pytest authority and prove the exact run set."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "tools/inference_native_locus_v1.json"
SCHEMA = "elpis.inference-native-execution.v1"


def digest_lines(values):
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def junit_totals(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag.endswith("testsuite") else list(root)
    return {
        key: sum(int(s.attrib.get(key, "0")) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }


class ExecutionRecorder:
    def __init__(self):
        self.nodeids = []

    def pytest_runtest_logstart(self, nodeid, location):
        self.nodeids.append(nodeid)


def validate_execution(authority, observed_nodeids, totals):
    expected = tuple(authority["nodeids"])
    observed = tuple(observed_nodeids)
    if observed != expected:
        missing = tuple(node for node in expected if node not in set(observed))
        extra = tuple(node for node in observed if node not in set(expected))
        raise ValueError(
            "NATIVE_EXECUTED_NODE_SET_MISMATCH:"
            f"expected={len(expected)}:observed={len(observed)}:"
            f"missing={missing[:5]!r}:extra={extra[:5]!r}"
        )
    observed_sha = digest_lines(observed)
    if observed_sha != authority["nodeids_sha256"]:
        raise ValueError(
            "NATIVE_EXECUTED_NODE_SHA256_MISMATCH:"
            f"{observed_sha}:{authority['nodeids_sha256']}"
        )
    expected_totals = {
        "tests": authority["count"],
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    if totals != expected_totals:
        raise ValueError(
            "NATIVE_EXECUTION_JUNIT_NONPASS:"
            + repr({"observed": totals, "expected": expected_totals})
        )
    return observed_sha


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--section", choices=("provider", "locus"), required=True)
    ap.add_argument("--junitxml", type=Path, required=True)
    ap.add_argument("--record", type=Path, required=True)
    args = ap.parse_args(argv)

    payload = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    authority = payload[args.section]
    recorder = ExecutionRecorder()
    pytest_argv = [
        "-q",
        "-p", "no:cacheprovider",
        f"--junitxml={args.junitxml}",
        *authority["paths"],
    ]
    rc = int(pytest.main(pytest_argv, plugins=[recorder]))
    if not args.junitxml.is_file():
        print("NATIVE_EXECUTION_JUNIT_MISSING", file=sys.stderr)
        return 1

    totals = junit_totals(args.junitxml)
    try:
        executed_sha = validate_execution(authority, recorder.nodeids, totals)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if rc != 0:
        print(f"NATIVE_EXECUTION_PYTEST_NONZERO:{rc}", file=sys.stderr)
        return 1

    record = {
        "schema": SCHEMA,
        "section": args.section,
        "authority_count": authority["count"],
        "authority_nodeids_sha256": authority["nodeids_sha256"],
        "executed_count": len(recorder.nodeids),
        "executed_nodeids": recorder.nodeids,
        "executed_nodeids_sha256": executed_sha,
        "junit": totals,
        "pytest_exit_code": rc,
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS_NATIVE_EXECUTED_EXACT_SET "
        f"section={args.section} count={len(recorder.nodeids)} "
        f"nodeids_sha256={executed_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
