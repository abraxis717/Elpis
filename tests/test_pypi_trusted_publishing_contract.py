from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pypi-publish.yaml"


def test_trusted_publisher_identity_and_oidc_boundary():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "release:" in text
    assert "types: [published]" in text
    assert "name: pypi" in text
    assert "id-token: write" in text
    assert "pypa/gh-action-pypi-publish@release/v1" in text
    assert "python-package-distributions" in text

    forbidden = (
        "TWINE_PASSWORD",
        "PYPI_TOKEN",
        "password:",
        "secrets.",
    )
    for marker in forbidden:
        assert marker not in text


def test_publish_job_is_separate_from_build_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "\n  build:\n" in text
    assert "\n  publish:\n" in text
    assert "needs: build" in text
    assert "permissions: {}" in text


def test_build_input_is_immutable_git_archive_not_mutable_checkout():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'git archive --format=tar "${{ github.event.release.tag_name }}"' in text
    assert '"${RUNNER_TEMP}/elpis-release-tree"' in text
    assert 'test ! -e "${release_tree}/.git"' in text
    assert 'cd "${RUNNER_TEMP}/elpis-release-tree"' in text

    # Verification and build both occur after the immutable export step.
    export_at = text.index("- name: Export immutable release tree")
    verify_at = text.index("- name: Verify exported public release")
    build_at = text.index("- name: Build distributions from immutable export")
    assert export_at < verify_at < build_at

    # There is exactly one package build invocation and it emits outside both
    # the mutable checkout and the exported source tree.
    assert text.count("python -m build") == 1
    assert (
        'python -m build --outdir '
        '"${RUNNER_TEMP}/python-package-distributions"'
    ) in text


def test_release_tag_identity_is_checked_before_archive_export():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        'test "$(git rev-parse HEAD)" = '
        '"$(git rev-list -n 1 "${{ github.event.release.tag_name }})"'
    ) in text
    identity_at = text.index("- name: Verify checked-out tag identity")
    export_at = text.index("- name: Export immutable release tree")
    assert identity_at < export_at


def test_publish_job_still_consumes_only_uploaded_build_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")

    publish = text.split("\n  publish:\n", 1)[1]
    assert "actions/checkout" not in publish
    assert "git archive" not in publish
    assert "python -m build" not in publish
    assert "actions/download-artifact@v4" in publish
    assert "pypa/gh-action-pypi-publish@release/v1" in publish
