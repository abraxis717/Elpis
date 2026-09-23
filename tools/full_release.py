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
from typing import Any

try:
    from tools import publication_assertions_v2 as publication
    from tools import release_orchestrator as orchestrator
except ModuleNotFoundError:
    import publication_assertions_v2 as publication
    import release_orchestrator as orchestrator

SCHEMA = "elpis.full-release.state.v1"
RATIFICATION_SCHEMA = "elpis.release-ratification.v1"
TERMINAL_SCHEMA = "elpis.full-release.closed.v1"
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


def git(root: Path, *args: str) -> str:
    proc = run(root, ["git", *args])
    require(proc.returncode == 0, "GIT_NONPASS:" + " ".join(args) + ":" + (proc.stdout or "")[-3000:])
    return (proc.stdout or "").strip()


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


def remote_main(root: Path) -> str:
    out = git(root, "ls-remote", "origin", "refs/heads/main")
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
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *authority["locus"]["paths"]],
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


def qualification(root: Path, private: Path, candidate: str, manifest_sha: str) -> Path:
    env = base_env()
    checks = {
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
        "installed_artifact": run_check(
            root, private, "installed_artifact",
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *INSTALLED_ARTIFACT_TESTS],
            env=env,
        ),
        "native": native_check(root, private, env=env),
    }
    report = {
        "schema": "elpis.release-orchestrator.qualification.v1",
        "candidate_sha": candidate,
        "manifest_sha256": manifest_sha,
        "checks": checks,
    }
    path = private / "qualification.json"
    atomic_json(path, report)
    return path


def ensure_sealed(root: Path, state: dict[str, Any], state_path: Path) -> dict[str, Any]:
    version = state["version"]
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
        return state

    clean_status(root)
    require(not manifest.exists(), "MANIFEST_ALREADY_EXISTS_WITHOUT_FULL_RELEASE_STATE")
    proc = run(root, [sys.executable, "tools/seal_release.py", "--version", version, "--schema", "v3"], env=base_env())
    require(proc.returncode == 0, "SEAL_NONPASS:" + (proc.stdout or "")[-5000:])
    status = git(root, "status", "--porcelain", "--untracked-files=all")
    require(status.splitlines() == [f"?? {manifest_rel.as_posix()}"], "SEAL_SCOPE_NONPASS:" + status)
    git(root, "add", manifest_rel.as_posix())
    proc = run(root, ["git", "commit", "-m", f"release: seal Elpis{version} v3 manifest"])
    require(proc.returncode == 0, "SEAL_COMMIT_NONPASS:" + (proc.stdout or "")[-5000:])
    state["candidate_sha"] = git(root, "rev-parse", "HEAD")
    state["manifest_sha256"] = sha256_bytes(manifest.read_bytes())
    atomic_json(state_path, state)
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
        root, private, state["candidate_sha"], state["manifest_sha256"]
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


def ensure_closeout_commits(root: Path, state: dict[str, Any], state_path: Path) -> dict[str, Any]:
    if not state.get("assertion_commit"):
        status = git(root, "status", "--porcelain", "--untracked-files=all")
        require(status.splitlines() == [" M PUBLICATION_ASSERTIONS.json"], "ASSERTION_COMMIT_SCOPE_NONPASS:" + status)
        git(root, "add", "PUBLICATION_ASSERTIONS.json")
        proc = run(root, ["git", "commit", "-m", f"release: record Elpis{state['version']} publication assertion"])
        require(proc.returncode == 0, "ASSERTION_COMMIT_NONPASS:" + (proc.stdout or "")[-3000:])
        state["assertion_commit"] = git(root, "rev-parse", "HEAD")
        atomic_json(state_path, state)

    if not state.get("ratification_commit"):
        clean_status(root)
        path, value = ratification_record(root, state)
        require(not path.exists(), "RATIFICATION_ALREADY_EXISTS_WITHOUT_STATE")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        git(root, "add", path.relative_to(root).as_posix())
        proc = run(root, ["git", "commit", "-m", f"release: ratify Elpis{state['version']} postpublication closeout"])
        require(proc.returncode == 0, "RATIFICATION_COMMIT_NONPASS:" + (proc.stdout or "")[-3000:])
        state["ratification_commit"] = git(root, "rev-parse", "HEAD")
        atomic_json(state_path, state)
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


