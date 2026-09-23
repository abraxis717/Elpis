# Elpis2.2.30

## Version: v2.2.30

Elpis2.2.30 is the lifecycle-contract corrective successor to the untagged, unpublished Elpis2.2.29 sealed candidate.

## Failed predecessor preservation

Elpis2.2.29 remains immutable sealed evidence at commit `f4022927b40e720acdca9775d7de123a511add99`. Its parent is `ba39ff1d869e5edc545d7713506ca442676bf75b` and its write-once manifest remains `manifests/Elpis2.2.29.RELEASE_MANIFEST.json` with SHA-256 `19b8e7aeb1589f2ec230290db41ad70171cb3c8430fa619dc8b900e990eab885`.

The Elpis2.2.29 release lifecycle stopped during exact sealed qualification because `tests/test_2_2_29_corrective_successor_prep.py` unconditionally required the current manifest to be absent even after the one-shot release driver had committed that manifest. The failure was therefore a lifecycle-test mechanics defect. No Elpis2.2.29 tag, GitHub Release, PyPI artifact, publication assertion, or public-main mutation was created.

The Elpis2.2.29 manifest is not modified by this successor.

## Corrective lifecycle contract

- Replace the Elpis2.2.29 preparation-only test with immutable failed-seal preservation checks.
- Use `tests/test_2_2_30_successor_contract.py` for current release identity and write-once-manifest authority without assuming any particular lifecycle stage.
- Add `tests/test_current_release_lifecycle_neutrality.py`, which forbids any current-version `*_prep.py` test from entering the permanent root suite.
- Include that lifecycle-neutrality guard in `tools/full_release.py` release-lifecycle qualification.
- Predeclare the Elpis2.2.30 write-once manifest authority without materializing the manifest.
- Preserve the Apache-2.0 repository-attribution migration and all qualified Elpis2.2.29 engineering changes.

## Release authority

The repository-owned `tools/full_release.py` remains the only intended one-shot path through sealing, hosted qualification, publication, publication assertion, ratification, final-main closeout, and terminal closure. This note records source and authority state; it is not publication evidence.
