# Elpis2.2.27

## Version: v2.2.27

Elpis2.2.27 is the narrow hosted-CI corrective successor to the untagged, unpublished Elpis2.2.26 sealed candidate.

## Failed predecessor preservation

Elpis2.2.26 remains immutable sealed evidence at commit `61b8b12dc44e7389ba690abd1ad36f168f9080cc` with manifest SHA-256 `b31cf459bf2ff8d08206b22f1fe6fc6c258c5d5e6daf502129cf03d1863c5838`. Public `main` advanced to that exact seal. Hosted native-inference workflow run `35732077852` failed at workflow-definition validation before any job was created because the workflow referenced the runner context in job-level `env`. Elpis2.2.26 was not tagged, was not published as a GitHub Release, was not published to PyPI, and has no publication assertion.

The Elpis2.2.26 manifest is not modified by this successor.

## Corrective change

- Remove `${{ runner.temp }}` expressions from job-level `env`.
- Initialize `ELPIS_INFERENCE_WORKSPACE`, `ELPIS_FMS_FILE_LIBRARY`, and `TMPDIR` after runner allocation from the `RUNNER_TEMP` environment variable.
- Persist those values for subsequent steps through `GITHUB_ENV`.
- Retain the exact native-provider build, 7/7 provider sentinel, 149/149 native-backed inference + Runtime R3 locus, zero-skip policy, and no-cache qualification contract.
- Add a regression that rejects reintroduction of job-level `runner` context usage.

## Preserved technical authority

The Elpis inference source, Runtime R3 corrective source, native FMS provider, package discovery, proposal/execution authority boundaries, and qualified test loci are unchanged from the Elpis2.2.26 seal.

This preparation does not create an Elpis2.2.27 manifest, tag, publication assertion, GitHub Release, or PyPI publication.
