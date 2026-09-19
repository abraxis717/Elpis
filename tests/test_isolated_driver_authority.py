from __future__ import annotations

import base64
from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
import stat
import struct
import warnings
import zipfile

import pytest

from elpis_fractal_spine.isolated_driver import WheelAuthority
from elpis_fractal_spine.isolated_driver.errors import AuthorityError, WheelError
from elpis_fractal_spine.isolated_driver.wheel import materialize_wheel, remove_snapshot, recheck_snapshot

PACKAGE = "isolated_fixture_driver"
DIST = "isolated-fixture-driver"
INFO = "isolated_fixture_driver-1.0.dist-info"
GROUP = "elpis.inference_drivers.v1"
DRIVER = "synthetic.inference.v1"

PROVIDER = '''
import os
from elpis_fractal_spine.contracts import ModelResidencyBinding, InferenceExecutionResult
counter = 0
class Provider:
    def __init__(self, context):
        self.context = context
        self.held = False
    def acquire(self, request):
        if self.held:
            raise ValueError('already acquired')
        self.held = True
        return ModelResidencyBinding(request.model_id, request.preferred_tier, 'HOT', 'synthetic', 'cpu', 'lease')
    def release(self, binding):
        self.held = False
    def execute(self, request, *, residency=None):
        global counter
        counter += 1
        return InferenceExecutionResult('OK', (counter,), 1, 'synthetic', 'cpu', 'HOT')
    def close(self):
        pass
def factory(context):
    return Provider(context)
'''


def wheel_files(source=PROVIDER, *, name=DIST, version="1.0", group=GROUP,
                driver=DRIVER, target=PACKAGE + ":factory", extras=None):
    result = {
        PACKAGE + "/__init__.py": source.encode(),
        INFO + "/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode(),
        INFO + "/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: py3-none-any\n",
        INFO + "/entry_points.txt": f"[{group}]\n{driver} = {target}\n".encode(),
    }
    result.update(extras or {})
    return result


def make_wheel(tmp_path, source=PROVIDER, *, files=None, record_transform=None,
               extra_members=(), compression=zipfile.ZIP_STORED):
    files = wheel_files(source) if files is None else dict(files)
    record = []
    for name, content in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
        record.append(f"{name},sha256={digest},{len(content)}\n")
    record.append(f"{INFO}/RECORD,,\n")
    data = "".join(record)
    if record_transform is not None:
        data = record_transform(data)
    files[INFO + "/RECORD"] = data.encode()
    path = tmp_path / "opaque-artifact.whl"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w", compression=compression) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
            for name, content in extra_members:
                archive.writestr(name, content)
    authority = WheelAuthority(DRIVER, DIST, "1.0", GROUP, PACKAGE + ":factory",
                               hashlib.sha256(path.read_bytes()).hexdigest())
    return path, authority


def materialize(tmp_path, **kwargs):
    path, authority = make_wheel(tmp_path, **kwargs)
    return materialize_wheel(path, authority, scratch_root=tmp_path)


def test_authority_digest_and_frozen_validation(tmp_path):
    _, authority = make_wheel(tmp_path)
    assert authority.digest == WheelAuthority(**dict(reversed(list(asdict(authority).items())))).digest
    for key, value in (("driver_id", ""), ("distribution_name", "Mixed_Name"),
                       ("distribution_name", "two--names"), ("distribution_version", ""),
                       ("entry_point_group", "bad group"), ("entry_point_value", "x:y [extra]"),
                       ("entry_point_value", "x"), ("wheel_sha256", "F" * 64)):
        with pytest.raises(AuthorityError):
            replace(authority, **{key: value})
    with pytest.raises(AttributeError):
        authority.driver_id = "changed"


