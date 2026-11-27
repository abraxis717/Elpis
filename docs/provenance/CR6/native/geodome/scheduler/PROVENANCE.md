# CR1-P4B — Synchronous sparse transport candidate

Algorithmic port of `Geodome/geodome_scheduler.py`, HexaFlake source revision
`4e5fe56670c61a0d8906770b03033658c3087c3a`, API 1.0.0. See
../UPSTREAM_LICENSE and ../UPSTREAM_NOTICE. New source is Apache-2.0.
Parent geometry manifest `294dee626216c2071af8a05f451a7b6c7a6a11376df07d112113ae713db89c7d`;
parent state manifest `f738173d3540b24d44d47321da7507aa6b1e08118a626b6e6b7a7f66f93f5811`.
No parent source changes. Standalone C11 candidate only.

Enrollment is explicit (1..1024, narrower than reference 4096). A physical
arc is not an admitted transport edge. Unique admitted arcs must connect
valid enrolled handles, and each vertex has at most six incident directed
outgoing and six incoming arcs. Therefore at most 6144 distinct directed
arcs can be admitted, notwithstanding the reference 24576 arc limit.
Round/visit ceilings 256/6291456 retained; active budget counts the union
of sources and destinations. A scheduler payload ceiling of 16 MiB is
checked before allocation. Memory is preallocated at creation, including
snapshot and inbox storage. During a round, transport reads the snapshot,
then destination updates consume sorted arc inboxes. After transport finishes,
ascending destination order permits in-place compaction of candidate rows
without overwriting any unprocessed destination snapshot. State commits
only after complete validation. Budget stops publish status only; callback
and validation errors leave counters, frontier and committed rows unchanged.
Scratch is reused, not authoritative, and not promised to be erased on error.
The scheduler scans bounded enrollment metadata when planning and publishing;
this is not a claim of asymptotically optimal active-worklist implementation.

Callbacks are trusted pure synchronous functions; no mutation, reentry,
state/index destruction, pointer retention, FP-environment mutation or
concurrent access. C pointer validity and output buffer size are caller
obligations. State must outlive scheduler; the index may be destroyed after
admission. Status codes classify errors, not Python exception-type parity.
The reference's floating-point numeric equality is preserved (signed zeros
compare equal). f32 messages and updates are rounded before comparison;
normal IEEE execution and nearest/even are required, no FTZ/DAZ. Constructor
qsort may allocate inside libc, outside direct-allocation wrappers. No direct
scheduler allocation in start/step/inspect. No implicit node acquisition,
no whole-run rollback, no persistence, CGC, ECS_C, or RuntimeCore integration.

Local qualification uses the recovered Python scheduler with a minimal fixture
state and native index plus independent graph BFS. Full qualification requires
actual pinned reference Geodome index and NodeState on Ouroboros. No storage
syscall containment claim; no root admission. Scientific advantage untested.
