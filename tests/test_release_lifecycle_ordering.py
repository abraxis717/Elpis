from __future__ import annotations

from pathlib import Path
import ast
import json
import re
import runpy


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

    # Development source is checked in place and cannot borrow a historical
    # tag's green result. Tag events still verify exact physical payload.
    assert strict not in reference
    assert "python tools/verify_public_release.py --development" in reference
    assert "git worktree add" not in reference
    assert "python tools/verify_public_release.py --candidate" in reference


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


def test_ci_verify_job_is_bytecode_free() -> None:
    blocks = dict(_workflow_job_blocks(_text(CI)))
    verify = blocks["verify"]
    assert "PYTHONDONTWRITEBYTECODE: '1'" in verify
    assert "PYTHONNOUSERSITE: '1'" in verify
    assert "pip install --require-hashes --only-binary=:all: -r qualification/locks/test-tools-py311-py312.lock" in verify


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
            assert "uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in block, (
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
        ("ci.yml", "release-integrity"),
        ("ci.yml", "verify"),
        ("pypi-publish.yaml", "build"),
        ("reference-runtime.yml", "reference-runtime-smoke"),
    ]


def test_tag_sensitive_workflows_restore_annotated_tag_objects() -> None:
    ci = _text(CI)
    reference = _text(REFERENCE)
    pypi = _text(PYPI)

    ci_fetch = (
        'git fetch --force --no-tags origin '
        '"refs/tags/${RELEASE_TAG}:refs/tags/${RELEASE_TAG}"'
    )
    ci_type = (
        'test "$(git cat-file -t "refs/tags/${RELEASE_TAG}")" = "tag"'
    )
    ci_verify = "python tools/verify_public_release.py"
    assert ci_fetch in ci
    assert ci_type in ci
    assert ci.index(ci_fetch) < ci.index(ci_verify)

    reference_fetch = (
        'git fetch --force --no-tags origin '
        '"refs/tags/${release_tag}:refs/tags/${release_tag}"'
    )
    reference_type = (
        'test "$(git cat-file -t "refs/tags/${release_tag}")" = "tag"'
    )
    assert reference_fetch in reference
    assert reference_type in reference
    assert reference.index(reference_fetch) < reference.index(
        "python tools/verify_public_release.py"
    )

    pypi_fetch = (
        'git fetch --force --no-tags origin '
        '"refs/tags/${RELEASE_TAG}:refs/tags/${RELEASE_TAG}"'
    )
    pypi_type = (
        'test "$(git cat-file -t "refs/tags/${RELEASE_TAG}")" = "tag"'
    )
    strict = (
        "python tools/verify_public_release.py "
        "--verify-repository-identity"
    )
    assert pypi_fetch in pypi
    assert pypi_type in pypi
    assert pypi.index(pypi_fetch) < pypi.index(strict)




def test_publication_closeout_uses_v2_and_freezes_v1() -> None:
    text = _text(POLICY)

    # Policy prose is Markdown and may be line-wrapped without changing
    # semantics. Test normalized prose rather than physical line layout.
    normalized = " ".join(text.split())

    required = (
        "`PUBLISHED_RELEASES.json` is frozen legacy v1",
        "`PUBLICATION_ASSERTIONS.json`",
        "`--append-tag` is no longer",
        "external-observation receipt",
        "annotated tag object",
        "peeled commit",
        "release manifest bytes",
        "Git-less release export",
        "performs no network discovery itself",
    )

    for phrase in required:
        assert phrase in normalized, phrase
def test_release_wide_mutation_suite_requires_unpublished_successor(
    tmp_path,
    capsys,
) -> None:
    ns = runpy.run_path(
        str(
            ROOT
            / "tools/mutation_suite.py"
        )
    )

    gate = ns[
        "_mutation_suite_version_gate"
    ]

    fixture = tmp_path / "repo"
    fixture.mkdir()

    (
        fixture
        / "PUBLISHED_RELEASES.json"
    ).write_text(
        json.dumps({
            "published_releases": [
                {"version": "9.9.8"}
            ],
        })
        + "\n"
    )

    (
        fixture
        / "PUBLICATION_ASSERTIONS.json"
    ).write_text(
        json.dumps({
            "publication_assertions": [
                {"version": "9.9.9"}
            ],
        })
        + "\n"
    )

    (
        fixture / "VERSION"
    ).write_text("9.9.9\n")

    assert gate(fixture) == (
        "MUTATION_SUITE_REQUIRES_"
        "UNPUBLISHED_SUCCESSOR_VERSION:"
        "9.9.9"
    )

    (
        fixture / "VERSION"
    ).write_text("10.0.0\n")

    assert gate(fixture) is None

    main = ns["main"]

    main.__globals__[
        "_mutation_suite_version_gate"
    ] = lambda root: (
        "SYNTHETIC_LIFECYCLE_BLOCK"
    )

    assert main([]) == 2

    assert (
        "SYNTHETIC_LIFECYCLE_BLOCK"
        in capsys.readouterr().out
    )


def test_excluded_registry_mutations_do_not_reseal_before_guard_execution() -> None:
    tree = ast.parse(
        (
            ROOT
            / "tools/mutation_suite.py"
        ).read_text()
    )

    funcs = {
        node.name: node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    for name in (
        "m17_mutate_frozen_legacy_publication_registry",
        "m18_forge_gitless_v2_successor_append",
    ):
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "_reseal"
            for node in ast.walk(
                funcs[name]
            )
        )
