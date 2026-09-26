# Cadence boundary audit R0

This is a local source candidate, not runtime admission or publication approval.
Elpis base: `c65c28769f17bd68ac4c1c10ab334f35f93f46ff`.
Cadence donor: `f12f1bb30286f5bc0b339853cabe94fc9fbb3ffe`.

Cadence is an **external exact donor**. The Elpis candidate contains no Cadence
submodule, no `third_party/cadence` tree, no mode-160000 gitlink and no mandatory
`cadence-net` package dependency. Elpis owns only the first-party
`CadenceECSProbe`, its compact donor-authority record, tests, documentation and
attribution. The external donor remains independently qualified.

## External donor authority

`components/CadenceECSProbe/CADENCE_DONOR_AUTHORITY.json` binds:

- fork repository `https://github.com/abraxis717/cadence.git`;
- upstream repository `https://github.com/muellerberndt/cadence`;
- exact donor commit `f12f1bb30286f5bc0b339853cabe94fc9fbb3ffe`;
- distribution `cadence-net` version `0.16.0`;
- MIT licensing and `Copyright (c) 2026 Bernhard Mueller`;
- source package `src/cadence`;
- all 44 Python source files under that package;
- source content digest `a408b7db453ccef348f6bc31d2f55f081d8e132a2b0907534343ffe202bf917f`;
- digest domain `elpis.cadence-python-source.v1`;
- external-qualification usage only, with runtime admission and root distribution inclusion false.

The source digest binds the executable Python donor bytes used by this probe.
The Git revision remains provenance authority. The committed authority record
contains no machine-local path.

The probe accepts an explicit caller-supplied donor root. It requires the source
package at `<donor_root>/src/cadence`, hashes the complete Python source surface,
checks the exact source-file count and digest, and requires `cadence` and
`cadence.record_patch` to resolve to that exact package. The probe performs no
runtime Git operations, downloads, package installation or `sys.path` mutation.
A donor-specific qualification process may expose `<donor_root>/src` through
`PYTHONPATH`; ordinary Elpis import, root qualification and release scanning do
not require the external checkout.

## Mapping to existing authority

| Donor mechanism inspected | ECS fit and disposition |
| --- | --- |
| Bounded patch and local state (`record_patch.py`, `temporal.py`, `belief.py`) | Private numeric models may consume detached ECS observations. They do not replace the kernel's canonical state, authoritative history or lifecycle. Cadence arrays are learned experiment state, not ECS state roots. |
| Ports (`ports.py`, `record_ports.py`) | Learned numeric projections and patch coupling are different from entity-bound ECS `EntityPort` handles. Neither type adapts the other's identity, attribution or scheduling guarantees. The probe uses explicit one-hot event-kind ports only. |
| RecordPatchNet | Selected for the minimal experiment: bounded gated context, residual records, private prediction and local observed repair on CPU/NumPy. |
| Equilibrium settling and detuning | Numerical consistency is not semantic validity, useful prediction, admission or fitness. No equilibrium diagnostic becomes EvolutionPathGate assertion or selection evidence. |
| Records (`records.py`) | Residual memory remains private to one invocation. It cannot become a second factual ECS event log or overwrite replay history. |
| PopulationPatch (`population.py`) | Selection/inheritance would overlap EvolutionPathGate selection and Darwinian episode ownership. Deferred to separately scoped research. |
| TemporalPatchNet / TemporalMemory | Persistent context and imagined paths may support future research but are not connected to the token path or StateOfThought. |
| BeliefPatch | Action-conditioned transitions require separately defined observation/action semantics and factual evidence. Not connected. |
| Recursive self-readback | Final readback is detached diagnostic output only. No recursive steering, feedback controller or learned same-epoch authority is connected. |
| Existing ECS / EDEN-ECS / DarwinianMatrix | Cadence does not own structural refinement, ecological transactions, mutation budgets, selection or materialization. |

## Implemented experiment

`components/CadenceECSProbe/src/elpis_cadence_ecs.evaluate_history` accepts a
complete, unfiltered `ContextProjection` describing 2..64 committed events and
at most 1 MiB of raw event records. It independently replays that bounded prefix
using ECSContextProjector and compares the complete canonical projection. A
claimed digest alone is not validation. Invalid, filtered, reordered, truncated
and stale-bound projections fail before donor resolution or construction.

For each consecutive pair, a fresh invocation-local RecordPatchNet predicts the
next committed event kind privately, then receives the actual next committed
kind as its teaching target. Only event kind reaches the numeric ports; entity
IDs, payloads and timing are omitted. Outputs are uncalibrated numeric scores,
not probabilities. The one-hot target defines a mechanical sequence-prediction
task, not semantics. The result is a detached immutable diagnostic report. No
model, record store, kernel capability, proposal, selection result or execution
capability survives the call.

The fixed profile uses 8 hidden channels, 32 record cells, 4 active cells,
initial slowest timescale 8 and learning rate 0.5. It permits at most 63 writes
and 1008 backtracking replay calls (16 per transition). These are operation
bounds, not wall-clock or efficacy claims.

Fresh-process tests require identical report digests for identical replay-valid
history and explicit seed across Python hash seeds 0, 717 and 845813583. A
separate contamination test requires a report produced after an unrelated prior
probe invocation to equal the report from a fresh process. These tests close the
module/global-state continuity loophole without promoting Cadence state into ECS
authority.

## Lane separation

- Active inference stays `R3 / DSV41 -> token inference`.
- Synchronous active-inference dependency on the slow path stays false.
- StateOfThought remains completed epoch -> observer -> request-local proposal -> future epoch/block, with host-owned control state, MAX_HOPS=8, CYCLE_WINDOW=4 and TTL=2.
- EvolutionPathGate -> R4 guarded wrapper -> DarwinianMatrix episode remains `CLOSED_QUALIFIED_INACTIVE`, slow-path only.
- CadenceECSProbe remains `RESEARCH_ONLY_INACTIVE`, `runtime_admission=false`, `scientific_qualification=false`, `mutation_authority=false`, `selection_authority=false` and has no automatic caller.

## Packaging and MIT audit

The Elpis repository does not distribute Cadence source in this composition.
`cadence-net` is not a root wheel dependency or active runtime dependency. The
external donor is MIT licensed and its repository retains the complete MIT
license. `THIRD_PARTY_NOTICES.md` records the exact donor identity and license;
it does not falsely claim the donor LICENSE is bundled in Elpis. If a future
Elpis artifact distributes Cadence source or binaries, that distribution must
retain the applicable MIT copyright and permission notice.

The earlier submodule/gitlink shape was rejected because Elpis publication
membership could not represent it and recursive first-party scanners traversed
donor-owned assertions/artifacts. That semantic source-shape conflict is closed
by keeping the donor external, not by weakening scanners or rewriting donor
source.

No local evidence, JUnit output, native build, generated population, model,
checkpoint, Branch42, Branch47/48 workspace or home-directory artifact belongs
in this candidate. No commit, tag, release or push is authorized by this audit.