def test_valid_snapshot_readonly_rechecked_and_cleaned(tmp_path):
    snapshot = materialize(tmp_path)
    assert snapshot.package_root.is_dir()
    for path in snapshot.package_root.rglob("*"):
        assert not path.stat().st_mode & 0o222
    recheck_snapshot(snapshot.package_root, snapshot.members, snapshot.digest)
    content = snapshot.package_root / PACKAGE / "__init__.py"
    content.chmod(0o600)
    content.write_text("raise RuntimeError('tamper')")
    content.chmod(0o400)
    with pytest.raises(WheelError, match="changed|grew"):
        recheck_snapshot(snapshot.package_root, snapshot.members, snapshot.digest)
    remove_snapshot(snapshot.work_root)
    assert not snapshot.work_root.exists()


def test_hash_mismatch_precedes_zip_parsing_and_extraction(tmp_path, monkeypatch):
    path, authority = make_wheel(tmp_path)
    path.write_bytes(b"not a wheel")
    monkeypatch.setattr(zipfile, "ZipFile", lambda *a, **k: pytest.fail("ZIP parse before outer hash"))
    with pytest.raises(WheelError, match="outer wheel"):
        materialize_wheel(path, authority, scratch_root=tmp_path)
    assert not list(tmp_path.glob("elpis-driver-*"))


@pytest.mark.parametrize("member", ["../escape.py", "/escape.py", "a/../../escape", "a//b.py",
                                    "a/./b.py", "C:/escape", "a\\b.py", "a./b", "NUL", "a//", "a\x00hidden"])
def test_zip_path_attacks(tmp_path, member):
    # Include a correct RECORD entry, so a missing path check cannot be hidden
    # by an unrelated missing-hash rejection later in verification.
    with pytest.raises(WheelError, match="unsafe|ambiguous|aliased|path bound"):
        materialize(tmp_path, files=wheel_files(extras={member: b"attack"}))
    assert not list(tmp_path.glob("elpis-driver-*"))
    assert not (tmp_path.parent / "escape.py").exists()


@pytest.mark.parametrize("extra", [
    [(PACKAGE + "/__init__.py", PROVIDER.encode())],
    [(PACKAGE.upper() + "/alias.py", b"case alias")],
    [("collision", b"file"), ("collision/child", b"other")],
])
def test_duplicate_alias_and_directory_collision(tmp_path, extra):
    with pytest.raises(WheelError, match="duplicate|alias|collision"):
        materialize(tmp_path, extra_members=extra)


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFSOCK])
def test_zip_special_files(tmp_path, mode):
    info = zipfile.ZipInfo("special")
    info.create_system = 3
    info.external_attr = (mode | 0o777) << 16
    with pytest.raises(WheelError, match="special"):
        materialize(tmp_path, extra_members=[(info, b"/outside")])


@pytest.mark.parametrize("change", [{"name": "wrong"}, {"version": "9.0"}, {"group": "other.group"},
                                    {"driver": "other.driver"}, {"target": "wrong:factory"}])
def test_metadata_and_entrypoint_mismatches(tmp_path, change):
    with pytest.raises(WheelError):
        materialize(tmp_path, files=wheel_files(**change))


def test_duplicate_entrypoint_and_dist_info(tmp_path):
    files = wheel_files()
    files[INFO + "/entry_points.txt"] += f"{DRIVER} = evil:factory\n".encode()
    with pytest.raises(WheelError, match="duplicate"):
        materialize(tmp_path, files=files)
    files = wheel_files(extras={"other-1.0.dist-info/METADATA": b"Name: other\n"})
    with pytest.raises(WheelError, match="dist-info"):
        materialize(tmp_path, files=files)


@pytest.mark.parametrize("transform", [
    lambda r: r.replace("sha256=", "sha512=", 1),
    lambda r: r.replace("sha256=", "sha256=!", 1),
    lambda r: "\n".join(r.splitlines()[1:]) + "\n",
    lambda r: r.replace(r.splitlines()[0].split(",")[1], "", 1),
    lambda r: r.replace(r.splitlines()[0].split(",")[1], "sha256=" + "A" * 43, 1),
    lambda r: r + r.splitlines()[0] + "\n",
])
def test_record_tamper_missing_hash_and_malformed_digest(tmp_path, transform):
    with pytest.raises(WheelError, match="RECORD"):
        materialize(tmp_path, record_transform=transform)


