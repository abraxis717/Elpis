# Elpis2.2.34 corrective successor authority

Elpis2.2.33 is immutable failed release evidence.

- sealed/public main commit: `f38f4398f079f099f76f0dd8ec31cfd64c6836e2`
- signed annotated tag object: `d8ffa46236a45da917b6077b0ba09f0a095b49e0`
- manifest SHA-256: `2ebe637a0fc3455ca3bec15f25171e8a7c81f96135b3518b760247ffcbcdbf1c`
- main CI run `36154649515`: success
- tag CI run `36155836648`: failure
- failed job `108140027138`: `Repository completeness and installed artifact`
- GitHub Release: absent
- PyPI 2.2.33: absent

The failing tag checkout exposed a local lightweight `refs/tags/Elpis2.2.33` representation inside the repository-completeness job. `tools/verify_public_release.py --development` then treated that incidental ref as release authority and failed with `RELEASE_TAG_NOT_ANNOTATED:Elpis2.2.33`, despite the public tag object itself being valid and signed.

Elpis2.2.34 separates semantic modes. Development/candidate verification ignores incidental current-release tag representation; strict tagged identity continues to require the annotated tag object and exact tag-at-HEAD relation. No Elpis2.2.33 workflow is rerun or rehabilitated.
