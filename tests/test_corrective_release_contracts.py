"""Adversarial successor contracts. These tests never publish or create keys."""
import ast
import base64
import json
from pathlib import Path
import subprocess
import sys
import hashlib
import zipfile
from types import SimpleNamespace

import pytest

from tools import full_release as full
from tools import release_origin as origin
from tools import release_orchestrator as machine
from tools import release_orchestrator_io as boundary_io
from tools import qualification_environment as environment
from tools import digest_sink_census as census

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().rstrip("\n")


def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    (root / "source.py").write_text("pass\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "candidate")
    return root


def test_git_status_columns_are_preserved(tmp_path):
    root = repository(tmp_path)
    (root / "source.py").write_text("# changed\n")
    assert full.git(root, "status", "--porcelain") == " M source.py"
    assert full.git_raw(root, "status", "--porcelain", "-z") == " M source.py\0"
    git(root, "add", ".")
    assert full.git(root, "status", "--porcelain") == "M  source.py"


@pytest.mark.parametrize("stage", ["assertion_commit", "ratification_commit"])
@pytest.mark.parametrize("boundary", ["intent", "commit", "returned", "complete", "state", "final"])
def test_restart_head_at_every_local_commit_boundary(tmp_path, stage, boundary):
    root = repository(tmp_path)
    state = {"candidate_sha": git(root, "rev-parse", "HEAD"), "version": "2.2.31", "orchestrator_closed": True}
    journal_path = tmp_path / "journal.json"
    journal = full.OuterJournal(journal_path)
    stages = [("assertion_commit", "PUBLICATION_ASSERTIONS.json"),
              ("ratification_commit", "RELEASE_RATIFICATIONS/Elpis2.2.31.json")]
    for current, path in stages:
        payload = b"{}\n"
        journal.begin(
            current,
            {
                "parent": git(root, "rev-parse", "HEAD"),
                "path": path,
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
        )
        if current == stage and boundary == "intent":
            break
        p = root / path
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(payload)
        git(root, "add", path)
        git(root, "commit", "-qm", current)
        oid = git(root, "rev-parse", "HEAD")
        if current == stage and boundary == "commit":
            break
        journal.returned(current, {"commit": oid})
        if current == stage and boundary == "returned":
            break
        journal.complete(current, {"commit": oid})
        if current == stage and boundary == "complete":
            break
        state[current] = oid
        if current == stage:
            if boundary == "final":
                state["final_main"] = oid
            break
    full.validate_resume_head(root, state, full.OuterJournal(journal_path))
    (root / "source.py").write_text("# injected descendant\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "unjournaled source change")
    with pytest.raises(full.FullReleaseError):
        full.validate_resume_head(root, state, full.OuterJournal(journal_path))


@pytest.mark.parametrize("version", [(3, 10), (3, 13), (3, 14)])
def test_unsupported_interpreter_fails_before_work(version):
    with pytest.raises(ValueError, match="PYTHON_UNSUPPORTED"):
        environment.supported_python(version)


def test_locks_are_exact_and_hash_bound(tmp_path):
    lock = tmp_path / "x.lock"
    lock.write_text("pytest==9.0.3 --hash=sha256:" + "a" * 64 + "\n")
    old, _ = environment.read_lock(lock)
    lock.write_text(lock.read_text().replace("9.0.3", "9.0.4"))
    assert environment.read_lock(lock)[0] != old
    for invalid in ("pytest", "pytest>=9", "pytest==9.0.3", "-r other.lock", "--index-url https://example.invalid"):
        lock.write_text(invalid)
        with pytest.raises(ValueError):
            environment.read_lock(lock)
    digest, entries = environment.read_lock(ROOT / "qualification/locks/test-tools-py311-py312.lock")
    assert len(digest) == 64 and len(entries) == 6


def test_pip_enforces_hashes_and_cannot_upgrade_locked_fixture(tmp_path):
    def wheel(version):
        path = tmp_path / f"audit_fixture-{version}-py3-none-any.whl"
        prefix = f"audit_fixture-{version}.dist-info/"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(prefix + "METADATA", f"Metadata-Version: 2.1\nName: audit-fixture\nVersion: {version}\n")
            archive.writestr(prefix + "WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            archive.writestr(prefix + "RECORD", "")
        return path
    old = wheel("1.0")
    wheel("1.1")
    lock = tmp_path / "fixture.lock"
    report = tmp_path / "report.json"
    command = [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--no-index",
               "--find-links", str(tmp_path), "--require-hashes", "--only-binary=:all:", "--report", str(report), "-r", str(lock)]
    lock.write_text("audit-fixture==1.0\n")
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode != 0 and "Hashes are required" in rejected.stderr
    lock.write_text("audit-fixture==1.0 --hash=sha256:" + hashlib.sha256(old.read_bytes()).hexdigest() + "\n")
    passed = subprocess.run(command, capture_output=True, text=True)
    assert passed.returncode == 0, passed.stderr
    assert json.loads(report.read_text())["install"][0]["metadata"]["version"] == "1.0"
    with zipfile.ZipFile(old, "a") as archive:
        archive.writestr("injected.py", "pass\n")
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode != 0 and "DO NOT MATCH THE HASHES" in rejected.stderr


def test_census_format_preserves_historical_fingerprints():
    # Historical registry equality is covered by the existing census suite.
    for expression in ["hashlib.sha256(x.encode())", "sha256(None)", "sha256(b'abc')", "sha256([x for x in y if x])", "sha256((lambda x: x)(1))"]:
        node = ast.parse(expression).body[0].value
        assert census.canonical_ast(node) == ast.dump(node)
    class NewSyntax(ast.AST):
        _fields = ()
    with pytest.raises(census.CensusError):
        census.canonical_ast(NewSyntax())


def test_origin_missing_or_repository_trust_root(tmp_path):
    root = repository(tmp_path)
    with pytest.raises(ValueError, match="TRUST_ROOT_REQUIRED"):
        origin.verify_tag(root, "a" * 40, "b" * 40, "Elpis2.2.31", None)
    path = root / "signers"
    path.write_text("invalid")
    with pytest.raises(ValueError, match="IN_REPOSITORY"):
        origin.verify_tag(root, "a" * 40, "b" * 40, "Elpis2.2.31", path)


@pytest.mark.parametrize("data", ["", "* ssh-ed25519 aaa", "bad", "test ssh-ed25519 !!!!", "test ssh-rsa AAAA"])
def test_origin_malformed_signers(tmp_path, data):
    root = repository(tmp_path)
    path = tmp_path / "signers"
    path.write_text(data)
    with pytest.raises(ValueError, match="SIGNERS_INVALID"):
        origin.verify_tag(root, "a" * 40, "b" * 40, "Elpis2.2.31", path)


@pytest.mark.parametrize("attack", ["unsigned", "target", "name", "modified-signature", "invalid-signer", "pgp-confusion", "pgp-message-confusion", "x509-confusion", "valid-boundary"])
def test_origin_verifier_process_contract(tmp_path, monkeypatch, attack):
    # Synthetic PUBLIC key bytes and injected Git results test argument binding;
    # this is explicitly not a cryptographic positive-control fixture.
    root = tmp_path / "repo"
    root.mkdir()
    trust = tmp_path / "signers"
    key = base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + b"a" * 32).decode()
    trust.write_text("release@example.invalid ssh-ed25519 " + key + "\n")
    calls = []
    target = "b" * 40
    tag = "Elpis2.2.31"
    payload = f"object {target if attack != 'target' else 'c' * 40}\ntype commit\ntag {tag if attack != 'name' else 'Other'}\ntagger Test <test@example.invalid> 1 +0000\n\nmessage\n".encode()
    if attack != "unsigned":
        encoded = base64.b64encode(b"SSHSIG\x00invalid-test-only")
        if attack == "pgp-confusion":
            encoded = b"-----BEGIN PGP SIGNATURE-----"
        elif attack == "pgp-message-confusion":
            encoded = b"-----BEGIN PGP MESSAGE-----"
        elif attack == "x509-confusion":
            encoded = b"-----BEGIN SIGNED MESSAGE-----"
        payload += b"-----BEGIN SSH SIGNATURE-----\n" + encoded + b"\n-----END SSH SIGNATURE-----\n"
    def run(argv, **kwargs):
        calls.append(argv)

        text_mode = bool(kwargs.get("text"))

        def result(stdout, stderr="", returncode=0):
            if text_mode:
                if isinstance(stdout, bytes):
                    stdout = stdout.decode(errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode(errors="replace")
            else:
                if isinstance(stdout, str):
                    stdout = stdout.encode()
                if isinstance(stderr, str):
                    stderr = stderr.encode()

            return SimpleNamespace(
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )

        if (
            "rev-parse" in argv
            and (
                "--show-toplevel" in argv
                or "--absolute-git-dir" in argv
                or "--git-common-dir" in argv
            )
        ):
            # Storage-topology observation is not the subject of this
            # synthetic verifier-process test. Model all repository
            # storage queries as the existing synthetic repository.
            return result(str(root) + "\n")

        if "verify-tag" in argv:
            return result(
                b"",
                b"signature result",
                1
                if attack in {
                    "modified-signature",
                    "invalid-signer",
                }
                else 0,
            )

        return result(
            b"tag\n" if "-t" in argv else payload
        )
    monkeypatch.setattr(origin.subprocess, "run", run)
    monkeypatch.setattr(origin.shutil, "which", lambda name: "/usr/bin/ssh-keygen")
    if attack == "valid-boundary":
        assert origin.verify_tag(
            root,
            "a" * 40,
            target,
            tag,
            trust,
        )["signature_format"] == "ssh-ed25519"

        verifier_calls = [
            argv
            for argv in calls
            if "verify-tag" in argv
        ]

        assert len(verifier_calls) == 1

        verifier = verifier_calls[0]

        assert (
            "gpg.ssh.allowedSignersFile=" + str(trust)
            in verifier
        )
        assert verifier[-2:] == [
            "verify-tag",
            "a" * 40,
        ]
    else:
        with pytest.raises(ValueError):
            origin.verify_tag(root, "a" * 40, target, tag, trust)


def test_real_historical_unsigned_tag_is_not_origin_authenticated(tmp_path):
    trust = tmp_path / "signers"
    key = base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + b"a" * 32).decode()
    trust.write_text("release@example.invalid ssh-ed25519 " + key + "\n")
    with pytest.raises(ValueError, match="SSH_SIGNATURE_REQUIRED"):
        origin.verify_tag(ROOT, "049c72e92c53ac927d2bef1c0b4d52a0ce1df1f6",
                          "912921b78f9766494e137f9f472b59fc4fc53b17", "Elpis2.2.30", trust)


@pytest.mark.parametrize("witness", ["absent", "actions", "release", "pypi"])
def test_tag_reconciliation_collects_external_witnesses_without_replay(tmp_path, witness):
    boundary = boundary_io.LiveBoundary(tmp_path, tmp_path / "unused")
    boundary.remote_refs = lambda intent: {"refs/heads/main": "a" * 40}
    requested = []
    def api(endpoint):
        requested.append(endpoint)
        if "/releases/" in endpoint:
            return {"id": 1} if witness == "release" else None
        rows = [{"id": 1}] if witness == "actions" else []
        return {"total_count": len(rows), "workflow_runs": rows}
    boundary.api = api
    boundary.runner = SimpleNamespace(http_json=lambda url: {"info": {}} if witness == "pypi" else None)
    outcome = boundary.reconcile("ANNOTATED_TAG_CREATED", {"repository": "abraxis717/Elpis", "version": "2.2.31"}, {})
    assert outcome["outcome"] == ("ABSENT_UNPROVEN" if witness == "absent" else "PREVIOUS_SIDE_EFFECT")
    assert set(outcome["witnesses"]) == {"remote_refs", "release", "pypi", "actions"}
    assert len(requested) == 2


def test_reconciliation_cannot_accept_truncated_actions_census(tmp_path):
    boundary = boundary_io.LiveBoundary(tmp_path, tmp_path / "unused")
    boundary.remote_refs = lambda intent: {}
    boundary.api = lambda endpoint: None if "/releases/" in endpoint else {"total_count": 1001, "workflow_runs": []}
    boundary.runner = SimpleNamespace(http_json=lambda url: None)
    with pytest.raises(machine.ReleaseError, match="CENSUS_INCOMPLETE"):
        boundary.reconcile("ANNOTATED_TAG_CREATED", {"repository": "abraxis717/Elpis", "version": "2.2.31"}, {})
