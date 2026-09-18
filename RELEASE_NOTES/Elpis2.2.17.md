# Elpis2.2.17

## Version: v2.2.17

Elpis2.2.17 is the corrective successor to immutable tagged-CI-failed Elpis2.2.16.

## Corrective change

Elpis2.2.16 successfully fixed the tag-triggered `reference-runtime` path: that workflow passed for the 2.2.16 annotated tag. The remaining failure was CI's `Public release verifier` job. `actions/checkout@v4` fetched the peeled commit into `refs/tags/Elpis2.2.16`, and the job immediately ran `verify_public_release.py`; strict repository identity therefore correctly reported `RELEASE_TAG_NOT_ANNOTATED:Elpis2.2.16`.

Elpis2.2.17 restores the exact remote release tag into the local tag ref in CI before the first public-release verifier command, requires the ref object type to be `tag`, and requires its peeled commit to equal the checked-out release commit. The previously qualified reference-runtime and PyPI tag restoration remain unchanged.

## Failed predecessor evidence

- Elpis2.2.16 manifest SHA-256: `3edbd7150bf7ce73cd8eb4bc00398773c6e140db877f1d601be02f7086f98477`
- peeled commit: `1ef7faf72fc43ef9da44c7ebca77a0faaba37a57`
- annotated tag object: `ce6b9d56e92ee300af914fee087c265fa77b4ff3`
- failed CI run: `35332265193`
- tag-triggered reference-runtime run `35332265344`: PASS
- disposition: `SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED`

No Elpis2.2.16 GitHub Release or PyPI publication exists, and its tag is not moved, rewritten, rerun, or rehabilitated.
