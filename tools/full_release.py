#!/usr/bin/env python3
"""One-shot resumable Elpis release from clean committed successor to terminal closeout.

Normal operator entry point:

    python tools/full_release.py --execute

The lower-level release_orchestrator remains authoritative for remote publication
mutations. This tool owns sealing, local qualification, orchestrator invocation,
publication-assertion commit, separate ratification commit, final-main fast-forward,
and exact hosted closeout qualification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import shutil
import tarfile
from typing import Any

try:
    from tools import publication_assertions_v2 as publication
    from tools import release_orchestrator as orchestrator
    from tools import release_orchestrator_io as orchestrator_io
except (ModuleNotFoundError, ImportError):
    import publication_assertions_v2 as publication
    import release_orchestrator as orchestrator
    import release_orchestrator_io as orchestrator_io

SCHEMA = "elpis.full-release.state.v1"
RATIFICATION_SCHEMA = "elpis.release-ratification.v1"
TERMINAL_SCHEMA = "elpis.full-release.closed.v1"
JOURNAL_SCHEMA = "elpis.full-release.journal.v1"
REPOSITORY = "abraxis717/Elpis"

LIFECYCLE_TESTS = (
    "tests/test_release_lifecycle_ordering.py",
    "tests/test_release_tag_qualification.py",
    "tests/test_release_repository_identity.py",
    "tests/test_publication_assertions_v2.py",
    "tests/test_published_releases_registry.py",
    "tests/test_release_sealer_guards.py",
    "tests/test_seal_release_mutations.py",
    "tests/test_release_immutability_gate_integration.py",
    "tests/test_compact_release_manifest_v3.py",
    "tests/test_current_release_hygiene.py",
    "tests/test_current_release_lifecycle_neutrality.py",
    "tests/test_tag_disposition_closure.py",
)
INSTALLED_ARTIFACT_TESTS = (
    "tests/test_reference_fms_driver_wheel.py",
    "tests/test_inference_plugin_trust_boundary_contract.py",
    "tests/test_optional_torch_collection_contract.py",
)


class FullReleaseError(RuntimeError):
    pass


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise FullReleaseError(diagnostic)


def run(root: Path, argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def git_raw(root: Path, *args: str) -> str:
    """Git machine output, including significant leading spaces and NULs."""
    proc = run(root, ["git", *args])
    require(proc.returncode == 0, "GIT_NONPASS:" + " ".join(args) + ":" + (proc.stdout or "")[-3000:])
    return proc.stdout or ""


def git(root: Path, *args: str) -> str:
    """Line-oriented Git text: remove final newline only, never status columns."""
    return git_raw(root, *args).removesuffix("\n")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    raw = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)



def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def journal_digest(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


class OuterJournal:
    """Hash-chained durable intent/returned/complete journal for outer mutations."""

    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = {"schema": JOURNAL_SCHEMA, "events": []}
        require(
            isinstance(self.data, dict)
            and set(self.data) == {"schema", "events"}
            and self.data["schema"] == JOURNAL_SCHEMA
            and isinstance(self.data["events"], list),
            "FULL_RELEASE_JOURNAL_INVALID",
        )
        self.replay()

    def replay(self) -> dict[str, Any] | None:
        previous = journal_digest({"schema": JOURNAL_SCHEMA})
        active = None
        completed = set()
        for seq, event in enumerate(self.data["events"]):
            require(
                isinstance(event, dict)
                and set(event) == {"seq", "previous", "stage", "kind", "data", "sha256"},
                "FULL_RELEASE_JOURNAL_EVENT_INVALID",
            )
            unsigned = {key: value for key, value in event.items() if key != "sha256"}
            require(
                event["seq"] == seq
                and event["previous"] == previous
                and event["sha256"] == journal_digest(unsigned),
                "FULL_RELEASE_JOURNAL_CHAIN_INVALID",
            )
            kind = event["kind"]
            stage = event["stage"]
            require(isinstance(stage, str) and stage, "FULL_RELEASE_JOURNAL_STAGE_INVALID")
            if kind == "intent":
                require(active is None and stage not in completed, "FULL_RELEASE_JOURNAL_INTENT_ORDER")
                active = event
            elif kind == "returned":
                require(active is not None and active["stage"] == stage, "FULL_RELEASE_JOURNAL_RETURN_ORDER")
                active = event
            elif kind == "complete":
                require(active is not None and active["stage"] == stage, "FULL_RELEASE_JOURNAL_COMPLETE_ORDER")
                completed.add(stage)
                active = None
            else:
                raise FullReleaseError("FULL_RELEASE_JOURNAL_KIND_INVALID")
            previous = event["sha256"]
        return active

    def completed(self, stage: str) -> bool:
        active = None
        done = False
        for event in self.data["events"]:
            if event["stage"] != stage:
                continue
            if event["kind"] == "intent":
                active = event
            elif event["kind"] == "returned":
                active = event
            elif event["kind"] == "complete":
                active = None
                done = True
        return done and active is None

    def active(self) -> dict[str, Any] | None:
        return self.replay()

    def write(self, stage: str, kind: str, data: Any) -> None:
        events = self.data["events"]
        previous = events[-1]["sha256"] if events else journal_digest({"schema": JOURNAL_SCHEMA})
        event = {
            "seq": len(events),
            "previous": previous,
            "stage": stage,
            "kind": kind,
            "data": data,
        }
        event["sha256"] = journal_digest(event)
        events.append(event)
        self.replay()
        atomic_json(self.path, self.data)

    def begin(self, stage: str, data: Any) -> None:
        active = self.active()
        if active is not None:
            require(active["stage"] == stage, "FULL_RELEASE_JOURNAL_OTHER_MUTATION_ACTIVE")
            return
        if self.completed(stage):
            return
        self.write(stage, "intent", data)

    def returned(self, stage: str, data: Any) -> None:
        active = self.active()
        require(active is not None and active["stage"] == stage, "FULL_RELEASE_JOURNAL_NO_ACTIVE_INTENT")
        if active["kind"] == "returned":
            return
        self.write(stage, "returned", data)

    def complete(self, stage: str, data: Any) -> None:
        if self.completed(stage):
            return
        active = self.active()
        require(active is not None and active["stage"] == stage, "FULL_RELEASE_JOURNAL_NO_ACTIVE_RETURN")
        if active["kind"] == "intent":
            self.returned(stage, {"recovered": True, "observed": data})
        self.write(stage, "complete", data)


def git_common_dir(root: Path) -> Path:
    value = git(root, "rev-parse", "--git-common-dir")
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def state_dir(root: Path, version: str) -> Path:
    return git_common_dir(root) / "elpis-full-release-v1" / version


def clean_status(root: Path) -> None:
    dirty = git(root, "status", "--porcelain", "--untracked-files=all")
    require(not dirty, "WORKTREE_NOT_CLEAN:" + dirty)


def current_version(root: Path) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    require(bool(version), "VERSION_EMPTY")
    return version


def remote_url() -> str:
    return f"https://github.com/{REPOSITORY}.git"


def remote_main(root: Path) -> str:
    out = git(root, "ls-remote", remote_url(), "refs/heads/main")
    rows = [line.split() for line in out.splitlines() if line.strip()]
    require(len(rows) == 1, "REMOTE_MAIN_CARDINALITY")
    return rows[0][0]


def base_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_check(root: Path, private: Path, name: str, argv: list[str],
              *, env: dict[str, str]) -> dict[str, Any]:
    proc = run(root, argv, env=env)
    raw = (proc.stdout or "").encode()
    (private / f"{name}.log").write_bytes(raw)
    require(proc.returncode == 0, f"QUALIFICATION_NONPASS:{name}:" + (proc.stdout or "")[-5000:])
    return {"argv": argv, "exit_code": 0, "output_sha256": sha256_bytes(raw)}


def native_check(root: Path, private: Path, *, env: dict[str, str]) -> dict[str, Any]:
    authority_path = root / "tools/inference_native_locus_v1.json"
    proc = run(root, [sys.executable, "tools/verify_inference_native_locus.py", "--check"], env=env)
    chunks = [proc.stdout or ""]
    require(proc.returncode == 0, "NATIVE_LOCUS_AUTHORITY_NONPASS:" + chunks[-1][-4000:])
    authority = json.loads(authority_path.read_text(encoding="utf-8"))

    workspace = private / "native-workspace"
    build = workspace / "native-build"
    tmp = workspace / "tmp"
    if workspace.exists():
        shutil.rmtree(workspace)
    build.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    library = build / "libelpis_fms_file_assets_r0.so"

    for argv in (
        ["cmake", "-S", "native/hacf/file_assets_r0", "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
        ["cmake", "--build", str(build), "--parallel"],
    ):
        proc = run(root, argv, env=env)
        chunks.append(proc.stdout or "")
        require(proc.returncode == 0, "NATIVE_BUILD_NONPASS:" + (proc.stdout or "")[-4000:])
    require(library.is_file(), "NATIVE_LIBRARY_MISSING")

    nenv = dict(env)
    nenv["PYTHONPATH"] = "runtime/R3/src:src"
    nenv["ELPIS_INFERENCE_WORKSPACE"] = str(workspace)
    nenv["ELPIS_FMS_FILE_LIBRARY"] = str(library)
    nenv["TMPDIR"] = str(tmp)
    proc = run(
        root,
        [
            sys.executable, "tools/run_inference_native_locus.py",
            "--section", "locus",
            "--junitxml", str(workspace / "inference-native.xml"),
            "--record", str(workspace / "locus-execution.json"),
        ],
        env=nenv,
    )
    chunks.append(proc.stdout or "")
    require(proc.returncode == 0, "NATIVE_EXACT_LOCUS_NONPASS:" + (proc.stdout or "")[-5000:])
    raw = "".join(chunks).encode()
    (private / "native.log").write_bytes(raw)
    return {
        "argv": ["INTERNAL_NATIVE_EXACT_LOCUS", *authority["locus"]["paths"]],
        "exit_code": 0,
        "output_sha256": sha256_bytes(raw),
    }


def installed_artifact_check(
    root: Path, private: Path, *, env: dict[str, str], version: str
) -> dict[str, Any]:
    workspace = private / "installed-artifact"
    if workspace.exists():
        shutil.rmtree(workspace)
    source = workspace / "source"
    dist = workspace / "dist"
    target = workspace / "site"
    source.mkdir(parents=True, exist_ok=True)
    dist.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    chunks: list[str] = []

    archive = workspace / "source.tar"
    archive_argv = [
        "git", "archive", "--format=tar", f"--output={archive}", "HEAD",
    ]
    proc = run(root, archive_argv, env=env)
    chunks.append(proc.stdout or "")
    require(
        proc.returncode == 0,
        "ARTIFACT_SOURCE_EXPORT_NONPASS:" + (proc.stdout or "")[-5000:],
    )
    import importlib
    snapshot = importlib.import_module('tools.release_snapshot' if __package__ else 'release_snapshot')
    with tarfile.open(archive) as stream:
        snapshot.extract_git_archive(stream, source)
    archive.unlink()

    build_argv = [
        sys.executable, "-m", "pip", "wheel", ".", "--no-deps",
        "--no-build-isolation",
        "--wheel-dir", str(dist),
    ]
    proc = run(source, build_argv, env=env)
    chunks.append(proc.stdout or "")
    require(proc.returncode == 0, "ARTIFACT_WHEEL_BUILD_NONPASS:" + (proc.stdout or "")[-5000:])
    wheels = sorted(dist.glob(f"elpisai-{version}-*.whl"))
    require(len(wheels) == 1, "ARTIFACT_WHEEL_CARDINALITY")
    wheel = wheels[0]

    install_argv = [
        sys.executable, "-m", "pip", "install", "--no-deps",
        "--target", str(target), str(wheel),
    ]
    proc = run(root, install_argv, env=env)
    chunks.append(proc.stdout or "")
    require(proc.returncode == 0, "ARTIFACT_WHEEL_INSTALL_NONPASS:" + (proc.stdout or "")[-5000:])

    smoke = (
        "import importlib.metadata as m, pathlib, sys;"
        f"site=pathlib.Path({str(target)!r}).resolve();"
        "sys.path.insert(0,str(site));"
        "import elpis.inference.file_assets as f;"
        "import elpis_reference.cli as c;"
        f"assert m.version('elpisai')=={version!r};"
        "assert pathlib.Path(f.__file__).resolve().is_relative_to(site);"
        "assert pathlib.Path(c.__file__).resolve().is_relative_to(site);"
        "print('INSTALLED_ARTIFACT_IMPORT_PASS')"
    )
    proc = run(root, [sys.executable, "-I", "-c", smoke], env=env)
    chunks.append(proc.stdout or "")
    require(proc.returncode == 0, "ARTIFACT_IMPORT_SMOKE_NONPASS:" + (proc.stdout or "")[-5000:])

    contract_argv = [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        *INSTALLED_ARTIFACT_TESTS,
    ]
    proc = run(root, contract_argv, env=env)
    chunks.append(proc.stdout or "")
    require(proc.returncode == 0, "ARTIFACT_CONTRACT_TESTS_NONPASS:" + (proc.stdout or "")[-5000:])

    raw = "".join(chunks).encode()
    (private / "installed_artifact.log").write_bytes(raw)
    return {
        "argv": ["BUILD_INSTALL_WHEEL_AND_CONTRACT_TESTS", *INSTALLED_ARTIFACT_TESTS],
        "exit_code": 0,
        "output_sha256": sha256_bytes(raw),
    }


def qualification_checks(root: Path, private: Path, *, version: str) -> dict[str, Any]:
    private.mkdir(parents=True, exist_ok=True)
    env = base_env()
    return {
        "root_tests": run_check(
            root, private, "root_tests",
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            env=env,
        ),
        "release_lifecycle": run_check(
            root, private, "release_lifecycle",
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *LIFECYCLE_TESTS],
            env=env,
        ),
        "negative_mutations": run_check(
            root, private, "negative_mutations",
            [sys.executable, "tools/run_mutation_suite_ci.py"],
            env=env,
        ),
        "installed_artifact": installed_artifact_check(
            root, private, env=env, version=version
        ),
        "native": native_check(root, private, env=env),
    }


def environment_authority(root: Path) -> dict:
    import importlib
    module = importlib.import_module('tools.qualification_environment' if __package__ else 'qualification_environment')
    return module.authority(root)


def preseal_qualification(
    root: Path, private: Path, development_sha: str, version: str
) -> Path:
    require(git(root, "rev-parse", "HEAD") == development_sha, "PRESEAL_HEAD_MISMATCH")
    clean_status(root)
    checks = qualification_checks(root, private, version=version)
    clean_status(root)
    report = {
        "schema": "elpis.full-release.preseal-qualification.v1",
        "environment": environment_authority(root),
        "development_sha": development_sha,
        "version": version,
        "checks": checks,
    }
    path = private / "preseal-qualification.json"
    atomic_json(path, report)
    return path


def qualification(root: Path, private: Path, candidate: str, manifest_sha: str) -> Path:
    require(git(root, "rev-parse", "HEAD") == candidate, "SEALED_QUALIFICATION_HEAD_MISMATCH")
    clean_status(root)
    checks = qualification_checks(root, private, version=current_version(root))
    clean_status(root)
    report = {
        "schema": "elpis.release-orchestrator.qualification.v1",
        "candidate_sha": candidate,
        "manifest_sha256": manifest_sha,
        "checks": checks,
    }
    if tuple(map(int, current_version(root).split('.'))) >= (2, 2, 31):
        report.update(schema="elpis.release-orchestrator.qualification.v2", environment=environment_authority(root))
    path = private / "qualification.json"
    atomic_json(path, report)
    return path


def ensure_preseal_qualified(
    root: Path, private: Path, state: dict[str, Any], state_path: Path
) -> dict[str, Any]:
    if state.get("preseal_qualification_path"):
        path = Path(state["preseal_qualification_path"])
        require(path.is_file(), "PRESEAL_QUALIFICATION_MISSING")
        require(
            sha256_bytes(path.read_bytes()) == state["preseal_qualification_sha256"],
            "PRESEAL_QUALIFICATION_DIGEST_MISMATCH",
        )
        return state
    path = preseal_qualification(
        root, private / "preseal", state["development_sha"], state["version"]
    )
    state["preseal_qualification_path"] = str(path)
    state["preseal_qualification_sha256"] = sha256_bytes(path.read_bytes())
    atomic_json(state_path, state)
    return state


def commit_paths(root: Path, commit: str) -> list[str]:
    out = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    return [line for line in out.splitlines() if line]


def validate_resume_head(root: Path, state: dict, journal: OuterJournal) -> None:
    """Accept only the exact journaled chain; an arbitrary descendant is unsafe.

    A commit may reach disk before returned/complete or before the state file.
    Recovery must have an intent, exact parent and exact path scope. The owning
    closeout step then validates payloads and durably completes that operation.
    """
    expected = state["candidate_sha"]
    head = git(root, "rev-parse", "HEAD")
    for stage, path in (
        ("assertion_commit", "PUBLICATION_ASSERTIONS.json"),
        ("ratification_commit", f"RELEASE_RATIFICATIONS/Elpis{state['version']}.json"),
    ):
        events = [e for e in journal.data["events"] if e["stage"] == stage]
        stored = state.get(stage)
        if not events:
            require(not stored, "RESUME_COMMIT_WITHOUT_JOURNAL:" + stage)
            break
        require(state.get("orchestrator_closed") is True, "RESUME_CLOSEOUT_BEFORE_ORCHESTRATOR")
        require(events[0]["kind"] == "intent" and events[0]["data"] == {"parent": expected, "path": path},
                "RESUME_INTENT_CONFLICT:" + stage)
        completed = next((e["data"].get("commit") for e in reversed(events) if e["kind"] == "complete"), None)
        if stored:
            require(stored == completed, "RESUME_STATE_JOURNAL_CONFLICT:" + stage)
        observed = completed or stored
        if observed is None and head != expected:
            observed = head
        if observed is None:
            break
        parents = git(root, "rev-list", "--parents", "-n", "1", observed).split()
        require(parents == [observed, expected], "RESUME_PARENT_MISMATCH:" + stage)
        require(commit_paths(root, observed) == [path], "RESUME_SCOPE_MISMATCH:" + stage)
        returned = next((e["data"].get("commit") for e in reversed(events) if e["kind"] == "returned"), None)
        require(returned is None or returned == observed, "RESUME_RETURNED_CONFLICT:" + stage)
        expected = observed
    require(head == expected, "LOCAL_HEAD_NOT_JOURNALED_RELEASE_STATE")
    if state.get("final_main"):
        require(state["final_main"] == expected, "RESUME_FINAL_MAIN_CONFLICT")


def ensure_sealed(
    root: Path,
    state: dict[str, Any],
    state_path: Path,
    journal: OuterJournal,
) -> dict[str, Any]:
    version = state["version"]
    development = state["development_sha"]
    manifest_rel = Path(f"manifests/Elpis{version}.RELEASE_MANIFEST.json")
    manifest = root / manifest_rel

    if "candidate_sha" in state:
        raw = subprocess.run(
            ["git", "show", f"{state['candidate_sha']}:{manifest_rel.as_posix()}"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(raw.returncode == 0, "SEALED_MANIFEST_NOT_IN_CANDIDATE")
        require(sha256_bytes(raw.stdout) == state["manifest_sha256"], "SEALED_MANIFEST_STATE_MISMATCH")
        validate_resume_head(root, state, journal)
        return state

    head = git(root, "rev-parse", "HEAD")
    if head != development:
        parent = git(root, "rev-parse", f"{head}^")
        require(parent == development, "UNJOURNALED_HEAD_ADVANCE_BEFORE_SEAL")
        require(
            commit_paths(root, head) == [manifest_rel.as_posix()],
            "RECOVERED_SEAL_COMMIT_SCOPE_NONPASS",
        )
        raw = subprocess.run(
            ["git", "show", f"{head}:{manifest_rel.as_posix()}"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(raw.returncode == 0, "RECOVERED_SEAL_MANIFEST_MISSING")
        active = journal.active()
        require(
            journal.completed("seal_commit")
            or (active is not None and active["stage"] == "seal_commit"),
            "SEAL_COMMIT_EXISTS_WITHOUT_JOURNAL_INTENT",
        )
        observed = {"candidate_sha": head, "manifest_sha256": sha256_bytes(raw.stdout)}
        journal.complete("seal_commit", observed)
        state.update(observed)
        atomic_json(state_path, state)
        clean_status(root)
        return state

    status = git(root, "status", "--porcelain", "--untracked-files=all")
    if not manifest.exists():
        require(not status, "WORKTREE_NOT_CLEAN_BEFORE_SEAL:" + status)
        journal.begin("seal_commit", {"development_sha": development, "manifest": manifest_rel.as_posix()})
        proc = run(
            root,
            [sys.executable, "tools/seal_release.py", "--version", version, "--schema", "v3"],
            env=base_env(),
        )
        require(proc.returncode == 0, "SEAL_NONPASS:" + (proc.stdout or "")[-5000:])
        status = git(root, "status", "--porcelain", "--untracked-files=all")
    else:
        require(
            journal.active() is not None
            and journal.active()["stage"] == "seal_commit",
            "MANIFEST_EXISTS_WITHOUT_SEAL_JOURNAL_INTENT",
        )

    require(
        status.splitlines() in (
            [f"?? {manifest_rel.as_posix()}"],
            [f"A  {manifest_rel.as_posix()}"],
        ),
        "SEAL_SCOPE_NONPASS:" + status,
    )
    git(root, "add", manifest_rel.as_posix())
    proc = run(root, ["git", "commit", "-m", f"release: seal Elpis{version} v3 manifest"])
    require(proc.returncode == 0, "SEAL_COMMIT_NONPASS:" + (proc.stdout or "")[-5000:])
    candidate = git(root, "rev-parse", "HEAD")
    observed = {"candidate_sha": candidate, "manifest_sha256": sha256_bytes(manifest.read_bytes())}
    journal.returned("seal_commit", observed)
    require(commit_paths(root, candidate) == [manifest_rel.as_posix()], "SEAL_COMMIT_SCOPE_POSTCHECK_NONPASS")
    journal.complete("seal_commit", observed)
    state.update(observed)
    atomic_json(state_path, state)
    clean_status(root)
    return state


def fixed_tagger(root: Path, state: dict[str, Any], state_path: Path) -> str:
    if state.get("tagger"):
        return state["tagger"]
    state["tagger"] = git(root, "var", "GIT_COMMITTER_IDENT")
    atomic_json(state_path, state)
    return state["tagger"]


def ensure_intent(root: Path, private: Path, state: dict[str, Any], state_path: Path) -> tuple[Path, Path]:
    if state.get("qualification_path") and state.get("intent_path"):
        return Path(state["intent_path"]), Path(state["qualification_path"])

    qualification_path = qualification(
        root, private / "sealed", state["candidate_sha"], state["manifest_sha256"]
    )
    notes = root / "RELEASE_NOTES" / f"Elpis{state['version']}.md"
    intent = {
        "schema": orchestrator.SCHEMA,
        "repository": REPOSITORY,
        "version": state["version"],
        "candidate_sha": state["candidate_sha"],
        "manifest_sha256": state["manifest_sha256"],
        "main_before": state["main_before"],
        "tagger": fixed_tagger(root, state, state_path),
        "qualification_sha256": sha256_bytes(qualification_path.read_bytes()),
        "notes_sha256": sha256_bytes(notes.read_bytes()),
    }
    if tuple(map(int, state["version"].split('.'))) >= (2, 2, 31):
        import importlib
        origin = importlib.import_module('tools.release_origin' if __package__ else 'release_origin')
        oid = os.environ.get("ELPIS_SIGNED_TAG_OBJECT", "")
        trust = os.environ.get("ELPIS_ALLOWED_SIGNERS")
        require(bool(oid), "SIGNED_TAG_OBJECT_REQUIRED_AFTER_QUALIFICATION")
        proof = origin.verify_tag(root, oid, state["candidate_sha"], f"Elpis{state['version']}", Path(trust) if trust else None)
        intent.update(schema=orchestrator.SIGNED_SCHEMA, signed_tag_object=oid,
                      allowed_signers_sha256=proof["allowed_signers_sha256"])
    intent_path = private / "intent.json"
    atomic_json(intent_path, intent)
    state["qualification_path"] = str(qualification_path)
    state["intent_path"] = str(intent_path)
    atomic_json(state_path, state)
    return intent_path, qualification_path


def ratification_record(root: Path, state: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    rows = publication.load_registry(root)["publication_assertions"]
    matches = [row for row in rows if row["version"] == state["version"]]
    require(len(matches) == 1, "PUBLICATION_ASSERTION_CARDINALITY")
    assertion = matches[0]
    value = {
        "schema": RATIFICATION_SCHEMA,
        "version": state["version"],
        "release_tag": f"Elpis{state['version']}",
        "sealed_commit": state["candidate_sha"],
        "manifest_sha256": state["manifest_sha256"],
        "publication_assertion_sha256": orchestrator.digest(assertion),
    }
    return root / "RELEASE_RATIFICATIONS" / f"Elpis{state['version']}.json", value


def ensure_closeout_commits(
    root: Path,
    state: dict[str, Any],
    state_path: Path,
    journal: OuterJournal,
) -> dict[str, Any]:
    candidate = state["candidate_sha"]

    if not state.get("assertion_commit"):
        head = git(root, "rev-parse", "HEAD")
        if head != candidate:
            require(git(root, "rev-parse", f"{head}^") == candidate, "ASSERTION_RECOVERY_PARENT_NONPASS")
            require(commit_paths(root, head) == ["PUBLICATION_ASSERTIONS.json"], "ASSERTION_RECOVERY_SCOPE_NONPASS")
            active = journal.active()
            require(
                journal.completed("assertion_commit")
                or (active is not None and active["stage"] == "assertion_commit"),
                "ASSERTION_COMMIT_EXISTS_WITHOUT_JOURNAL_INTENT",
            )
            journal.complete("assertion_commit", {"commit": head})
            state["assertion_commit"] = head
            atomic_json(state_path, state)
        else:
            status = git(root, "status", "--porcelain", "--untracked-files=all")
            require(
                status.splitlines() in (
                    [" M PUBLICATION_ASSERTIONS.json"],
                    ["M  PUBLICATION_ASSERTIONS.json"],
                ),
                "ASSERTION_COMMIT_SCOPE_NONPASS:" + status,
            )
            journal.begin("assertion_commit", {"parent": candidate, "path": "PUBLICATION_ASSERTIONS.json"})
            git(root, "add", "PUBLICATION_ASSERTIONS.json")
            proc = run(root, ["git", "commit", "-m", f"release: record Elpis{state['version']} publication assertion"])
            require(proc.returncode == 0, "ASSERTION_COMMIT_NONPASS:" + (proc.stdout or "")[-3000:])
            commit = git(root, "rev-parse", "HEAD")
            journal.returned("assertion_commit", {"commit": commit})
            require(git(root, "rev-parse", f"{commit}^") == candidate, "ASSERTION_COMMIT_PARENT_NONPASS")
            require(commit_paths(root, commit) == ["PUBLICATION_ASSERTIONS.json"], "ASSERTION_COMMIT_SCOPE_POSTCHECK_NONPASS")
            journal.complete("assertion_commit", {"commit": commit})
            state["assertion_commit"] = commit
            atomic_json(state_path, state)

    assertion_commit = state["assertion_commit"]
    if not state.get("ratification_commit"):
        path, value = ratification_record(root, state)
        expected_raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        head = git(root, "rev-parse", "HEAD")
        if head != assertion_commit:
            require(git(root, "rev-parse", f"{head}^") == assertion_commit, "RATIFICATION_RECOVERY_PARENT_NONPASS")
            require(commit_paths(root, head) == [path.relative_to(root).as_posix()], "RATIFICATION_RECOVERY_SCOPE_NONPASS")
            raw = subprocess.run(
                ["git", "show", f"{head}:{path.relative_to(root).as_posix()}"],
                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            require(raw.returncode == 0 and raw.stdout == expected_raw, "RATIFICATION_RECOVERY_BYTES_NONPASS")
            active = journal.active()
            require(
                journal.completed("ratification_commit")
                or (active is not None and active["stage"] == "ratification_commit"),
                "RATIFICATION_COMMIT_EXISTS_WITHOUT_JOURNAL_INTENT",
            )
            journal.complete("ratification_commit", {"commit": head})
            state["ratification_commit"] = head
            atomic_json(state_path, state)
        else:
            status = git(root, "status", "--porcelain", "--untracked-files=all")
            if path.exists():
                require(
                    journal.active() is not None
                    and journal.active()["stage"] == "ratification_commit",
                    "RATIFICATION_EXISTS_WITHOUT_JOURNAL_INTENT",
                )
                require(path.read_bytes() == expected_raw, "RATIFICATION_EXISTING_BYTES_NONPASS")
            else:
                require(not status, "WORKTREE_NOT_CLEAN_BEFORE_RATIFICATION:" + status)
                journal.begin(
                    "ratification_commit",
                    {"parent": assertion_commit, "path": path.relative_to(root).as_posix()},
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(expected_raw)
            git(root, "add", path.relative_to(root).as_posix())
            proc = run(root, ["git", "commit", "-m", f"release: ratify Elpis{state['version']} postpublication closeout"])
            require(proc.returncode == 0, "RATIFICATION_COMMIT_NONPASS:" + (proc.stdout or "")[-3000:])
            commit = git(root, "rev-parse", "HEAD")
            journal.returned("ratification_commit", {"commit": commit})
            require(git(root, "rev-parse", f"{commit}^") == assertion_commit, "RATIFICATION_COMMIT_PARENT_NONPASS")
            require(commit_paths(root, commit) == [path.relative_to(root).as_posix()], "RATIFICATION_COMMIT_SCOPE_POSTCHECK_NONPASS")
            journal.complete("ratification_commit", {"commit": commit})
            state["ratification_commit"] = commit
            atomic_json(state_path, state)
    clean_status(root)
    return state


def final_local_qualification(root: Path, private: Path) -> None:
    env = base_env()
    for name, argv in (
        ("terminal_publication", [sys.executable, "tools/publication_assertions_v2.py", "--check"]),
        ("terminal_verifier", [sys.executable, "tools/verify_public_release.py"]),
        ("terminal_root", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]),
    ):
        run_check(root, private, name, argv, env=env)
    clean_status(root)


def closeout_runs(
    root: Path, version: str, head: str, *, wait_seconds: int, poll_seconds: int
) -> dict[str, int]:
    boundary = orchestrator_io.LiveBoundary(root, Path("/dev/null"), execute=False)
    intent = {"repository": REPOSITORY, "version": version, "candidate_sha": head}
    deadline = time.monotonic() + wait_seconds
    while True:
        require(time.monotonic() <= deadline, "CLOSEOUT_WORKFLOWS_TIMEOUT")
        rows = boundary.workflows("MAIN_HOSTED_GREEN", intent)
        if rows is not None:
            return {key: int(row["run_id"]) for key, row in rows.items()}
        time.sleep(poll_seconds)


def ensure_final_push(
    root: Path,
    state: dict[str, Any],
    state_path: Path,
    journal: OuterJournal,
) -> dict[str, Any]:
    head = state["ratification_commit"]
    require(git(root, "rev-parse", "HEAD") == head, "LOCAL_HEAD_NOT_RATIFICATION")
    candidate = state["candidate_sha"]
    remote = remote_main(root)
    if state.get("final_main"):
        require(state["final_main"] == head and remote == head, "FINAL_MAIN_STATE_CONFLICT")
        return state

    journal.begin("final_main_push", {"expected_remote": candidate, "target": head})
    if remote == candidate:
        require(
            run(root, ["git", "merge-base", "--is-ancestor", candidate, head]).returncode == 0,
            "RATIFICATION_NOT_DESCENDANT_OF_SEAL",
        )
        proc = run(
            root,
            [
                "git", "push", "--porcelain", "--no-follow-tags",
                f"--force-with-lease=refs/heads/main:{candidate}",
                remote_url(), f"{head}:refs/heads/main",
            ],
        )
        require(proc.returncode == 0, "FINAL_MAIN_PUSH_NONPASS:" + (proc.stdout or "")[-3000:])
        journal.returned("final_main_push", {"push_returncode": 0, "target": head})
        remote = remote_main(root)
    elif remote == head:
        active = journal.active()
        require(
            journal.completed("final_main_push")
            or (active is not None and active["stage"] == "final_main_push"),
            "REMOTE_ALREADY_AT_FINAL_WITHOUT_JOURNAL_INTENT",
        )
    else:
        raise FullReleaseError("REMOTE_MAIN_CONFLICT_AT_CLOSEOUT:" + remote)

    require(remote == head, "FINAL_MAIN_PUSH_NOT_OBSERVED")
    journal.complete("final_main_push", {"remote_main": head})
    state["final_main"] = head
    atomic_json(state_path, state)
    return state


def plan(root: Path) -> dict[str, Any]:
    return {
        "mode": "DRY_RUN_NO_COMMANDS",
        "version": current_version(root),
        "command": "python tools/full_release.py --execute",
        "stages": [
            "preseal_qualification",
            "seal_v3_and_commit",
            "exact_sealed_qualification",
            "release_orchestrator_through_publication_assertion",
            "publication_assertion_commit",
            "separate_ratification_commit",
            "terminal_local_verification",
            "final_main_fast_forward",
            "required_closeout_hosted_workflows",
            "terminal_closed_receipt",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--wait-seconds", type=int, default=3600)
    ap.add_argument("--poll-seconds", type=int, default=15)
    args = ap.parse_args(argv)
    root = args.root.resolve()

    if not args.execute:
        print(json.dumps(plan(root), indent=2))
        return 0

    try:
        # Bind the interpreter and complete locked dependency graph before any
        # local release mutation or external observation/publication.
        environment = environment_authority(root)
        require(args.wait_seconds > 0, "WAIT_SECONDS_INVALID")
        require(1 <= args.poll_seconds <= 60, "POLL_SECONDS_INVALID")
        version = current_version(root)
        common = git_common_dir(root) / "elpis-full-release-v1"
        common.mkdir(parents=True, exist_ok=True)
        with publication._exclusive_lock(common / "full-release.lock"):
            private = state_dir(root, version)
            path = private / "state.json"
            private.mkdir(parents=True, exist_ok=True)
            journal = OuterJournal(private / "journal.json")

            if path.exists():
                state = json.loads(path.read_text(encoding="utf-8"))
                require(
                    state.get("schema") == SCHEMA and state.get("version") == version,
                    "FULL_RELEASE_STATE_CONFLICT",
                )
                require(state.get("environment") == environment, "FULL_RELEASE_ENVIRONMENT_CHANGED")
            else:
                clean_status(root)
                state = {
                    "schema": SCHEMA,
                    "version": version,
                    "environment": environment,
                    "development_sha": git(root, "rev-parse", "HEAD"),
                    "main_before": remote_main(root),
                    "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                }
                atomic_json(path, state)

            state = ensure_preseal_qualified(root, private, state, path)
            state = ensure_sealed(root, state, path, journal)
            intent_path, qualification_path = ensure_intent(root, private, state, path)

            if not state.get("orchestrator_closed"):
                proc = run(
                    root,
                    [
                        sys.executable, "tools/release_orchestrator.py",
                        "--intent", str(intent_path),
                        "--qualification", str(qualification_path),
                        "--execute",
                        "--wait-seconds", str(args.wait_seconds),
                        "--poll-seconds", str(args.poll_seconds),
                    ],
                )
                if proc.returncode == 75:
                    print(proc.stdout or "", end="")
                    return 75
                require(proc.returncode == 0, "RELEASE_ORCHESTRATOR_NONPASS:" + (proc.stdout or "")[-5000:])
                (private / "orchestrator.log").write_text(proc.stdout or "", encoding="utf-8")
                state["orchestrator_closed"] = True
                atomic_json(path, state)

            state = ensure_closeout_commits(root, state, path, journal)
            final_local_qualification(root, private)
            state = ensure_final_push(root, state, path, journal)
            runs = closeout_runs(
                root,
                version,
                state["final_main"],
                wait_seconds=args.wait_seconds,
                poll_seconds=args.poll_seconds,
            )

            require(remote_main(root) == state["final_main"], "TERMINAL_MAIN_MISMATCH")
            env = base_env()
            for argv, diagnostic in (
                ([sys.executable, "tools/publication_assertions_v2.py", "--check"], "TERMINAL_PUBLICATION_NONPASS"),
                ([sys.executable, "tools/verify_public_release.py"], "TERMINAL_VERIFIER_NONPASS"),
            ):
                proc = run(root, argv, env=env)
                require(proc.returncode == 0, diagnostic + ":" + (proc.stdout or "")[-3000:])
            clean_status(root)

            closed = {
                "schema": TERMINAL_SCHEMA,
                "version": version,
                "release_tag": f"Elpis{version}",
                "development_sha": state["development_sha"],
                "sealed_commit": state["candidate_sha"],
                "assertion_commit": state["assertion_commit"],
                "ratification_commit": state["ratification_commit"],
                "final_public_main": state["final_main"],
                "manifest_sha256": state["manifest_sha256"],
                "preseal_qualification_sha256": state["preseal_qualification_sha256"],
                "closeout_hosted_runs": runs,
            }
            atomic_json(private / "CLOSED.json", closed)
            state["terminal_closed"] = True
            state["closeout_hosted_runs"] = runs
            atomic_json(path, state)
            print(json.dumps(closed, indent=2, sort_keys=True))
            return 0
    except (FullReleaseError, orchestrator.ReleaseError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("FULL_RELEASE_NONPASS:" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
