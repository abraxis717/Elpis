# Elpis2.2.19

## Version: v2.2.19

Elpis2.2.19 corrects publication-authority semantics exposed by immutable failed Elpis2.2.18 while preserving the qualified runtime, release-manifest v3, annotated-tag restoration, and Git-less mutation-suite behavior already established in the 2.2 line.

## Corrective changes

- `PUBLISHED_RELEASES.json` is treated as explicit append-only publication fact rather than the closed-world projection of every semantic tag not listed in `FAILED_RELEASES.json`.
- `tools/refresh_published_releases.py --check` validates each existing publication assertion against its manifest, tag, version, and peeled commit without requiring an unpublished semantic tag to acquire a PUBLISHED record.
- Publication closeout uses the explicit `--append-tag Elpis2.2.19` operation only after the release orchestrator has independently observed successful tag CI, GitHub Release publication, release-event CI, PyPI publication, and the expected wheel/sdist.
- Elpis2.2.18 is recorded as immutable `SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED` evidence with its exact annotated tag object, peeled commit, and manifest digest.
- The single-shot release journal records irreversible remote mutations immediately after success and before subsequent verification, so restart reconciliation cannot confuse stale local state with remote reality.

## Failed predecessor evidence

Elpis2.2.18 reached a clean sealed commit and passed all four public-main workflows. Its valid annotated tag was then pushed, after which both CI and reference-runtime rejected the repository because the publication registry incorrectly equated tag existence with publication. No GitHub Release or PyPI publication exists for Elpis2.2.18.

- manifest SHA-256: `b7ad8112d01ea102f44cf06ec1064d296e1657b07d5c5113c06c9d5dbbdfd95b`
- peeled commit: `0a32fc5ee7d2e34487150fd39f432b1993d47c22`
- annotated tag object: `beb4cd6131c6a1c072fc427de3f26c8e0e10b980`
- failed tag CI runs: `35345927233` (CI), `35345927266` (reference-runtime)
- disposition: `SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED`

This release changes release-lifecycle authority semantics only. It does not widen runtime admission, generated-source execution authority, model authority, or the scientific claim surface.
