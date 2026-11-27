# CR2-P3 — fixed-capacity independent adaptive-cell pool

Parent: CR2-P1 cell mechanics and CR2-P2 R97W scientific replay. The pool
owns one contiguous volatile allocation, 1..1024 slots, with caller-assigned
local keys, owner/epoch/slot-generation guards and no borrowed cell pointers.
It has no authority to enroll a Geodome vertex or evidence, and no automatic
learning or consolidation. All operations on a pool are serialized. Different
cells can hold open transactions simultaneously, but publication is per-cell,
not a multi-cell atomic commit. The caller must authorize every operation.

The only preexisting C-source change is moving the exact cell struct into a
private header shared with the pool. Numerical and transaction bodies are
unchanged; standalone target cgp links the same cgr library. The runner
reconstructs the original source from that header and verifies byte equality.
No learned weights are exported to storage; copy/query buffers remain caller
owned. Release/reset explicitly discard both banks; no implicit eviction or
checkpoint. The pool's logical wipe is not a physical RAM erasure guarantee.
Test-only counter injection functions are excluded from the shared library.
Pool allocation and lifecycle are independent of any Geodome/ECS_C binding.

The C test interleaves 3 episodes at capacities 16/64/256/1024 against the
qualified stateless update and interpolation primitives, compares every staged
fast and committed bank, includes aborts, and checks stale/foreign/exhausted
handles, allocation refusal, no direct hot allocations and fresh genesis.
This is a mechanical residency assay, not an independent scientific replay
or evidence for coupled/swarm learning. The original P1 and P2 tests replay
against the refactored standalone cell as regressions.
