"""Verify an immutable byte copy, then explicitly materialize a private wheel.

R0 supports flat purelib/platlib wheels, not .data relocation or namespace
entry-point packages. No installer, dependency resolver, or plugin import runs.
"""
from __future__ import annotations

import base64
import configparser
import csv
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
import io
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile
import zipfile
import zlib

from ..structural_refinement import _sha256_hex
from .authority import WheelAuthority
from elpis.canonical_identity import content_digest
from .errors import WheelError
import mmap

MAX_WHEEL_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_DIRECTORY_BYTES = 4 * 1024 * 1024
CHUNK = 64 * 1024




@dataclass(frozen=True)
class Snapshot:
    work_root: Path
    package_root: Path
    members: tuple[tuple[str, str, int], ...]
    digest: str
    authority_digest: str


def remove_snapshot(root: Path) -> None:
    """Only call for a host-created private root; do not follow symlinks."""
    if not root.exists():
        return
    for directory, dirs, files in os.walk(root, followlinks=False):
        os.chmod(directory, 0o700)
        for name in files:
            path = Path(directory, name)
            if not path.is_symlink():
                os.chmod(path, 0o600)
    shutil.rmtree(root)


def _member_name(name: str) -> str:
    # Conservative portable spelling also rejects drive/ADS names, NUL,
    # backslashes, Unicode aliases, repeated separators and dot components.
    if not name or len(name) > 512 or not re.fullmatch(r"[A-Za-z0-9_+./-]+", name):
        raise WheelError("unsafe ZIP member spelling")
    parts = name.rstrip("/").split("/")
    if name.endswith("//"):
        raise WheelError("ambiguous trailing ZIP separators")
    if any(part in ("", ".", "..") or part.endswith(".") for part in parts):
        raise WheelError("unsafe ZIP member path")
    if any(part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))} for part in parts):
        raise WheelError("platform-aliased ZIP path")
    return "/".join(parts)


