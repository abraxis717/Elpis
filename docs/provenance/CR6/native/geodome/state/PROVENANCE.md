# CR1-P4A — Sparse state candidate

Algorithmic port of `Geodome/geodome_state.py` from HexaFlake revision
`4e5fe56670c61a0d8906770b03033658c3087c3a`, API v1.0.0. Parent geometry
candidate manifest SHA-256 `294dee626216c2071af8a05f451a7b6c7a6a11376df07d112113ae713db89c7d`.
See ../UPSTREAM_LICENSE and ../UPSTREAM_NOTICE. New source is Apache-2.0.

Scope: fixed frequency-120 geometry, sparse state only, capacities 1..1024,
widths 1..256, binary32/binary64. Reference dense mode and capacity >1024 not
admitted. Slots allocated LIFO with per-slot generation and reset epoch. A
bounded process-local atomic owner counter prevents ordinary cross-instance
and destroy/recreate ABA, scoped to one loaded implementation; not a security
capability, not cross-process identity. Lifecycle and all state operations are
serialized by caller. A destroyed pointer cannot be used. Immutable geometry
is borrowed only for a single acquire-by-code call. No model/scheduler/host
admission, no file API, no autonomous operation, no persistent state. Direct
allocations only on creation; full staging reserved at creation, no growth.

The C ABI accepts valid caller-owned pointer buffers and explicit dimensions;
Python object-type and arbitrary-precision integer guards are not transferable.
Status codes classify refusals but are not a byte-for-byte mapping of Python
exceptions; over-capacity batches refuse before row validation. f32 conversion
requires round-to-nearest; binary32 subnormals assume normal IEEE execution
(no FTZ/DAZ). Qualification tests include signed zero and subnormals. Scratch
is cleared on refusal and success; logical state changes only after validation.
Reset clears all reserved slots in place and refuses epoch exhaustion; release
clears the row. No security claim about forensic memory erasure on destroy.
No thread-safe concurrent state operations. The fixed owner counter is the only
process-global mutable datum and has no persistent representation.

This candidate does not qualify scheduler transactions, adaptation, storage
syscall containment, or root-build admission. Allocation wrappers cover direct
state source allocation calls, not all possible system/libc allocations.
