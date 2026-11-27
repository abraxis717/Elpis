# CR2-P1: bounded R97W adaptive-cell candidate

Reference: CGC commit `0895c2bc732a377b5a5f0d063ae13cc72684ec9a`,
`research/benchmarks/r97w/portable/{experiment.py,SPEC_PORTABLE.json}` and
`src/cgc/ecsg_e0.py` (SHA-256 `92c987e0fb54d80193fd60ecc9a3e31088f0f9b7cd2cfe8e08c4636a198d7084`).
The portable reference is derived, not a historical frozen package.
Elpis sealed CR1 predecessor `83563dac48a2dcb4cfa2cb0fcf317789d0cc726e`.
Reuse the pinned ECS_G math ABI, not K1 consolidation or CGC120 wrapper.

Three outputs, five inputs (caller supplies bias feature), eight microscopic
units per output. MSE across all rows and outputs, full gradient norm clipping
at 2.0 with denominator epsilon 1e-12, SGD rate 0.08, eight steps, Reptile
interpolation 0.28. Scalar binary64 arithmetic; toleranced Torch parity, not
bitwise cross-implementation identity. Same-binary replay requires bitwise
identity. Native finite-intermediate refusals intentionally fail closed.

One serialized cell, fixed capacity; no automatic updates, no implicit
consolidation, no storage I/O. Begin/observe/propose/learn/consolidate/reset/
commit/abort separate responsibilities. Query exposes committed banks only;
copy_bank permits trusted diagnostic inspection of staged banks. Observation
ID is caller metadata, not authenticated provenance. Commit can publish
explicit partial fast adaptation, for cold/continual controls. Consolidate
requires eight steps; reset is explicit. Initial weights are caller-supplied
immutable within the cell lifetime; no fresh state derived from checkpoints.
No root build, swarm, ECS_C or RuntimeCore admission; no scientific utility
claim until the complete portable benchmark is independently replayed.
