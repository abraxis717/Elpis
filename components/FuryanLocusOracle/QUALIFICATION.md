# Furyan R0 component qualification

Furyan R0 is an independent mathematical falsifier, not allocation authority.
The mathematical domain and limits remain exactly those in `FURYAN_R0_SPEC.md`.
Qualification does not authorize runtime allocation, generated-source execution,
model authority, runtime admission, or substitution for the production allocator.

## Reproduce

From the repository root, with pytest installed:

```sh
env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python tools/verify_furyan_locus_oracle.py
```

The default verifier checks all identity and import boundaries before executing
component code, then runs local conformance and the existing exhaustive root
gate in a fresh process. Temporary artifacts stay inside the repository and are
removed. Any failed check returns nonzero and prevents a qualification claim.
`--identity-only` verifies bytes and structural independence only; its result is
explicitly not scientific qualification.

The small local surface is also ordinary pytest:

```sh
env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python -m pytest -p no:cacheprovider \
  --basetemp=.furyan-local-pytest components/FuryanLocusOracle/tests
```

Remove `.furyan-local-pytest` after that standalone run. Local conformance covers
identity, authority escalation, source/import adversaries, isolated execution
without production/site packages, exact existing mutation diagnostics, and the
existing tail/larger reference corpora. It does not copy the core enumeration.

## Identity and frozen evidence

`COMPONENT_MANIFEST.json` uses the existing `elpis.component_manifest.v1`
internal-component convention (also used by QueryLocalProposalIngress and
StreamingRegexIngress), with explicit byte inventories and canonical self-hash
as used by the repository's internal successor manifests. Canonical JSON here
is sorted keys, compact separators, ASCII escaping, and no NaN. This wrapper
identity does not change Furyan's own frozen JSON/digest semantics.

`frozen_r0_files` contains the original eleven hashes from the root integration
gate. One aggregate anchor in the verifier fixes that exact historical mapping.
The root test derives its file hashes from the manifest and invokes the verifier;
simply updating manifest hashes after modifying R0 fails. `source_inventory`
binds every component file except the manifest itself (Python/pytest caches are
excluded). `component_content_digest` hashes that inventory. `evidence_references`
additionally binds the root science gate and standalone verifier. The manifest
self-hash excludes only its own field. These are reproducible integrity bindings,
not signatures or protection against an author deliberately replacing every gate.

Provenance records the commit/tree that introduced the unchanged R0 source and
the exact synchronized commit/tree used to add this qualification wrapper. It
does not fabricate legacy promotion receipts or assert a future commit ID.
Any semantic change requires a separately named/versioned successor preserving
these R0 bytes. The verifier fails closed on symlinks, missing files, unexpected
component files (including import shadows), changed evidence and authority flags.

## Scientific and independence gates

`tests/test_furyan_release_integration.py` remains the exhaustive authority:

| n | Canonical cases | Sum of orbit sizes | SAT | UNSAT |
|---|---:|---:|---:|---:|
| 1 | 1 | 1 | 1 | 0 |
| 2 | 36 | 64 | 8 | 28 |
| 3 | 43,968 | 262,144 | 456 | 43,512 |

All 44,005 cases agree with the independent exhaustive reference. Every SAT
certificate is directly validated. The gate pins the inventory digest and both
minimal core counterexamples at (3 operations, 2 edges). Six fresh executions
(SAT/UNSAT, three hash seeds, differing working directories) require byte identity.
The existing twelve mutants must die at their designated guards for the exact
reasons. Rule/domain kills remain labeled as such, including M1's redundant
route-gap rule; they are not misrepresented as end-to-end SAT/UNSAT disagreements.

The verifier walks the complete AST of the oracle, validator, contract, reference,
baseline, and corpus against a closed per-file import graph, rejecting dynamic
loading/introspection and non-CLI `sys` access. All transitive local dependencies
are covered and byte-pinned. The validator can import transport only; the reference
can import only itertools/functools. Negative tests attack those rules independently
of hash checks. A fresh isolated Python process also runs SAT/UNSAT and direct
certificate validation with production imports blocked. This is a proof about
these frozen sources, not a general sandbox for arbitrary Python.

`tests/run_science.py` and `tests/production_differential.py` remain untouched
historical promotion/defect evidence. Their original branch/base/old-production
preconditions are intentionally not replayed against repaired production.
Current parity remains a separate gate: `tests/test_joint_allocator.py` and
`tools/qualify_allocator_budget.py`. Furyan is not installed as a runtime package.

## Integration and admission

The root pytest inventory test requires this qualification, so deleting the
manifest, local surface, verifier or scientific files fails ordinary root pytest.
The CI Furyan job runs the complete verifier followed by separate production parity;
the component-attribution matrix runs the same full verification qualification.

`public_registry_admission=false`. The public registry already denies runtime
admission, but `verify_canonical_assembly.py` requires its IDs to equal the historical
canonical assembly minus the canonical-only host, and requires release-authenticated
component manifests and consistent dependency graphs. Adding this verification
component there would require a separate assembly/release admission, beyond this
qualification. Both registries and release identities remain unchanged, following
the repository's precedent for qualified internal components outside that assembly.

The exhaustive claim is the finite n=1..3 core. The tail and n=4..8 corpora are
bounded checks, not exhaustive qualification of all larger inputs or all Elpis
semantics. No current production defect is claimed by this component qualification.
