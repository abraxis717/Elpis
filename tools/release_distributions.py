#!/usr/bin/env python3
"""Build deterministic release distributions and verify byte authority."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


AUTHORITY_SCHEMA = "elpis.distribution-artifacts.v1"
BEGIN = "<!-- ELPIS_DISTRIBUTION_ARTIFACTS_V1\n"
END = "\n-->"


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def source_date_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "")
    if not raw.isdigit() or int(raw) <= 0:
        fail("SOURCE_DATE_EPOCH_REQUIRED")
    return int(raw)


def canonicalize_sdist(path: Path, epoch: int) -> None:
    members = []
    payloads = {}

    with tarfile.open(path, "r:gz") as source:
        for member in source.getmembers():
            members.append(copy.copy(member))
            if member.isfile():
                stream = source.extractfile(member)
                if stream is None:
                    fail(
                        "SDIST_MEMBER_UNREADABLE:"
                        + member.name
                    )
                payloads[member.name] = stream.read()

    temporary = path.with_name(path.name + ".canonical")

    with temporary.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=epoch,
        ) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as target:
                for member in sorted(
                    members,
                    key=lambda item: item.name,
                ):
                    member.uid = 0
                    member.gid = 0
                    member.uname = ""
                    member.gname = ""
                    member.mtime = epoch
                    member.pax_headers = {}

                    data = None
                    if member.isfile():
                        body = payloads[member.name]
                        member.size = len(body)
                        data = io.BytesIO(body)

                    target.addfile(member, data)

    os.replace(temporary, path)


def identities(directory: Path, version: str):
    wheel = sorted(
        directory.glob(f"elpisai-{version}-*.whl")
    )
    sdist = sorted(
        directory.glob(f"elpisai-{version}.tar.gz")
    )

    if len(wheel) != 1:
        fail("DISTRIBUTION_WHEEL_CARDINALITY")
    if len(sdist) != 1:
        fail("DISTRIBUTION_SDIST_CARDINALITY")

    return sorted(
        [
            {
                "filename": wheel[0].name,
                "packagetype": "bdist_wheel",
                "sha256": sha256(wheel[0]),
            },
            {
                "filename": sdist[0].name,
                "packagetype": "sdist",
                "sha256": sha256(sdist[0]),
            },
        ],
        key=lambda item: item["filename"],
    )


def extract_authority(body: str):
    if body.count(BEGIN) != 1 or body.count(END) != 1:
        fail("RELEASE_ARTIFACT_AUTHORITY_MARKER_INVALID")

    prefix, remainder = body.split(BEGIN, 1)
    raw, suffix = remainder.split(END, 1)

    if BEGIN in prefix or BEGIN in suffix or END in suffix:
        fail("RELEASE_ARTIFACT_AUTHORITY_MARKER_INVALID")

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(
            "RELEASE_ARTIFACT_AUTHORITY_JSON_INVALID:"
            + str(exc)
        )

    if not isinstance(value, dict):
        fail("RELEASE_ARTIFACT_AUTHORITY_INVALID")

    if value.get("schema") != AUTHORITY_SCHEMA:
        fail("RELEASE_ARTIFACT_AUTHORITY_SCHEMA_INVALID")

    return value


def build(directory: Path, version: str) -> None:
    epoch = source_date_epoch()
    directory.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(directory),
        ]
    )
    if proc.returncode:
        raise SystemExit(proc.returncode)

    sdists = sorted(
        directory.glob(f"elpisai-{version}.tar.gz")
    )
    if len(sdists) != 1:
        fail("DISTRIBUTION_SDIST_CARDINALITY")

    canonicalize_sdist(sdists[0], epoch)

    # Force cardinality/shape validation after canonicalization.
    identities(directory, version)


def verify(
    directory: Path,
    version: str,
    body_path: Path,
) -> None:
    authority = extract_authority(
        body_path.read_text(encoding="utf-8")
    )

    if authority.get("version") != version:
        fail("RELEASE_ARTIFACT_AUTHORITY_VERSION_MISMATCH")

    expected = authority.get("files")
    if not isinstance(expected, list):
        fail("RELEASE_ARTIFACT_AUTHORITY_FILES_INVALID")

    observed = identities(directory, version)

    if expected != observed:
        print(
            "EXPECTED=" + canonical(expected),
            file=sys.stderr,
        )
        print(
            "OBSERVED=" + canonical(observed),
            file=sys.stderr,
        )
        fail("RELEASE_ARTIFACT_AUTHORITY_MISMATCH")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    build_parser = sub.add_parser("build")
    build_parser.add_argument(
        "--outdir",
        type=Path,
        required=True,
    )
    build_parser.add_argument(
        "--version",
        required=True,
    )

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument(
        "--dist",
        type=Path,
        required=True,
    )
    verify_parser.add_argument(
        "--version",
        required=True,
    )
    verify_parser.add_argument(
        "--release-body",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    if args.command == "build":
        build(args.outdir, args.version)
        return 0

    verify(
        args.dist,
        args.version,
        args.release_body,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
