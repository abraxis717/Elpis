import hashlib
import json
from pathlib import Path

import pytest

from tools import release_orchestrator as machine
from tools import release_orchestrator_io as io


VERSION = "2.2.32"


def artifact_set(wheel_sha="a" * 64, sdist_sha="b" * 64):
    return [
        {
            "filename":
                "elpisai-2.2.32-py3-none-any.whl",
            "packagetype": "bdist_wheel",
            "sha256": wheel_sha,
        },
        {
            "filename": "elpisai-2.2.32.tar.gz",
            "packagetype": "sdist",
            "sha256": sdist_sha,
        },
    ]


def qualification(tmp_path):
    value = {
        "schema":
            "elpis.release-orchestrator.qualification.v2",
        "candidate_sha": "1" * 40,
        "manifest_sha256": "2" * 64,
        "environment": {},
        "checks": {
            "installed_artifact": {
                "argv": ["fixture"],
                "exit_code": 0,
                "output_sha256": "3" * 64,
                "artifacts": artifact_set(),
            }
        },
    }
    path = tmp_path / "qualification.json"
    path.write_text(json.dumps(value))
    return path


def intent(path):
    return {
        "schema": machine.SIGNED_SCHEMA,
        "version": VERSION,
        "qualification_sha256":
            hashlib.sha256(path.read_bytes()).hexdigest(),
    }


class Runner:
    def __init__(self, artifacts):
        self.artifacts = artifacts

    def http_json(self, url):
        urls = []
        for item in self.artifacts:
            urls.append(
                {
                    "filename": item["filename"],
                    "packagetype": item["packagetype"],
                    "upload_time_iso_8601":
                        "2026-09-24T09:00:00Z",
                    "yanked": False,
                    "digests": {
                        "sha256": item["sha256"],
                    },
                }
            )
        return {
            "info": {
                "name": "elpisai",
                "version": VERSION,
            },
            "urls": urls,
        }


def test_qualified_distribution_identity_accepts_exact_pair(
    tmp_path,
):
    report = json.loads(
        qualification(tmp_path).read_text()
    )
    assert io.qualified_distribution_artifacts(
        report,
        VERSION,
    ) == artifact_set()


def test_pypi_observation_accepts_exact_qualified_bytes(
    tmp_path,
):
    q = qualification(tmp_path)
    boundary = io.LiveBoundary(
        tmp_path,
        q,
        runner=Runner(artifact_set()),
    )

    observed = boundary.observe(
        "PYPI_EXTERNALLY_OBSERVED",
        intent(q),
        {},
    )

    assert [
        {
            "filename": item["filename"],
            "packagetype": item["packagetype"],
            "sha256": item["sha256"],
        }
        for item in observed["files"]
    ] == artifact_set()


def test_pypi_observation_rejects_wheel_hash_drift(
    tmp_path,
):
    q = qualification(tmp_path)
    boundary = io.LiveBoundary(
        tmp_path,
        q,
        runner=Runner(
            artifact_set(wheel_sha="f" * 64)
        ),
    )

    with pytest.raises(
        machine.ReleaseError,
        match="PYPI_ARTIFACT_IDENTITY_MISMATCH",
    ):
        boundary.observe(
            "PYPI_EXTERNALLY_OBSERVED",
            intent(q),
            {},
        )


def test_pypi_observation_rejects_missing_distribution(
    tmp_path,
):
    q = qualification(tmp_path)
    boundary = io.LiveBoundary(
        tmp_path,
        q,
        runner=Runner(artifact_set()[:1]),
    )

    with pytest.raises(
        machine.ReleaseError,
        match="PYPI_ARTIFACT_IDENTITY_MISMATCH",
    ):
        boundary.observe(
            "PYPI_EXTERNALLY_OBSERVED",
            intent(q),
            {},
        )


def test_workflow_and_local_builder_share_source_date_epoch():
    workflow = Path(
        ".github/workflows/pypi-publish.yaml"
    ).read_text()
    local = Path("tools/full_release.py").read_text()

    assert "SOURCE_DATE_EPOCH" in workflow
    assert "SOURCE_DATE_EPOCH" in local
    assert (
        'python tools/release_git_cli.py show -s --format=%ct "${RELEASE_TAG}^{}"'
        in workflow
    )
    assert '"--format=%ct"' in local


def test_pypi_workflow_verifies_authority_before_upload():
    workflow = Path(
        ".github/workflows/pypi-publish.yaml"
    ).read_text()

    verify_at = workflow.index(
        "- name: Verify exact qualified distribution authority"
    )
    upload_at = workflow.index(
        "- name: Upload distributions for isolated publish job"
    )
    publish_at = workflow.index(
        "- name: Publish package distributions to PyPI"
    )

    assert verify_at < upload_at < publish_at
    assert "workflow_dispatch:" not in workflow
    assert "github.event.release.body" in workflow
    assert "tools/release_distributions.py verify" in workflow
