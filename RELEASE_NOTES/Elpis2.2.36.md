# Elpis2.2.36

## Version: v2.2.36

Elpis2.2.36 carries the qualified ECS/Cadence slow-path research tranche that was developed on the 2.2.35 candidate line and was not previously published.

For users comparing against the last published release, **Elpis2.2.34**, the substantive change is not merely release plumbing: this release adds a bounded Cadence-backed ECS diagnostic path, qualified inactive StateOfThought and EvolutionPathGate surfaces, and inactive Runtime R4 guarded wiring while preserving the existing active R3/DSV41 inference path and authority model.

## ECS + Cadence research tranche

### CadenceECSProbe

`CadenceECSProbe` is a bounded, source-only research component that consumes a complete replay-validated ECS `ContextProjection`.

For consecutive committed ECS events, it performs a prequential next-event-kind diagnostic:

1. the current committed event kind is provided as input;
2. the donor predicts the next event kind;
3. that prediction is fixed before the next observed event is supplied;
4. the observed next event kind becomes the teaching target;
5. local donor repair/record update occurs only after the target has been observed.

The probe does not treat donor imagination as ECS history. No predicted continuation, backtracking branch, or donor-local state transition becomes factual ECS evidence.

Probe output is detached immutable diagnostics only. It is not:
- a probability calibration claim;
- semantic truth;
- runtime admission;
- selection authority;
- mutation authority;
- execution authority;
- Darwinian fitness;
- or token-path authority.

### Exact external donor boundary

Cadence remains an external donor rather than vendored source, a Git submodule, or a mandatory Elpis package dependency.

The qualified donor identity is pinned to:

- repository commit: `f12f1bb30286f5bc0b339853cabe94fc9fbb3ffe`;
- distribution: `cadence-net`;
- distribution version: `0.16.0`;
- Python source surface: 44 `.py` files;
- complete source digest: `a408b7db453ccef348f6bc31d2f55f081d8e132a2b0907534343ffe202bf917f`.

The Elpis adapter fails closed if the donor is absent, substituted, or source-drifted.

### Continuity and hidden-state rule

ECS canonical committed history remains the sole continuity authority.

The probe follows:

`canonical ECS history H -> fresh Cadence instance -> derived C(H) -> detached diagnostics only`

Cadence state does not survive probe invocation. Identical replay-valid ECS history and seed must reconstruct the same report independently of earlier unrelated probe calls.

That restriction prevents a second hidden mutable continuity channel from appearing beside ECS.

## Qualified inactive slow-path components

### StateOfThought

The release includes the qualified `StateOfThought` source surface under the contract:

`completed inference epoch -> request-local proposal -> future epoch/block only`

It has:
- no same-epoch steering;
- no adjacent-token blocking;
- no synchronous slow-path dependency from the active token path;
- bounded hop/cycle/TTL behavior;
- request-local state only.

### EvolutionPathGate and Runtime R4

The release also includes the qualified `EvolutionPathGate` source surface and inactive Runtime R4 guarded wiring for Darwinian episodes.

These components remain outside the active R3/DSV41 token path. Their presence in the repository does not grant:
- runtime admission;
- selection authority;
- mutation authority;
- automatic Darwinian fitness authority;
- or execution authority.

## Active inference and registry boundary

Active inference remains **R3 / DSV41 -> token inference**.

The new ECS/Cadence and slow-path components do not add a synchronous import, call, wait, or feedback dependency to that active path.

The existing canonical 16-component public assembly registry remains unchanged. The newly added research surfaces are qualified/inactive rather than silently promoted into the active registry.

## Qualification evidence

The bounded engineering and isolation claims are backed by:

- external Cadence CPU donor baseline: **821 passed**, **52 optional-backend skips**, **1 documented upstream xfail**, **0 failures**;
- StateOfThought fresh-process qualification under hash seeds **0**, **717**, and **845813583**;
- exact native R3 locus: **227/227**, zero skips;
- Cadence same-process repeatability checks;
- fresh-process/hash-seed deterministic report identity;
- cross-invocation contamination isolation;
- ECS/projection nonmutation checks;
- prefix-causality/no-lookahead checks;
- changed-target and later-history tests proving prior predictions do not retroactively change;
- fail-closed missing/substituted/drifted donor tests;
- import-only active-path inspection excluding Cadence, Torch, StateOfThought, R3/R4 feedback, and Darwinian slow-path contamination.

The observed local Cadence learning curve is a mechanical capability witness only. This release makes no held-out efficacy, semantic-understanding, language-inference, fitness, or superiority claim for Cadence.

## Release-control correction from Elpis2.2.35

Elpis2.2.35 carried the same substantive engineering tranche but was never tagged or published.

Its main-branch hosted qualification failed in GitHub Actions run `36254311919`, job `108438070230`, during the permanent repository/root-suite contract. The failure was not in Cadence, ECS replay, StateOfThought, Runtime R4, the native R3 locus, component attribution, or inference-native qualification.

The exact defect was release-authority bookkeeping:

`manifests/Elpis2.2.35.RELEASE_MANIFEST.json` had materialized under `FIRST_COMMITTED_BLOB_IMMUTABLE`, introducing the historical `/full_elpis_runtime_admission` declaration, while `tools/runtime_admission_temporality_v1.json` still reflected the pre-materialization write-once set.

The hosted diagnostic was:

`UNREGISTERED_DECLARATION:('manifests/Elpis2.2.35.RELEASE_MANIFEST.json', 'json_key', '<json>', '/full_elpis_runtime_admission')`

Elpis2.2.36 corrects that lifecycle authority by:

- preserving the failed 2.2.35 manifest and candidate exactly as immutable historical evidence;
- keeping `Elpis2.2.35` untagged and unpublished;
- predeclaring the 2.2.36 release manifest under the existing first-committed-blob immutability rule;
- regenerating runtime-admission temporality authority from the immutable write-once release-manifest authority before hosted qualification;
- retaining the same separation between active runtime authority, historical release snapshots, and qualified-but-inactive research components.

This correction changes release-authority bookkeeping, not the scientific claims or runtime admission status of the ECS/Cadence tranche.
