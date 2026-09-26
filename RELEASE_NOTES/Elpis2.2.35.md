# Elpis2.2.35

## Version: v2.2.35

Elpis2.2.35 publishes a qualified, inactive ECS slow-path research tranche on top of the Elpis2.2.34 runtime and release authority.

### ECS + Cadence research boundary

- Adds `CadenceECSProbe`, a bounded source-only research component that consumes a complete replay-validated ECS `ContextProjection`.
- The probe performs prequential next-event-kind diagnostics: prediction occurs before the observed next event is supplied, and local Cadence repair occurs only after the target is observed.
- Probe output is detached immutable diagnostics only. It is not semantic truth, probability, fitness, selection authority, mutation authority, runtime authority, or token-path authority.
- Cadence remains an external exact donor rather than a Git submodule, vendored source tree, or mandatory Elpis package dependency.
- The donor boundary pins Cadence commit `f12f1bb30286f5bc0b339853cabe94fc9fbb3ffe`, package `cadence-net` 0.16.0, and the complete 44-file Python source digest `a408b7db453ccef348f6bc31d2f55f081d8e132a2b0907534343ffe202bf917f`.
- Fresh-process/hash-seed qualification establishes deterministic report identity for identical ECS history and seed, and prior unrelated probe invocation does not contaminate a later report.

### Qualified inactive slow-path components

- Adds the qualified `StateOfThought` source surface. Its contract remains `completed inference epoch -> request-local proposal -> future epoch/block only`; it has no same-epoch steering and no synchronous token-path dependency.
- Adds the qualified `EvolutionPathGate` source surface and inactive Runtime R4 guarded wiring for Darwinian episodes.
- These components remain outside active runtime registries and outside the active R3/DSV41 token path.

### Authority boundaries

Active inference remains R3/DSV41. This release does not grant runtime admission to CadenceECSProbe, StateOfThought, EvolutionPathGate, Runtime R4, DarwinianMatrix, or RRSI through the token path.

No Cadence model state becomes a second continuity authority: the probe constructs fresh donor state from replay-validated ECS history and returns detached diagnostics. No imagined continuation becomes factual ECS evidence.

The demonstrated Cadence learning curve is a mechanical capability witness only. This release makes no held-out efficacy, semantic-understanding, language-inference, fitness, or superiority claim for Cadence.

### Qualification

The external Cadence CPU donor baseline completed with 821 passed, 52 optional-backend skips, one documented upstream xfail, and zero failures. StateOfThought passed independently under hash seeds 0, 717, and 845813583. The exact native R3 locus remained 227/227 with zero skips, and active-path contamination inspection found no synchronous import/call/wait dependency from R3/DSV41 into the new inactive paths.

The source and qualification evidence are deliberately separated: mechanical correctness, architectural safety, scientific efficacy, runtime admission, and release publication remain distinct authorities.
