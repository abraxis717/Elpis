import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import publication_assertions_v2 as publication
from tools import release_snapshot


def test_json_loader_rejects_duplicate_top_level_key():
    with pytest.raises(
        publication.PublicationAuthorityError,
        match="DUPLICATE_JSON_KEY:a",
    ):
        publication._load_json_bytes(
            b'{"a":1,"a":2}\n',
            label="duplicate",
        )


def test_json_loader_rejects_duplicate_nested_key():
    with pytest.raises(
        publication.PublicationAuthorityError,
        match="DUPLICATE_JSON_KEY:x",
    ):
        publication._load_json_bytes(
            b'{"outer":{"x":1,"x":2}}\n',
            label="nested-duplicate",
        )


def test_registry_loader_preserves_legacy_serialization_compatibility(tmp_path):
    path = tmp_path / publication.REGISTRY_NAME
    path.write_bytes(b'{"schema":"fixture"}\n')

    assert publication.load_registry(tmp_path) == {"schema": "fixture"}


def test_registry_loader_rejects_duplicate_keys(tmp_path):
    path = tmp_path / publication.REGISTRY_NAME
    path.write_bytes(b'{"schema":"one","schema":"two"}\n')

    with pytest.raises(
        publication.PublicationAuthorityError,
        match="DUPLICATE_JSON_KEY:schema",
    ):
        publication.load_registry(tmp_path)


def _published():
    return {
        "version": "2.2.31",
        "release_tag": "Elpis2.2.31",
        "peeled_commit": "a" * 40,
        "manifest_sha256": "b" * 64,
    }


def _snapshot_dirs(tmp_path, published):
    sealed = tmp_path / "sealed"
    live = tmp_path / "live"
    sealed.mkdir()
    live.mkdir()

    old = {"publication_assertions": []}
    new = {
        "publication_assertions": [published],
    }

    (sealed / "PUBLICATION_ASSERTIONS.json").write_text(
        json.dumps(old, indent=2, ensure_ascii=False) + "\n"
    )
    (live / "PUBLICATION_ASSERTIONS.json").write_text(
        json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    )

    return live, sealed, old, new


def _stub_snapshot_git(monkeypatch):
    monkeypatch.setattr(
        release_snapshot.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout=b"",
            stderr=b"",
        ),
    )
    monkeypatch.setattr(
        release_snapshot,
        "compare_physical",
        lambda *a, **k: [],
    )


def test_postpublication_snapshot_rejects_whitespace_equivalent_registry(
    tmp_path, monkeypatch
):
    published = _published()
    live, sealed, old, new = _snapshot_dirs(tmp_path, published)
    _stub_snapshot_git(monkeypatch)

    # Same parsed object, different physical representation.
    (live / "PUBLICATION_ASSERTIONS.json").write_text(
        json.dumps(new, separators=(",", ":")) + "\n"
    )

    errors = release_snapshot.postpublication_errors(
        live, sealed, published
    )

    assert errors == ["SNAPSHOT_ASSERTION_DELTA_INVALID"]


def test_postpublication_snapshot_rejects_duplicate_key_registry(
    tmp_path, monkeypatch
):
    published = _published()
    live, sealed, old, new = _snapshot_dirs(tmp_path, published)
    _stub_snapshot_git(monkeypatch)

    encoded = json.dumps([published], separators=(",", ":"))
    (live / "PUBLICATION_ASSERTIONS.json").write_text(
        '{"publication_assertions":[],'
        '"publication_assertions":'
        + encoded
        + "}\n"
    )

    errors = release_snapshot.postpublication_errors(
        live, sealed, published
    )

    assert errors
    assert "DUPLICATE_JSON_KEY" in errors[0]


def test_postpublication_snapshot_rejects_noncanonical_ratification(
    tmp_path, monkeypatch
):
    published = _published()
    live, sealed, old, new = _snapshot_dirs(tmp_path, published)
    _stub_snapshot_git(monkeypatch)

    ratification = {
        "schema": "elpis.release-ratification.v1",
        "version": published["version"],
        "release_tag": published["release_tag"],
        "sealed_commit": published["peeled_commit"],
        "manifest_sha256": published["manifest_sha256"],
        "publication_assertion_sha256":
            __import__("hashlib").sha256(
                (
                    json.dumps(
                        published,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    + "\n"
                ).encode()
            ).hexdigest(),
    }

    path = (
        live
        / "RELEASE_RATIFICATIONS"
        / f"{published['release_tag']}.json"
    )
    path.parent.mkdir()
    path.write_text(
        json.dumps(ratification, separators=(",", ":")) + "\n"
    )

    errors = release_snapshot.postpublication_errors(
        live, sealed, published
    )

    assert errors == ["SNAPSHOT_RATIFICATION_INVALID"]
