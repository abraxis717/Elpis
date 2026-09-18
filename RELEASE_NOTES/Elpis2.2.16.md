# Elpis2.2.16

## Version: v2.2.16

Elpis2.2.16 is the corrective successor to the immutable tagged-CI-failed Elpis2.2.15 candidate.

## Corrective change

The Elpis2.2.15 annotated tag is valid remotely, but the tag-triggered `reference-runtime` workflow observed a lightweight local tag after `actions/checkout@v4` fetched the peeled commit directly into the tag ref. Strict repository identity therefore correctly rejected the checkout with `RELEASE_TAG_NOT_ANNOTATED:Elpis2.2.15`.

Elpis2.2.16 restores the exact remote tag object into `refs/tags/<release>` before strict verification in both `reference-runtime` and the PyPI build workflow, then requires `git cat-file -t` to report `tag` and the peeled commit to equal the checked-out release commit.

## Failed predecessor evidence

- Elpis2.2.15 manifest SHA-256: `a97b06b1db5070bb4cedea221ea739e42b212b0516fa33d7b54bf023e3395393`
- peeled commit: `60c0473a667d3c201a0eecbfce0d18832afb79fe`
- annotated tag object: `c63a41838115adb681a0c20e122218305e6bb3a8`
- GitHub Actions run: `35327697128`
- disposition: `SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED`

No Elpis2.2.15 GitHub Release or PyPI publication exists, and its tag is not moved, rewritten, rerun, or rehabilitated.
