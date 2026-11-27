# CR3-P1: source-bound functional evidence and enrollment

Independent DEV candidate; no root build or RuntimeCore admission. The source
lifecycle and admission law belongs to the existing `elpis_ecs_c_session` (C ABI
v1), not this extension. Authority base: Elpis_DEV
`2d0c2a6103faa1e21f08463202cfa7ddb5aac08b`; native refoundation base
`9ceb04434789c820540e36429a13b1368d190a0d`. The legacy relational view remains
unchanged and is the source of the binding/liveness/retirement semantics. Its
relation/polarity aggregation cannot represent the successor obligation or
locator multimap without changing its contract; do not use its winner selection
as successor evidence authority.

## Contract

Functional positive evidence only (not a generic n-ary relation, negation,
uncertainty, truth, or inference engine). `relation` is an externally assigned
canonical identity for the functional relation including its subject and roles,
EXCLUDING target. Canonicalization/admission of the relation vocabulary and
provenance authenticity are external gates. `source`, `scope`, and `source_version`
are checked against the live session. Target and provenance are nonzero 32-byte
identities. Evidence ID = SHA256 of ASCII `elpis.ecsc.functional-evidence.v1`
(no NUL), source, relation, scope, source_version as LE64, target, provenance,
in that order. Physical/adaptive identity never participates in the hash or
resolution ordering. Same record can have multiple declared locators; distinct
provenance creates distinct evidence. Exact repeat of an association is refused.
No semantic supersession law beyond the session's explicit source version law:
unequal targets for a live obligation produce conflict, not a selected target.

Two bounded tables: one for evidence, one for associations. Each has a committed
and preallocated staged bank. Stage operations are atomic individually; caller
must abort a transaction if any refusal is intended to invalidate the entire
batch. Commit swaps both banks after comparing the pinned session coordinate;
all calls and session transitions must be serialized. No concurrent-reader or
multi-component atomicity claim. A committed receipt is an in-RAM coordinate
and transaction ID, not an ECS_C session transition receipt or durable log.
Queries pin session lineage/instance/generation/root and local store instance/
revision; reads during a transaction see the old committed bank. Dormant sources
are filtered but retained. Revision, termination and reclamation filter old
evidence immediately and allow explicit transactional prune; no automatic
reclamation or eviction. Attach before detach for relocation; last detach is
refused. Explicit reset is staged, not autonomous. Destroy before destroying the
borrowed session. Source admission charges are counted per transaction including
new associations; CR4 must enforce aggregate per-turn fuel over transactions.

Declared locator fields are copied, syntactically bounded, and compared exactly.
The actual Geodome and CGC owner/epoch/generation/slot/revision verification, key
binding, physical release and evidence/physical enrollment coordinated commit
are CR4 responsibilities. The locator revision is a diagnostic snapshot, never
semantic precedence. There is no nearest-match authority. Local scans are exact
and bounded; no geometry or performance advantage is claimed. Capacity ceilings:
1024 records, 4096 associations, 1024 admissions per transaction, 1024 per page.
No file I/O, no persistent mutable state, no thread, no post-create direct
allocation. Session library remains private/unpublished. All diagnostics are
explicit offline development artifacts.

## Qualification

The C fixture uses deterministic test nonces and the actual session ABI on the
target. Fixed digest vector, source checks, duplicates/conflicts, paging,
capacity/refusal, staged visibility, abort, stale coordinates and transactions,
source lifecycle and reclaim, store/instance isolation, full occupancy,
4096 exact association comparisons, and direct calloc instrumentation. The
runner compiles the original session crate offline and actual substrate hash.
Local smoke used an ABI-shaped fixture and OpenSSL SHA adapter only; neither
shim is shipped. Independent randomized differential, mutation adequacy and
standalone native containment remain later CR3 gates.