def closeout_runs(root: Path, version: str, head: str, *, wait_seconds: int, poll_seconds: int) -> dict[str, int]:
    workflows = orchestrator.required_workflows({"version": version})
    deadline = time.monotonic() + wait_seconds
    pending = dict(workflows)
    result: dict[str, int] = {}
    while pending:
        require(time.monotonic() <= deadline, "CLOSEOUT_WORKFLOWS_TIMEOUT:" + ",".join(sorted(pending)))
        for key, (name, path) in list(pending.items()):
            proc = run(
                root,
                [
                    "gh", "api", "-X", "GET",
                    f"repos/{REPOSITORY}/actions/workflows/{path}/runs"
                    f"?head_sha={head}&event=push&per_page=100",
                ],
            )
            require(proc.returncode == 0, f"CLOSEOUT_GH_API_NONPASS:{key}:" + (proc.stdout or "")[-2000:])
            payload = json.loads(proc.stdout or "{}")
            rows = [
                row for row in payload.get("workflow_runs", [])
                if row.get("head_sha") == head
                and row.get("head_branch") == "main"
                and row.get("event") == "push"
                and row.get("name") == name
            ]
            require(len(rows) <= 1, f"CLOSEOUT_WORKFLOW_AMBIGUOUS:{key}")
            if not rows:
                continue
            row = rows[0]
            require(row.get("run_attempt") == 1, f"CLOSEOUT_RERUN_FORBIDDEN:{key}")
            if row.get("status") != "completed":
                continue
            require(row.get("conclusion") == "success", f"CLOSEOUT_WORKFLOW_FAILED:{key}:{row.get('conclusion')}")
            result[key] = int(row["id"])
            del pending[key]
        if pending:
            time.sleep(poll_seconds)
    return result


def ensure_final_push(root: Path, state: dict[str, Any], state_path: Path) -> dict[str, Any]:
    head = state["ratification_commit"]
    require(git(root, "rev-parse", "HEAD") == head, "LOCAL_HEAD_NOT_RATIFICATION")
    candidate = state["candidate_sha"]
    remote = remote_main(root)
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
                "origin", f"{head}:refs/heads/main",
            ],
        )
        require(proc.returncode == 0, "FINAL_MAIN_PUSH_NONPASS:" + (proc.stdout or "")[-3000:])
    else:
        require(remote == head, "REMOTE_MAIN_CONFLICT_AT_CLOSEOUT:" + remote)
    state["final_main"] = head
    atomic_json(state_path, state)
    return state


def plan(root: Path) -> dict[str, Any]:
    return {
        "mode": "DRY_RUN_NO_COMMANDS",
        "version": current_version(root),
        "command": "python tools/full_release.py --execute",
        "stages": [
            "seal_v3_and_commit",
            "local_qualification",
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
        require(args.wait_seconds > 0, "WAIT_SECONDS_INVALID")
        require(1 <= args.poll_seconds <= 60, "POLL_SECONDS_INVALID")
        version = current_version(root)
        private = state_dir(root, version)
        path = private / "state.json"
        private.mkdir(parents=True, exist_ok=True)

        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8"))
            require(state.get("schema") == SCHEMA and state.get("version") == version, "FULL_RELEASE_STATE_CONFLICT")
        else:
            clean_status(root)
            state = {
                "schema": SCHEMA,
                "version": version,
                "main_before": remote_main(root),
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            atomic_json(path, state)

        state = ensure_sealed(root, state, path)
        intent_path, qualification_path = ensure_intent(root, private, state, path)

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

        state = ensure_closeout_commits(root, state, path)
        final_local_qualification(root, private)
        state = ensure_final_push(root, state, path)
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
            "sealed_commit": state["candidate_sha"],
            "assertion_commit": state["assertion_commit"],
            "ratification_commit": state["ratification_commit"],
            "final_public_main": state["final_main"],
            "manifest_sha256": state["manifest_sha256"],
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
