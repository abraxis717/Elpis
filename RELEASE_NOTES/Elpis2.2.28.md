# Elpis2.2.28

## Version: v2.2.28

Elpis2.2.28 is the corrective successor to published Elpis2.2.27 following the postpublication inference-infrastructure red-team.

## Release-authority milestone R0

This milestone repairs the release machinery before runtime semantics are changed:

- hosted `inference-native-r0` becomes a required main and tag qualification for 2.2.28 and later;
- the durable publication receipt records the exact successful tag-native run;
- historical receipts through 2.2.27 remain valid without retroactive mutation;
- native qualification binds exact pytest node IDs and SHA-256s of the selected test-source surface instead of trusting only 7/149 totals;
- release-critical GitHub Actions are pinned by immutable commit SHA;
- native qualification pins `pytest==9.0.2`, `numpy==1.26.4`, and `scipy==1.17.1`;
- Runtime R0 installs PyPI dependencies separately from the pinned PyTorch CPU index, eliminating the mixed-index dependency-confusion pattern.

## Historical boundary

Elpis2.2.27 remains immutable published evidence. Its native main and tag workflows did execute successfully, but the canonical release orchestrator and publication receipt did not require or durably retain the native witness. This successor corrects that authority gap prospectively.

## Remaining corrective scope

Replay completeness, typed malformed-request failure handling, numerical cross-machine replay, validation-cache rollback, asset/native trust roots, memory-accounting claims, compaction verification, ingress parsing, and lower-priority ABI/telemetry findings remain open until separately qualified.

No Elpis2.2.28 manifest, tag, GitHub Release, or PyPI publication is created by this milestone.
