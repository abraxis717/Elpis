import gzip
import hashlib
import io
from pathlib import Path
import tarfile

from tools import release_distributions as dist


def make_sdist(path, *, gzip_mtime, member_mtime):
    raw = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=raw,
        mtime=gzip_mtime,
    ) as gz:
        with tarfile.open(
            fileobj=gz,
            mode="w",
            format=tarfile.PAX_FORMAT,
        ) as tar:
            info = tarfile.TarInfo("pkg/file.txt")
            body = b"identical\n"
            info.size = len(body)
            info.mtime = member_mtime
            info.uid = 1000
            info.gid = 1000
            info.uname = "joe"
            info.gname = "joe"
            tar.addfile(info, io.BytesIO(body))
    path.write_bytes(raw.getvalue())


def test_sdist_canonicalizer_removes_archive_time_variance(
    tmp_path,
):
    a = tmp_path / "a.tar.gz"
    b = tmp_path / "b.tar.gz"

    make_sdist(
        a,
        gzip_mtime=100,
        member_mtime=101,
    )
    make_sdist(
        b,
        gzip_mtime=900,
        member_mtime=901,
    )

    dist.canonicalize_sdist(a, 1234567890)
    dist.canonicalize_sdist(b, 1234567890)

    assert a.read_bytes() == b.read_bytes()


def test_release_authority_extracts_exact_json():
    body = (
        "notes\n\n"
        + dist.BEGIN
        + '{"files":[],"schema":"'
        + dist.AUTHORITY_SCHEMA
        + '","version":"2.2.31"}'
        + dist.END
        + "\n"
    )

    value = dist.extract_authority(body)

    assert value == {
        "schema": dist.AUTHORITY_SCHEMA,
        "version": "2.2.31",
        "files": [],
    }
