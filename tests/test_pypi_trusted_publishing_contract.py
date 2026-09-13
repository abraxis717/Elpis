from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pypi-publish.yaml"


def _text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_trusted_publisher_identity_and_oidc_boundary():
    text = _text()

    assert "release:" in text
    assert "types: [published]" in text
    assert "workflow_dispatch:" in text
    assert "release_tag:" in text
    assert "required: true" in text
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
    text = _text()
    assert "\n  build:\n" in text
    assert "\n  publish:\n" in text
    assert "needs: build" in text
    assert "permissions: {}" in text


def test_release_and_recovery_events_resolve_one_required_immutable_tag():
    text = _text()
    assert "RELEASE_TAG: ${{ github.event.release.tag_name || inputs.release_tag }}" in text
    assert "ref: ${{ env.RELEASE_TAG }}" in text
    assert "fetch-depth: 0" in text
    assert 'test -n "${RELEASE_TAG}"' in text
    assert 'test "Elpis$(cat VERSION)" = "${RELEASE_TAG}"' in text
    assert 'test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 "${RELEASE_TAG}")"' in text


def test_build_input_is_immutable_git_archive_not_mutable_checkout():
    text = _text()

    assert 'git archive --format=tar "${RELEASE_TAG}"' in text
    assert '"${RUNNER_TEMP}/elpis-release-tree"' in text
    assert 'test ! -e "${release_tree}/.git"' in text
    assert 'cd "${RUNNER_TEMP}/elpis-release-tree"' in text

    identity_at = text.index("- name: Verify checked-out tag identity")
    repo_identity_at = text.index("- name: Verify repository release identity")
    export_at = text.index("- name: Export immutable release tree")
    verify_at = text.index("- name: Verify exported public release")
    build_at = text.index("- name: Build distributions from immutable export")
    check_at = text.index("- name: Check distributions")
    assert identity_at < repo_identity_at < export_at < verify_at < build_at < check_at

    assert text.count("python -m build") == 1
    assert (
        'python -m build --outdir '
        '"${RUNNER_TEMP}/python-package-distributions"'
    ) in text


def test_malformed_release_event_identity_command_is_gone():
    text = _text()
    assert 'git rev-list -n 1 "${{ github.event.release.tag_name }})' not in text
    assert '$(git rev-list -n 1 "${RELEASE_TAG}")' in text


def test_publish_job_still_consumes_only_uploaded_build_artifact():
    text = _text()

    publish = text.split("\n  publish:\n", 1)[1]
    assert "actions/checkout" not in publish
    assert "git archive" not in publish
    assert "python -m build" not in publish
    assert "actions/download-artifact@v4" in publish
    assert "pypa/gh-action-pypi-publish@release/v1" in publish
