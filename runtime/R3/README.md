# R3 experimental inference successor

R3 explicitly composes the independently tested inference package in
`src/elpis/inference`. It leaves R0/R1/R2 and public admission unchanged.
Execution is in process; Python and ctypes are not an isolation boundary.

`RuntimeR3.initial(snapshot)` creates immutable committed state.
`execute(state, request, expected_state=...)` performs prefill or deterministic
greedy generation through a private overlay. Typed failure returns the original
state with a failure receipt. `replay` checks the complete semantic receipt within the same recorded numerical execution profile; machine-agnostic bitwise replay is not claimed.
Performance telemetry is separate from receipt identity. Physical cache warming
may survive rollback; tokens, KV, n-gram history, global selection, structural
proposals, logical prefetch plans, context and committed step receipts may not.

Snapshots are pinned for the session. Context compaction creates a new snapshot;
the current target requires explicit new-session prefill for that snapshot.
It cannot silently reuse neural state computed under different latent context.

A tampered state or request may carry non-canonical values (e.g. NaN floats)
whose digest cannot be computed. Such a non-canonical identity is a tampered
identity: it fails closed as a typed `IDENTITY` error, never as an untyped
canonicalization error. The committed base check is part of the atomic
transaction, so a stale base returns the original state with a `FAILED` receipt
rather than raising.

The FMS file provider is an additive extension using unchanged HACF FMS ABI v2
for native page residency and leases. Its CPU POSIX profile has no accelerator
support. External immutable COLD assets are not copied into a writable cold
store. Buffered reads may populate unaccounted Linux page cache. Reported read
bytes are pread-returned bytes, not measured NVMe device traffic.

Import R3 explicitly from this project's `src` directory. It is deliberately
absent from the active assembly, public registry and default runtime wiring.
