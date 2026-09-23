from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.28"
TAG = "Elpis2.2.28"
MANIFEST_REL = "manifests/Elpis2.2.28.RELEASE_MANIFEST.json"


def test_228_active_successor_identity_is_atomic_and_manifest_lifecycle():
    assert (ROOT / "VERSION").read_text().strip() == VERSION
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["name"] == "elpisai"
    assert pyproject["project"]["version"] == VERSION
    assert f'version: "{VERSION}"' in (ROOT / "CITATION.cff").read_text()
    readme = (ROOT / "README.md").read_text()
    assert f"**Release line: Elpis{VERSION}**" in readme
    assert f"RELEASE_NOTES/Elpis{VERSION}.md" in readme
    assert (ROOT / f"RELEASE_NOTES/Elpis{VERSION}.md").is_file()
    assert (ROOT / "CHANGELOG.md").read_text().startswith(f"## Elpis{VERSION}")
    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == VERSION
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }
    manifest = ROOT / MANIFEST_REL
    if not manifest.exists():
        return
    data = json.loads(manifest.read_text())
    assert data["schema"] == "elpis.release-manifest.v3"
    assert data["package_name"] == "elpisai"
    assert data["version"] == VERSION
    assert data["release_name"] == TAG
    assert data["release_tag"] == TAG
    assert data["publication_policy"] == "elpis.publication-membership.v2"
    assert data["tree_digest_algorithm"] == "elpis.publication-tree.sha256.v1"
    assert data["full_elpis_runtime_admission"] is True
    assert data["execution_authorized"] is False
    assert data["generated_source_executed"] is False
    assert data["experiments_shipped"] is False
    assert data["output_authority_granted"] == 0
    assert data["request_guidance_gate_default"] is False
    assert data["validation_authority_propagated"] is False
    assert isinstance(data["publication_tree_sha256"], str)
    assert len(data["publication_tree_sha256"]) == 64
    assert isinstance(data["file_count"], int) and data["file_count"] > 0

def test_228_manifest_is_predeclared_write_once_only():
    immutable = json.loads(
        (ROOT / "tools/immutable_evidence_baseline_v1.json").read_text()
    )
    assert immutable["write_once_paths"][MANIFEST_REL] == {
        "release": TAG,
        "rule": "FIRST_COMMITTED_BLOB_IMMUTABLE",
    }

    temporality = json.loads(
        (ROOT / "tools/runtime_admission_temporality_v1.json").read_text()
    )
    expected = {
        "byte_authority": "FIRST_COMMITTED_BLOB_IMMUTABLE",
        "category": "HISTORICAL_RELEASE_SNAPSHOT",
        "locator": "/full_elpis_runtime_admission",
        "path": MANIFEST_REL,
        "qualname": "<json>",
        "release": TAG,
        "syntax": "json_key",
        "value": True,
    }
    assert expected in temporality["future_write_once_declarations"]


def test_228_native_is_required_by_orchestrator_and_publication_authority():
    from tools import publication_assertions_v2 as pub
    from tools import release_orchestrator as orch

    intent = {"version": VERSION}
    assert "main_inference_native" in orch.action_specs("MAIN_HOSTED_GREEN", intent)
    assert "tag_inference_native" in orch.action_specs("TAG_HOSTED_GREEN", intent)
    assert pub.required_actions(TAG)["tag_inference_native"] == (
        "inference-native-r0",
        "push",
    )


def test_228_publication_fact_is_append_only_and_exact_after_closeout():
    assertions = json.loads((ROOT / "PUBLICATION_ASSERTIONS.json").read_text())["publication_assertions"]
    rows = [row for row in assertions if row.get("version") == VERSION]
    assert len(rows) == 1
    expected = {'github_actions': {'pypi_publish': {'conclusion': 'success',
                                     'event': 'release',
                                     'head_sha': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
                                     'run_id': 35777050145,
                                     'workflow': 'pypi-publish'},
                    'release_event_ci': {'conclusion': 'success',
                                         'event': 'release',
                                         'head_sha': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
                                         'run_id': 35777050048,
                                         'workflow': 'CI'},
                    'tag_ci': {'conclusion': 'success',
                               'event': 'push',
                               'head_sha': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
                               'run_id': 35776230055,
                               'workflow': 'CI'},
                    'tag_component_attribution': {'conclusion': 'success',
                                                  'event': 'push',
                                                  'head_sha': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
                                                  'run_id': 35776229993,
                                                  'workflow': 'Component attribution'},
                    'tag_inference_native': {'conclusion': 'success',
                                             'event': 'push',
                                             'head_sha': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
                                             'run_id': 35776229995,
                                             'workflow': 'inference-native-r0'},
                    'tag_platform_matrix': {'conclusion': 'success',
                                            'event': 'push',
                                            'head_sha': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
                                            'run_id': 35776229983,
                                            'workflow': 'platform-matrix'},
                    'tag_reference_runtime': {'conclusion': 'success',
                                              'event': 'push',
                                              'head_sha': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
                                              'run_id': 35776230020,
                                              'workflow': 'reference-runtime'}},
 'github_release': {'published_at': '2026-09-22T19:56:51Z',
                    'release_id': 394074477,
                    'repository': 'abraxis717/Elpis',
                    'tag_name': 'Elpis2.2.28'},
 'manifest_path': 'manifests/Elpis2.2.28.RELEASE_MANIFEST.json',
 'manifest_sha256': '54840ffdc6fb114b251b12672ce560bf1a237a711d7262bd4a1011e79bc6bcc8',
 'peeled_commit': '9ffc041371fcaa837cdf1217f7f88276bc6c4bef',
 'peeled_object_type': 'commit',
 'pypi': {'files': [{'filename': 'elpisai-2.2.28-py3-none-any.whl',
                     'packagetype': 'bdist_wheel',
                     'sha256': '218bcb451bc18c2a7a91e732b7f5bc7fc1bd8803ad25d5b70d50ad3b89ace781',
                     'upload_time_iso_8601': '2026-09-22T19:57:49.919353Z',
                     'yanked': False},
                    {'filename': 'elpisai-2.2.28.tar.gz',
                     'packagetype': 'sdist',
                     'sha256': '8fe4e20647316a709270301e8972d108c6906e1813ef4ee531bf7cb52e5ca724',
                     'upload_time_iso_8601': '2026-09-22T19:57:51.993340Z',
                     'yanked': False}],
          'project': 'elpisai',
          'version': '2.2.28'},
 'release_tag': 'Elpis2.2.28',
 'tag_object': '341efae743651a61eb846e94ec607c39c7935185',
 'tag_object_type': 'tag',
 'version': '2.2.28'}
    assert rows[0] == expected
