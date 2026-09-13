from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

CI = ROOT / ".github/workflows/ci.yml"
REFERENCE = ROOT / ".github/workflows/reference-runtime.yml"
COMPONENT = ROOT / ".github/workflows/component-attribution.yml"
PLATFORM = ROOT / ".github/workflows/platform-matrix.yml"
PYPI = ROOT / ".github/workflows/pypi-publish.yaml"
POLICY = ROOT / "docs/RELEASE_GUARD_POLICY.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_all_public_main_push_workflows_are_explicit() -> None:
    for path in (CI, REFERENCE, COMPONENT, PLATFORM):
        text = _text(path)
        assert "  push:\n" in text
        assert "      - main\n" in text


def test_main_push_verification_does_not_require_future_tag() -> None:
    ci = _text(CI)
    reference = _text(REFERENCE)

    assert "python tools/verify_public_release.py" in ci
    assert "python tools/verify_public_release.py" in reference

    # The strict tag proof exists in CI, but it must be guarded to tag refs.
    strict = (
        "python tools/verify_public_release.py "
        "--verify-repository-identity"
    )
    assert strict in ci
    strict_at = ci.index(strict)
    guard_at = ci.rfind(
        "if: startsWith(github.ref, 'refs/tags/')",
        0,
        strict_at,
    )
    assert guard_at != -1

    # Reference-runtime uses only the tag-aware default verifier, so a
    # pre-tag main push cannot be blocked solely by a future tag.
    assert strict not in reference


def test_ci_explicitly_proves_candidate_identity_on_main_push() -> None:
    ci = _text(CI)
    candidate = (
        "python tools/verify_public_release.py "
        "--verify-candidate-repository-identity"
    )
    assert candidate in ci
    at = ci.index(candidate)
    guard = ci.rfind(
        "if: github.event_name == 'push' && "
        "github.ref == 'refs/heads/main'",
        0,
        at,
    )
    assert guard != -1


def test_release_event_keeps_strict_identity_before_build() -> None:
    text = _text(PYPI)
    assert "  release:\n" in text
    assert "    types: [published]\n" in text

    strict = (
        "python tools/verify_public_release.py "
        "--verify-repository-identity"
    )
    assert strict in text
    assert text.index(strict) < text.index(
        "- name: Export immutable release tree"
    )


def test_ci_runs_fast_lifecycle_contracts_in_verify_job() -> None:
    text = _text(CI)
    assert "tests/test_release_repository_identity.py" in text
    assert "tests/test_release_lifecycle_ordering.py" in text
    assert "tests/test_release_tag_qualification.py" in text


def test_policy_orders_push_before_tag_and_strict_tag_before_release() -> None:
    text = _text(POLICY)
    push = text.index("2. Push the exact qualified candidate commit")
    tag = text.index("3. Create the annotated release tag")
    release = text.index("5. Publish the GitHub Release")
    assert push < tag < release
    assert "candidate repository identity" in text
    assert "strict tagged repository identity" in text


def _workflow_job_blocks(text: str):
    try:
        jobs = text.split("\njobs:\n", 1)[1]
    except IndexError as exc:
        raise AssertionError("workflow jobs block absent") from exc

    matches = list(
        re.finditer(
            r"(?m)^  ([A-Za-z0-9_-]+):\n",
            jobs,
        )
    )
    for index, match in enumerate(matches):
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(jobs)
        )
        yield match.group(1), jobs[start:end]


def test_every_repository_verifier_workflow_job_fetches_full_git_history() -> None:
    workflow_dir = ROOT / ".github/workflows"
    proof_jobs = []

    for path in sorted(workflow_dir.glob("*.y*ml")):
        workflow = _text(path)
        for job_name, block in _workflow_job_blocks(workflow):
            if "verify_public_release.py" not in block:
                continue
            proof_jobs.append((path.name, job_name))
            assert "uses: actions/checkout@v4" in block, (
                path.name,
                job_name,
            )
            assert "fetch-depth: 0" in block, (
                f"{path.name}/{job_name}: "
                "repository identity proof requires full Git history"
            )
            assert "fetch-depth: 1" not in block, (
                path.name,
                job_name,
            )

    assert sorted(proof_jobs) == [
        ("ci.yml", "verify"),
        ("pypi-publish.yaml", "build"),
        ("reference-runtime.yml", "reference-runtime-smoke"),
    ]