def test_declared_size_bomb_and_ratio_bomb(tmp_path):
    path, authority = make_wheel(tmp_path)
    data = bytearray(path.read_bytes())
    position = data.index(b"PK\x01\x02")
    struct.pack_into("<I", data, position + 24, 129 * 1024 * 1024)
    path.write_bytes(data)
    authority = replace(authority, wheel_sha256=hashlib.sha256(data).hexdigest())
    with pytest.raises(WheelError, match="size limit"):
        materialize_wheel(path, authority, scratch_root=tmp_path)
    with pytest.raises(WheelError, match="ratio"):
        materialize(tmp_path, files=wheel_files(extras={"bomb.txt": b"a" * 1_000_000}), compression=zipfile.ZIP_DEFLATED)


def test_member_count_and_aggregate_limits(tmp_path, monkeypatch):
    import elpis_fractal_spine.isolated_driver.wheel as wheel
    path, authority = make_wheel(tmp_path)
    monkeypatch.setattr(wheel, "MAX_MEMBERS", 2)
    with pytest.raises(WheelError, match="count"):
        materialize_wheel(path, authority, scratch_root=tmp_path)
    monkeypatch.setattr(wheel, "MAX_MEMBERS", 4096)
    monkeypatch.setattr(wheel, "MAX_TOTAL_BYTES", 500)
    with pytest.raises(WheelError, match="aggregate"):
        materialize_wheel(path, authority, scratch_root=tmp_path)


def test_original_path_replacement_does_not_change_snapshot(tmp_path, monkeypatch):
    import elpis_fractal_spine.isolated_driver.wheel as wheel
    path, authority = make_wheel(tmp_path)
    original = wheel._inventory
    def replace_original(archive):
        path.write_bytes(b"substituted original path")
        return original(archive)
    monkeypatch.setattr(wheel, "_inventory", replace_original)
    snapshot = materialize_wheel(path, authority, scratch_root=tmp_path)
    assert (snapshot.package_root / PACKAGE / "__init__.py").read_text() == PROVIDER
    remove_snapshot(snapshot.work_root)


def test_central_directory_count_is_checked_before_zipfile_allocation(tmp_path, monkeypatch):
    path, authority = make_wheel(tmp_path)
    raw = bytearray(path.read_bytes())
    end = raw.rindex(b'PK\x05\x06')
    struct.pack_into('<HH', raw, end + 8, 65535, 65535)
    path.write_bytes(raw)
    authority = replace(authority, wheel_sha256=hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(zipfile, 'ZipFile', lambda *a, **k: pytest.fail('allocated unbounded ZIP directory'))
    with pytest.raises(WheelError, match='directory'):
        materialize_wheel(path, authority, scratch_root=tmp_path)


def test_empty_member_name_rejected_by_verifier(tmp_path):
    path, authority = make_wheel(tmp_path)
    local = struct.pack('<4s5H3I2H', b'PK\x03\x04', 20, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    central = struct.pack('<4s6H3I5H2I', b'PK\x01\x02', 20, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    end = struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, 1, 1, len(central), len(local), 0)
    raw = local + central + end
    path.write_bytes(raw)
    authority = replace(authority, wheel_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(WheelError, match='path bound'):
        materialize_wheel(path, authority, scratch_root=tmp_path)


def test_fifo_artifact_cannot_hang_verification(tmp_path):
    path, authority = make_wheel(tmp_path)
    fifo = tmp_path / 'artifact-fifo'
    os.mkfifo(fifo)
    with pytest.raises(WheelError, match='regular file'):
        materialize_wheel(fifo, authority, scratch_root=tmp_path)
    assert not list(tmp_path.glob('elpis-driver-*'))
