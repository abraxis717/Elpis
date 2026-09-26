# Local ECS + Cadence integration candidate R3

This working tree is intentionally uncommitted and must not be pushed.

## Base authority

- Elpis release/main: `c65c28769f17bd68ac4c1c10ab334f35f93f46ff`
- Elpis tree: `3a5c4d3381383609322d01235a94aa2d7d88a2a9`
- Cadence external donor: `f12f1bb30286f5bc0b339853cabe94fc9fbb3ffe`
- Cadence package: `cadence-net` 0.16.0, MIT
- Cadence source digest: `a408b7db453ccef348f6bc31d2f55f081d8e132a2b0907534343ffe202bf917f`
- Cadence integration form: external exact donor + first-party inactive probe

There is no `.gitmodules`, no mode-160000 gitlink, no `third_party/cadence`, no
vendored Cadence source and no mandatory `cadence-net` root dependency.

## Qualified inactive ECS surfaces

- `components/StateOfThought/` from settlement `PASS_INFERENCE_SOT_BRANCH_SETTLEMENT_R2`
- `components/EvolutionPathGate/` from Branch46 qualified inactive extraction/wiring
- `runtime/R4/` from Branch46 qualified inactive extraction/wiring

These remain source-only / inactive. This integration does not authorize runtime
admission or synchronous token-path wiring.

## Hard architecture invariants

- active inference remains R3 / DSV41 -> token inference
- active inference -> slow path synchronous dependency = false
- StateOfThought runtime admission = false
- StateOfThought is future-only, request-local, proposal-only
- FPRM dependency from StateOfThought = false
- R2 dependency from StateOfThought = false
- R4/Darwinian/RRSI dependency from token path = false
- CadenceECSProbe runtime admission = false
- CadenceECSProbe scientific qualification = false
- CadenceECSProbe token-path dependency = false
- CadenceECSProbe mutation authority = false
- CadenceECSProbe selection authority = false

## Explicit exclusions

Branch42 recursive refinement, Branch47/48 science workspaces, generated
populations, model/checkpoint artifacts, and local qualification/evidence trees
are not part of this candidate. PopulationPatch selection/inheritance, learned
recursive steering, imagined evidence, token-path Cadence repair and Cadence
ownership of ECS mutation/materialization remain excluded.

## Cadence disposition

Cadence remains a separate exact donor checkout or separately resolved research
dependency. `components/CadenceECSProbe/CADENCE_DONOR_AUTHORITY.json` binds the
reviewed fork/upstream identity, exact revision, package/version/license, full
44-file Python source digest and non-admission status without committing a host
path.

`components/CadenceECSProbe` provides an explicit source-only offline
composition: replay-validated ECS event history -> private next-kind prediction
-> observed local repair -> detached diagnostics. Its learned state is local to
one invocation. It has no automatic caller, runtime entrypoint, mutation or
selection authority.

Donor execution is explicit: a research/conformance caller supplies a donor root
and separately exposes `<donor_root>/src` to that process. The probe verifies the
exact source package before importing RecordPatchNet. Ordinary Elpis root
qualification does not require the external donor checkout.

Fresh-process tests additionally establish report-digest identity across
PYTHONHASHSEED 0, 717 and 845813583 and establish that an unrelated prior probe
invocation cannot contaminate a later history result.

See [the boundary and packaging audit](CADENCE_BOUNDARY_AUDIT_R0.md).

Publication readiness remains contingent on the complete current publication
gate returning zero mandatory failures. No commit, push, tag or release is
implied by this document.
