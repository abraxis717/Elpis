# Elpis2.2.23

## Version: v2.2.23

Elpis2.2.23 integrates the qualified ECSContextProjector as a deterministic, read-only component in the `elpisai` distribution.

## ECSContextProjector integration

- Preserve the qualified standalone projector core byte-for-byte under the `elpis_ecs_context` package.
- Add a public-Kernel adapter that snapshots committed history through `Kernel.events()`, derives the bound genesis descriptor from public Kernel configuration, and delegates to replay-backed `project_history`.
- Preserve exact replay validation, source binding, record/byte budgets, deterministic projection digests, and fail-closed handling of malformed or conflicting history.
- Add package discovery and installed-wheel qualification on Python 3.11 and 3.12.
- Add an independently verifiable component manifest, root verifier, component contract tests, and continuous CI/component-attribution enforcement.

## Authority boundary

ECSContextProjector remains read-only. It does not acquire ECS mutation, state-transition, validation, execution, model, network, tool, semantic-truth, history-authentication, or canonical-admission authority.

The component is distributed by `elpisai` but is not added to the legacy canonical/public component assembly. That assembly remains the separately qualified 17-canonical / 16-public structure, with the non-shipped `elpis_nanbeige42_host` retained only as canonical historical metadata.

## Preserved authority

The ratified primitive-closure identity, original Elpis2.0.0 distribution baseline, historical release manifests and publication records, ECS core authority, and previously qualified canonical/public assembly metadata remain unchanged.