def _inventory(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if not 1 <= len(infos) <= MAX_MEMBERS:
        raise WheelError("ZIP member count limit")
    paths: dict[str, zipfile.ZipInfo] = {}
    aliases: dict[str, str] = {}
    total = 0
    for info in infos:
        if info.orig_filename != info.filename:
            raise WheelError("ambiguous ZIP filename")
        name = _member_name(info.filename)
        if name in paths:
            raise WheelError("duplicate ZIP member")
        parts = name.split("/")
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            alias = prefix.casefold()
            if alias in aliases and aliases[alias] != prefix:
                raise WheelError("case-aliased ZIP path")
            aliases[alias] = prefix
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or (kind == stat.S_IFDIR) != info.is_dir() and kind != 0:
            raise WheelError("ZIP symlink/special-file/type mismatch")
        if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise WheelError("unsupported ZIP encryption/compression")
        if info.file_size > MAX_MEMBER_BYTES or info.file_size < 0:
            raise WheelError("ZIP member size limit")
        if info.file_size > max(1, info.compress_size) * MAX_COMPRESSION_RATIO:
            raise WheelError("ZIP compression ratio limit")
        if info.is_dir() and info.file_size:
            raise WheelError("nonempty directory member")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise WheelError("ZIP aggregate size limit")
        if parts[0].endswith(".data") or name.endswith((".pth", ".pyc", ".pyo")):
            raise WheelError("R0 does not support relocation, .pth or bytecode files")
        paths[name] = info
    for name in paths:
        parts = name.split("/")
        for i in range(1, len(parts)):
            parent = paths.get("/".join(parts[:i]))
            if parent is not None and not parent.is_dir():
                raise WheelError("file/directory path collision")
    return paths


def _preflight_directory(stream: object, size: int) -> None:
    """Bound the central directory BEFORE zipfile allocates ZipInfo objects.

    R0's sub-4GiB/4096-member ceilings need neither ZIP64 nor split archives.
    Parse only fixed-size directory headers here; ZipFile performs subsequent
    local-header, CRC, overlap and decompression consistency checks.
    """
    stream.seek(max(0, size - 65557))
    tail = stream.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or offset + 22 > len(tail):
        raise WheelError("missing ZIP end directory")
    _, disk, directory_disk, disk_count, count, length, start, comment = struct.unpack_from("<4s4H2IH", tail, offset)
    end_position = size - len(tail) + offset
    if (disk or directory_disk or count != disk_count or not 1 <= count <= MAX_MEMBERS
            or length > MAX_DIRECTORY_BYTES or start + length != end_position
            or offset + 22 + comment != len(tail)):
        raise WheelError("ZIP directory count/size/layout limit (ZIP64/split unsupported)")
    stream.seek(start)
    consumed = 0
    actual_count = 0
    while consumed < length:
        header = stream.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise WheelError("malformed ZIP central directory")
        name_size, extra_size, comment_size = struct.unpack_from("<3H", header, 28)
        entry_size = 46 + name_size + extra_size + comment_size
        consumed += entry_size
        actual_count += 1
        if not 1 <= name_size <= 512 or consumed > length or actual_count > MAX_MEMBERS:
            raise WheelError("ZIP directory member count/path bound")
        stream.seek(entry_size - 46, os.SEEK_CUR)
    if actual_count != count:
        raise WheelError("ZIP directory member count mismatch")
    stream.seek(0)


def _metadata_bytes(archive: zipfile.ZipFile, paths: dict, name: str) -> bytes:
    info = paths.get(name)
    if info is None or info.is_dir() or info.file_size > MAX_METADATA_BYTES:
        raise WheelError("missing/oversized wheel metadata")
    return archive.read(info)


def _one_header(message: object, key: str) -> str:
    values = message.get_all(key, [])
    if len(values) != 1:
        raise WheelError(f"missing/duplicate {key} metadata")
    return str(values[0])


def _verify_metadata(archive: zipfile.ZipFile, paths: dict, authority: WheelAuthority) -> str:
    roots = {name.split("/")[0] for name in paths if any(p.endswith(".dist-info") for p in name.split("/"))}
    expected = f"{authority.distribution_name.replace('-', '_')}-{authority.distribution_version}.dist-info"
    if roots != {expected} or any(".dist-info/" in name[len(expected) + 1:] for name in paths):
        raise WheelError("wheel must contain exactly the expected dist-info identity")
    metadata = BytesParser(policy=default).parsebytes(_metadata_bytes(archive, paths, expected + "/METADATA"))
    if metadata.defects or _one_header(metadata, "Name") != authority.distribution_name or _one_header(metadata, "Version") != authority.distribution_version:
        raise WheelError("METADATA distribution identity mismatch")
    if _one_header(metadata, "Metadata-Version") not in ("2.1", "2.2", "2.3", "2.4"):
        raise WheelError("unsupported METADATA version")
    wheel = BytesParser(policy=default).parsebytes(_metadata_bytes(archive, paths, expected + "/WHEEL"))
    if wheel.defects or _one_header(wheel, "Wheel-Version") != "1.0" or _one_header(wheel, "Root-Is-Purelib") not in ("true", "false"):
        raise WheelError("invalid WHEEL metadata")
    tags = wheel.get_all("Tag", [])
    if not tags or any(not re.fullmatch(r"[A-Za-z0-9_.]+-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+", str(tag)) for tag in tags):
        raise WheelError("invalid WHEEL tags")
    parser = configparser.ConfigParser(interpolation=None, strict=True, delimiters=("=",))
    parser.optionxform = str
    try:
        parser.read_string(_metadata_bytes(archive, paths, expected + "/entry_points.txt").decode("utf-8"))
        if parser.defaults() or not parser.has_section(authority.entry_point_group):
            raise WheelError("missing entry-point group")
        value = parser.get(authority.entry_point_group, authority.driver_id, fallback=None)
        if value != authority.entry_point_value:
            raise WheelError("entry-point identity mismatch")
    except (configparser.Error, UnicodeError) as exc:
        raise WheelError("invalid/duplicate wheel entry points") from exc
    return expected


def _records(archive: zipfile.ZipFile, paths: dict, root: str) -> dict[str, tuple[str, int]]:
    record_name = root + "/RECORD"
    try:
        rows = csv.reader(io.StringIO(_metadata_bytes(archive, paths, record_name).decode("utf-8")), strict=True)
        records = {}
        for row in rows:
            if len(row) != 3:
                raise WheelError("malformed RECORD row")
            name, encoded, size = row
            if _member_name(name) != name or name in records or name not in paths or paths[name].is_dir():
                raise WheelError("duplicate/unknown RECORD path")
            if name == record_name:
                if encoded or size:
                    raise WheelError("RECORD self-hash must be empty in R0")
                records[name] = ("", paths[name].file_size)
                continue
            if not re.fullmatch(r"sha256=[A-Za-z0-9_-]{43}", encoded):
                raise WheelError("RECORD requires unpadded SHA-256")
            digest = base64.b64decode(encoded[7:] + "=", altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(digest).decode().rstrip("=") != encoded[7:]:
                raise WheelError("noncanonical RECORD digest")
            if not re.fullmatch(r"0|[1-9][0-9]*", size) or len(size) > 12 or int(size) != paths[name].file_size:
                raise WheelError("RECORD size mismatch")
            records[name] = (digest.hex(), int(size))
        if set(records) != {name for name, info in paths.items() if not info.is_dir()}:
            raise WheelError("all regular members must be covered by RECORD")
        return records
    except (ValueError, UnicodeError, csv.Error) as exc:
        raise WheelError("invalid RECORD encoding") from exc


def materialize_wheel(wheel_path: Path, authority: WheelAuthority, *, scratch_root: Path) -> Snapshot:
    """Hash a streaming private copy before ZIP parsing, extraction or spawn.

    The original path is opened once. The private copy used for hashing is the
    very same file used for verification/extraction; a path replacement cannot
    switch the bytes after verification.
    """
    work = None
    try:
        work = Path(tempfile.mkdtemp(prefix="elpis-driver-", dir=scratch_root)).resolve()
        package = work / "snapshot"
        with (work / "artifact.whl").open("w+b") as copied:
            total = 0
            # Nonblocking open plus fstat avoids hanging on a FIFO/device path.
            descriptor = os.open(wheel_path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise WheelError("wheel artifact must be a regular file")
                while chunk := source.read(CHUNK):
                    total += len(chunk)
                    if total > MAX_WHEEL_BYTES:
                        raise WheelError("wheel compressed size limit")
                    copied.write(chunk)
            copied.flush()
            if total:
                with mmap.mmap(
                    copied.fileno(),
                    0,
                    access=mmap.ACCESS_READ,
                ) as view:
                    actual_wheel_sha256 = _sha256_hex(view)
            else:
                actual_wheel_sha256 = _sha256_hex(b"")
            if actual_wheel_sha256 != authority.wheel_sha256:
                raise WheelError("outer wheel SHA-256 mismatch")
            _preflight_directory(copied, total)
            with zipfile.ZipFile(copied) as archive:
                paths = _inventory(archive)
                root = _verify_metadata(archive, paths, authority)
                records = _records(archive, paths, root)
                # Verify every byte before materializing any package content.
                manifest = []
                for name, (expected, size) in sorted(records.items()):
                    payload = bytearray()
                    actual_size = 0
                    with archive.open(paths[name]) as stream:
                        while chunk := stream.read(CHUNK):
                            actual_size += len(chunk)
                            if actual_size > size:
                                raise WheelError("expanded ZIP member exceeds declared size")
                            payload.extend(chunk)
                    actual = _sha256_hex(payload)
                    if actual_size != size or expected and actual != expected:
                        raise WheelError("RECORD content digest mismatch")
                    manifest.append((name, actual, size))
                package.mkdir(mode=0o700)
                for name, expected, size in manifest:
                    destination = package / name
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with archive.open(paths[name]) as source, destination.open("xb") as target:
                        while chunk := source.read(CHUNK):
                            target.write(chunk)
                    actual_size = destination.stat().st_size
                    with destination.open("rb") as verified:
                        if actual_size:
                            with mmap.mmap(
                                verified.fileno(),
                                0,
                                access=mmap.ACCESS_READ,
                            ) as view:
                                actual = _sha256_hex(view)
                        else:
                            actual = _sha256_hex(b"")
                    if actual != expected or actual_size != size:
                        raise WheelError("artifact changed during extraction")
                    destination.chmod(0o400)
        (work / "artifact.whl").unlink()
        for directory, _, _ in os.walk(package, topdown=False):
            Path(directory).chmod(0o500)
        (work / "cwd").mkdir(mode=0o700)
        members = tuple(manifest)
        return Snapshot(work, package, members, content_digest("elpis.inference.isolated.snapshot-members.v1", members), authority.digest)
    except (OSError, ValueError, EOFError, zlib.error, zipfile.BadZipFile, RuntimeError) as exc:
        if work is not None:
            remove_snapshot(work)
        if isinstance(exc, WheelError):
            raise
        raise WheelError("wheel verification/materialization failed") from exc


def recheck_snapshot(root: Path, members: list, expected_digest: str) -> None:
    """Child-side byte verification immediately before making snapshot importable."""
    if content_digest("elpis.inference.isolated.snapshot-members.v1", members) != expected_digest:
        raise WheelError("snapshot manifest identity mismatch")
    expected_names = set()
    for name, expected, size in members:
        if _member_name(name) != name:
            raise WheelError("invalid snapshot member")
        path = root / name
        expected_names.add(name)
        if path.is_symlink() or not path.is_file() or path.resolve().is_relative_to(root) is False:
            raise WheelError("snapshot path escaped/disappeared")
        if path.stat().st_mode & 0o222:
            raise WheelError("writable snapshot content")
        with path.open("rb") as stream:
            total = os.fstat(stream.fileno()).st_size
            if total > size:
                raise WheelError("snapshot grew")
            if total:
                with mmap.mmap(
                    stream.fileno(),
                    0,
                    access=mmap.ACCESS_READ,
                ) as view:
                    actual = _sha256_hex(view)
            else:
                actual = _sha256_hex(b"")
        if total != size or actual != expected:
            raise WheelError("snapshot bytes changed")
    actual_names = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        if Path(directory).is_symlink() or Path(directory).stat().st_mode & 0o222:
            raise WheelError("unsafe snapshot directory")
        if any(Path(directory, name).is_symlink() for name in dirs):
            raise WheelError("snapshot symlink directory")
        actual_names.update((Path(directory, name).relative_to(root).as_posix()) for name in files)
    if actual_names != expected_names:
        raise WheelError("snapshot inventory changed")
