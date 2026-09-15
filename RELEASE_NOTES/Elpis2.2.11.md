# Elpis2.2.11

## Version: v2.2.11

Elpis2.2.11 is the post-publication corrective successor to Elpis2.2.10.

The release is intentionally narrower than the 2.2.10 hardening line: it closes post-publication findings that were independently reproduced against the published 2.2.10 tree, and it corrects qualification mechanics that made pristine-checkout behavior depend on harness state.

## Corrective changes

- **Durable ledger race:** owner commits advance only owner-known count/head/total-change facts while retaining the last externally validated SQLite `data_version`. A foreign commit after the owner commit remains visible and forces full validation on the next operation.
- **Replay qualification:** replay evidence must contain at least one recognized explicit boolean status, and all recognized statuses present must be `True`; missing, false, conflicting, or non-boolean status evidence fails closed.
- **Canonical identity:** Canonical Identity v1 reserves the `__bytes__` mapping sentinel, preventing an ordinary dictionary from aliasing the canonical encoding of raw bytes while preserving existing valid encodings.
- **Frozen authority under optimization:** no byte under `src/elpis_reference/structural_guidance/_authority` is rewritten. Instead, the non-frozen package boundary refuses `python -O` / `PYTHONOPTIMIZE` before frozen assert-based invariants can execute with assertions removed.
- **Publication-registry lifecycle:** pending current-release state is derived from repository VERSION, semantic tags, failed-release authority, published-release authority, and matching manifest state rather than `GITHUB_REF_*`.
- **Pristine verifier execution:** canonical-identity convergence verification bootstraps its repository source roots and no longer depends on ambient `PYTHONPATH`.
- **Optional Torch:** TRM-backed test modules skip explicitly when Torch is absent from the base installation, matching the optional `[trm]` dependency contract.
- **Child-process isolation:** direct semantic replay propagates the explicit TRMFractalSpine source root required by its fresh interpreter.

## Preserved boundaries

- The complete structural-guidance `_authority` subtree remains byte-identical to sealed Elpis2.2.7.
- The `${ELPIS_CANON}` source-binding fixture, implementation, and regression guard remain byte-identical to sealed Elpis2.2.7.
- Elpis2.2.10 remains immutable published historical evidence; no tag, GitHub Release, or PyPI artifact is rewritten.
- Scheduler-v1 historical compatibility, public replay authority, model/TRM authority, terminal execution authority, and public-component runtime admission are not broadened.

## Explicitly not claimed

- NumPy 2.x compatibility is not declared from a single successful third-party run; dependency-range changes require a separate supported-version matrix.
- Full PromotionPlanner qualification that depends on external `${ELPIS_CANON}` source authority is not claimed when that authority is unavailable.
- GitHub release immutability, release-tag rulesets/signing, action SHA pinning, packaging-toolchain pinning, and provenance/attestation remain separate supply-chain hardening work.

## Release lifecycle

This is a pre-seal successor candidate. `PUBLISHED_RELEASES.json` remains publication truth for already published releases only. Manifest sealing, hosted candidate qualification, immutable tag creation, tag-triggered CI, GitHub Release publication, PyPI Trusted Publishing, and post-publication registry materialization remain separate later gates.
