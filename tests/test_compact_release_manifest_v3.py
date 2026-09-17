"""Tiny fixture trees exercise compact authority without sealing this release."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tarfile
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/release_tree_digest.py"
V3 = runpy.run_path(str(HELPER))
REL = "manifests/Elpis9.9.9.RELEASE_MANIFEST.json"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args]).decode().strip()


def header(version="9.9.9", schema="v3"):
    historical = json.loads((ROOT / "manifests/Elpis2.2.5.RELEASE_MANIFEST.json").read_text())
    data = {key: value for key, value in historical.items() if key not in {"files", "file_count"}}
    data.update(schema=f"elpis.release-manifest.{schema}", version=version,
                release_name=f"Elpis{version}", release_tag=f"Elpis{version}")
    return data


def tree(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a.txt").write_bytes(b"abc")
    (root / "nested").mkdir()
    (root / "nested/z.txt").write_bytes(b"xyz\x00")
    return root


def record(root):
    return header() | V3["build_record"](root, REL)


def write_record(root, data):
    path = root / REL
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def verify(root, data):
    return V3["verify_record"](root, REL, data)


def verifier(root, version="9.9.9"):
    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    g = ns["check_manifest"].__globals__
    rel = Path(f"manifests/Elpis{version}.RELEASE_MANIFEST.json")
    g.update(REPO=root, RELEASE_VERSION=version, MANIFEST_REL=rel, MANIFEST=root / rel)
    g["RELEASE_IDENTITIES"][version] = {
        key: header()[key] for key in ("primitive_closure_commit", "base_release_commit")
    }
    return ns


def git_tree(tmp_path, object_format="sha1"):
    root = tree(tmp_path)
    git(root, "init", "-q", f"--object-format={object_format}")
    git(root, "config", "user.name", "Compact Fixture")
    git(root, "config", "user.email", "compact@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture")
    return root


def test_digest_has_independent_framing_vector(tmp_path):
    root = tree(tmp_path)
    encoded = b"elpis.publication-tree.v1\0" + (2).to_bytes(8, "big")
    for path, content in [(b"a.txt", b"abc"), (b"nested/z.txt", b"xyz\x00")]:
        encoded += len(path).to_bytes(8, "big") + path + b"F"
        encoded += len(content).to_bytes(8, "big") + hashlib.sha256(content).digest()
    expected = hashlib.sha256(encoded).hexdigest()
    paths = ["nested/z.txt", "a.txt"]
    assert V3["tree_digest"](root, paths) == expected
    os.utime(root / "a.txt", (123, 456))
    assert V3["tree_digest"](root, list(reversed(paths))) == expected


@pytest.mark.parametrize("mutation", ["byte", "addition", "deletion", "rename"])
def test_gitless_mutations_fail_the_digest_guard(tmp_path, mutation):
    root = tree(tmp_path)
    data = record(root)
    write_record(root, data)
    assert verify(root, data) == []
    if mutation == "byte":
        (root / "a.txt").write_bytes(b"abd")
    elif mutation == "addition":
        (root / "new.txt").write_bytes(b"new")
    elif mutation == "deletion":
        (root / "a.txt").unlink()
    else:
        (root / "a.txt").rename(root / "renamed.txt")
    assert "V3_PUBLICATION_TREE_SHA256_MISMATCH" in verify(root, data)
    # Disable just the aggregate comparison: same-count mutations now pass.
    data["publication_tree_sha256"] = V3["build_record"](root, REL)["publication_tree_sha256"]
    if mutation in {"byte", "rename"}:
        assert verify(root, data) == []


@pytest.mark.parametrize("path", ["build", "nested/__pycache__", "x.egg-info", ".pytest_cache"])
@pytest.mark.parametrize("with_git", [False, True])
def test_ephemeral_contamination_is_not_excludable(tmp_path, path, with_git):
    root = git_tree(tmp_path) if with_git else tree(tmp_path)
    data = record(root)
    (root / path).mkdir(parents=True)
    assert any("EPHEMERAL ARTIFACT PRESENT" in e for e in verify(root, data))


def test_compact_schema_has_bounded_fields_and_size(tmp_path):
    root = tree(tmp_path)
    for i in range(300):
        (root / f"file-{i:04d}.txt").write_text(str(i))
    data = record(root)
    paths = V3["publication_paths"](root, REL)
    inventory = header(schema="v2") | {"file_count": len(paths), "files": [
        {"path": p, "sha256": hashlib.sha256((root / p).read_bytes()).hexdigest()} for p in paths
    ]}
    assert not any(isinstance(v, (list, dict)) for v in data.values())
    assert len(json.dumps(data, indent=2)) < len(json.dumps(inventory, indent=2)) / 20
    assert verify(root, data | {"files": []}) == ["V3_AUTHORITY_FIELDS_INVALID"]
    assert verify(root, data | {"inventory": {}}) == ["V3_AUTHORITY_FIELDS_INVALID"]


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_git_tree_is_native_git_identity_and_survives_seal_commit(tmp_path, object_format):
    root = git_tree(tmp_path, object_format)
    # Exercise native directory ordering against similarly named files.
    (root / "nested.txt").write_bytes(b"sibling")
    (root / "link").symlink_to("a.txt")
    (root / "a.txt").chmod(0o755)
    git(root, "add", ".")
    git(root, "commit", "-qm", "modes and sort")
    data = record(root)
    assert data["git_tree_oid"] == git(root, "rev-parse", "HEAD^{tree}")
    assert data["git_object_format"] == object_format
    write_record(root, data)
    (root / "PUBLISHED_RELEASES.json").write_text("{}")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seal and publication fact")
    assert verify(root, data) == []
    (root / "PUBLISHED_RELEASES.json").write_text('{"publication": "later"}')
    assert verify(root, data) == []
    assert data["git_tree_oid"] != git(root, "rev-parse", "HEAD^{tree}")


@pytest.mark.parametrize("mutation", ["content", "addition", "deletion", "rename", "mode"])
def test_git_head_tree_mismatch_is_detected(tmp_path, mutation):
    root = git_tree(tmp_path)
    data = record(root)
    if mutation == "content":
        (root / "a.txt").write_bytes(b"abd")
    elif mutation == "addition":
        (root / "new.txt").write_bytes(b"added")
    elif mutation == "deletion":
        (root / "a.txt").unlink()
    elif mutation == "rename":
        (root / "a.txt").rename(root / "b.txt")
    else:
        (root / "a.txt").chmod(0o755)
    git(root, "add", "-A")
    assert verify(root, data) == ["PUBLICATION_GIT_INDEX_HEAD_MISMATCH"]
    git(root, "commit", "-qm", "mutate included tree")
    assert "V3_GIT_TREE_OID_MISMATCH" in verify(root, data)


def test_unstaged_git_bytes_and_forged_tree_id_fail_independently(tmp_path):
    root = git_tree(tmp_path)
    data = record(root)
    assert verify(root, data | {"git_tree_oid": "0" * 40}) == ["V3_GIT_TREE_OID_MISMATCH"]
    (root / "a.txt").write_bytes(b"abd")
    assert verify(root, data) == ["PUBLICATION_GIT_WORKTREE_HEAD_MISMATCH"]


def test_git_archive_verifies_without_git_then_fails_after_mutation(tmp_path):
    root = git_tree(tmp_path)
    data = record(root)
    write_record(root, data)
    git(root, "add", ".")
    git(root, "commit", "-qm", "sealed")
    exported = tmp_path / "export"
    exported.mkdir()
    archive = subprocess.check_output(["git", "-C", str(root), "archive", "HEAD"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(exported, filter="data")
    ns = verifier(exported)
    assert ns["check_manifest"]() == (True, [])
    assert ns["check_repository_identity"]() == (True, [])
    assert ns["check_repository_identity"](require_git=True) == (False, ["REPOSITORY_GIT_REQUIRED"])
    (exported / "a.txt").write_bytes(b"abd")
    assert ns["check_manifest"]() == (False, ["V3_PUBLICATION_TREE_SHA256_MISMATCH"])


@pytest.mark.requires_git
def test_historical_v2_archive_verifies_without_migration(tmp_path):
    archive = subprocess.check_output(["git", "-C", str(ROOT), "archive", "Elpis2.1.26"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(tmp_path, filter="data")
    ns = verifier(tmp_path, "2.1.26")
    before = ns["check_manifest"].__globals__["MANIFEST"].read_bytes()
    assert json.loads(before)["schema"] == "elpis.release-manifest.v2"
    assert ns["check_manifest"]() == (True, [])
    (tmp_path / "VERSION").write_text("mutation")
    assert ns["check_manifest"]() == (False, ["DIGEST MISMATCH: VERSION"])
    assert ns["check_manifest"].__globals__["MANIFEST"].read_bytes() == before


def test_current_226_cannot_opt_into_v3():
    with pytest.raises(ValueError, match="V3_REQUIRES_SUCCESSOR_AFTER_2_2_6"):
        V3["require_successor"]("2.2.6")
    if (ROOT / "VERSION").read_text().strip() == "2.2.6":
        # Refusal happens before writing in the real checkout, sealed or not.
        manifest = ROOT / "manifests/Elpis2.2.6.RELEASE_MANIFEST.json"
        before = manifest.read_bytes() if manifest.exists() else None
        ns = runpy.run_path(str(ROOT / "tools/seal_release.py"))
        assert ns["main"](["--schema", "v3"]) == 2
        assert (manifest.read_bytes() if manifest.exists() else None) == before


@pytest.mark.parametrize("path", ["../escape", "/absolute", "a//b", "./a", "a\\b", "."])
def test_noncanonical_paths_are_rejected(path):
    with pytest.raises(ValueError, match="PUBLICATION_PATH_INVALID"):
        V3["normalized_path"](path)


def test_symlink_identity_and_escape(tmp_path):
    root = tree(tmp_path)
    (root / "link").symlink_to("a.txt")
    data = record(root)
    (root / "link").unlink()
    (root / "link").write_bytes(b"a.txt")
    assert "V3_PUBLICATION_TREE_SHA256_MISMATCH" in verify(root, data)
    (root / "link").unlink()
    (root / "link").symlink_to("../outside")
    assert any("SYMLINK ESCAPE" in e for e in verify(root, data))


def sealer(root):
    ns = runpy.run_path(str(ROOT / "tools/seal_release.py"))
    checked = verifier(root)
    # This helper intentionally exercises compact release-manifest mechanics
    # in tiny synthetic trees that do not contain repository-wide authority
    # files. Immutability itself is qualified independently and through the
    # real release-gate integration tests.
    checked["check_repository_immutability"] = lambda: (True, [])
    g = ns["main"].__globals__
    g["REPO"] = root
    g["runpy"] = SimpleNamespace(run_path=lambda path: (
        V3 if Path(path).name == "release_tree_digest.py" else checked
    ))
    return ns["main"], checked


@pytest.mark.parametrize("schema", [None, "v3"])
def test_future_sealer_default_is_v2_and_v3_is_explicit(tmp_path, schema):
    root = tree(tmp_path)
    (root / "VERSION").write_text("9.9.9")
    seal, checked = sealer(root)
    assert seal([] if schema is None else ["--schema", schema]) == 0
    data = json.loads((root / REL).read_text())
    assert data["schema"] == f"elpis.release-manifest.{schema or 'v2'}"
    assert ("files" in data) == (schema is None)
    assert checked["check_manifest"]() == (True, [])
    before = (root / REL).read_bytes()
    assert seal(["--schema", "v3"]) == 2
    assert (root / REL).read_bytes() == before


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_seal_candidate_and_strict_tag_boundaries_remain_independent(tmp_path, object_format):
    root = git_tree(tmp_path, object_format)
    (root / "VERSION").write_text("9.9.9")
    git(root, "add", ".")
    git(root, "commit", "-qm", "candidate")
    seal, checked = sealer(root)
    check = checked["check_repository_identity"]
    g = check.__globals__
    authority = git(root, "rev-parse", "HEAD")
    g["RELEASE_IDENTITIES"]["9.9.9"] = dict.fromkeys(
        ("primitive_closure_commit", "base_release_commit"), authority,
    )
    assert check(require_git=True) == (True, [])
    assert seal(["--schema", "v3"]) == 0
    assert checked["check_manifest"]() == (True, [])
    assert check(require_git=True, require_tag=True, require_tag_at_head=True) == (
        False, ["RELEASE_TAG_COMMIT_MISSING:Elpis9.9.9"],
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "seal")
    git(root, "tag", "-a", "Elpis9.9.9", "-m", "fixture tag")
    assert check(require_git=True, require_tag=True, require_tag_at_head=True) == (True, [])
    assert checked["check_manifest"]() == (True, [])
    git(root, "commit", "--allow-empty", "-qm", "later commit")
    assert check(require_git=True) == (True, [])
    assert checked["check_manifest"]() == (True, [])
    ok, errors = check(require_git=True, require_tag=True, require_tag_at_head=True)
    assert not ok and any(e.startswith("RELEASE_TAG_NOT_HEAD:") for e in errors)


def test_v3_sealer_refuses_dirty_candidate_without_writing(tmp_path):
    root = git_tree(tmp_path)
    (root / "VERSION").write_text("9.9.9")
    git(root, "add", ".")
    git(root, "commit", "-qm", "candidate")
    seal, checked = sealer(root)
    checked["check_repository_identity"].__globals__["RELEASE_IDENTITIES"]["9.9.9"] = dict.fromkeys(
        ("primitive_closure_commit", "base_release_commit"), git(root, "rev-parse", "HEAD"),
    )
    (root / "a.txt").write_bytes(b"abd")
    assert seal(["--schema", "v3"]) == 3
    assert not (root / REL).exists()


def test_registry_remains_outside_digest_but_manifest_hash_still_authenticates_v3(tmp_path):
    root = tree(tmp_path)
    data = record(root)
    write_record(root, data)
    sha = hashlib.sha256((root / REL).read_bytes()).hexdigest()
    registry = {"schema": "elpis.published-releases.v1", "published_releases": [{
        "version": "9.9.9", "release_tag": "Elpis9.9.9", "manifest_path": REL,
        "manifest_sha256": sha, "peeled_commit": "a" * 40,
    }]}
    (root / "PUBLISHED_RELEASES.json").write_text(json.dumps(registry))
    assert verify(root, data) == []
    data["publication_tree_sha256"] = "0" * 64
    write_record(root, data)
    assert hashlib.sha256((root / REL).read_bytes()).hexdigest() != sha


@pytest.mark.parametrize("changes,marker", [
    ({"publication_policy": "unknown"}, "V3_PUBLICATION_POLICY_INVALID"),
    ({"tree_digest_algorithm": "unknown"}, "V3_PUBLICATION_POLICY_INVALID"),
    ({"file_count": True}, "V3_TREE_RECORD_INVALID"),
    ({"publication_tree_sha256": "wrong"}, "V3_TREE_RECORD_INVALID"),
    ({"git_tree_oid": "0" * 40}, "V3_GIT_RECORD_INVALID"),
])
def test_malformed_v3_authority_fails_closed(tmp_path, changes, marker):
    root = tree(tmp_path)
    assert verify(root, record(root) | changes) == [marker]


def test_git_local_residue_is_scanned_but_not_publication_membership(tmp_path):
    root = git_tree(tmp_path)
    data = record(root)
    (root / "local.txt").write_bytes(b"untracked")
    assert verify(root, data) == []
    (root / "build").mkdir()
    assert "EPHEMERAL ARTIFACT PRESENT" in verify(root, data)[0]


def test_empty_tree_and_unicode_newline_paths_are_deterministic(tmp_path):
    assert V3["tree_digest"](tmp_path, []) == hashlib.sha256(
        b"elpis.publication-tree.v1\0" + b"\0" * 8,
    ).hexdigest()
    for name in ["é.txt", "e\u0301.txt", "line\nbreak", "tab\tname"]:
        (tmp_path / name).write_text(name)
    paths = V3["publication_paths"](tmp_path, REL)
    assert V3["tree_digest"](tmp_path, paths) == V3["tree_digest"](tmp_path, paths[::-1])
    with pytest.raises(ValueError, match="PUBLICATION_DUPLICATE_PATH"):
        V3["tree_digest"](tmp_path, paths + paths)


def test_manifest_cannot_ratify_its_own_release_identity(tmp_path):
    root = tree(tmp_path)
    data = record(root)
    data["primitive_closure_commit"] = "0" * 40
    write_record(root, data)
    ok, errors = verifier(root)["check_manifest"]()
    assert not ok
    assert len(errors) == 1 and "manifest primitive_closure_commit mismatch" in errors[0]


def test_verifier_rejects_v3_for_current_release_independently_of_sealer(tmp_path):
    root = tree(tmp_path)
    write_record(root, record(root))
    ns = verifier(root)
    ns["check_manifest"].__globals__["RELEASE_VERSION"] = "2.2.6"
    ok, errors = ns["check_manifest"]()
    assert not ok and "V3_REQUIRES_SUCCESSOR_AFTER_2_2_6" in errors


def test_compact_membership_rejects_gitlinks(tmp_path):
    root = git_tree(tmp_path)
    data = record(root)
    git(root, "update-index", "--add", "--cacheinfo", "160000",
        git(root, "rev-parse", "HEAD"), "submodule")
    assert verify(root, data) == ["PUBLICATION_GIT_MODE_UNSUPPORTED:submodule:160000"]


def test_missing_tracked_file_is_explicit(tmp_path):
    root = git_tree(tmp_path)
    data = record(root)
    (root / "a.txt").unlink()
    assert verify(root, data) == ["PUBLICATION_FILE_MISSING:a.txt"]


def test_shallow_history_still_fails_closed_without_clone(tmp_path):
    root = git_tree(tmp_path)
    ns = verifier(root)
    check = ns["check_repository_identity"]
    check.__globals__["RELEASE_IDENTITIES"]["9.9.9"] = dict.fromkeys(
        ("primitive_closure_commit", "base_release_commit"), "0" * 40,
    )
    # A synthetic shallow boundary exercises the real Git shallow predicate.
    (root / ".git/shallow").write_text(git(root, "rev-parse", "HEAD") + "\n")
    ok, errors = check(require_git=True)
    assert not ok and len(errors) == 2
    assert all(e.startswith("REPOSITORY_HISTORY_INCOMPLETE:") for e in errors)
