# Elpis2.2.13

## Version: v2.2.13

Elpis2.2.13 is the corrective CI-convergence successor to immutable tagged-but-unpublished Elpis2.2.12. It preserves the bounded R2 feedback, FMS/PAL checkpoint-artifact residency, installed-provider discovery, and POSIX/CPU reference-driver semantics already qualified in the 2.2.12 line while correcting release-gate contracts that prevented that tagged candidate from becoming publishable.

## Corrective changes

- **Sole-FPRM load-policy contract:** the P0 composition-root test now encodes the qualified registry semantics exactly: `FPRM.Samsung_TRM` is the sole `ON_DEMAND` exception and every non-FPRM port remains `NEVER`. The registry itself is unchanged.
- **No-Torch pytest witness:** the base-install workflow pairs the wholly Torch-dependent feedback module with its explicit structural witness and requires exactly `1 passed, 1 skipped`, avoiding pytest's no-runnable-test exit status while retaining observable Torch absence.
- **Hosted apt isolation:** the native dependency step scopes apt operations to the official Ubuntu source file and disables ambient source-parts discovery, preventing unrelated third-party runner repositories from controlling this release gate.
- **Dependent hygiene synchronization:** the current-release CI contract test now checks the same exact `1 passed, 1 skipped` cardinality required by the qualified no-Torch workflow.

## Preserved boundaries

- The `Elpis2.2.12` annotated tag, peeled commit, and sealed manifest remain immutable failed-release evidence.
- `components/TRMFractalSpine/registry/model_ports.toml` remains unchanged; the admitted Samsung FPRM `ON_DEMAND` policy is preserved.
- The feedback-refinement test and optional-Torch collection witness remain unchanged.
- The already-qualified bounded R2, FMS/PAL, provider-discovery, and reference-driver runtime semantics are not broadened by these CI and release-contract corrections.
- `PUBLISHED_RELEASES.json` continues to represent published-release authority only.

## Release integrity

`FAILED_RELEASES.json` records Elpis2.2.12 as tagged, CI-failed, and unpublished with its exact tag object, peeled commit, manifest path, manifest digest, and three qualified failure classes. Elpis2.2.13 carries a distinct release identity while retaining the established primitive-closure and original distribution-baseline identities.
