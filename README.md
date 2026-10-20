# Elpis — native foundation (development publication)

This is a **selected native source publication**, not a mirror of
[`Elpis_DEV`](https://github.com/abraxis717/Elpis_DEV), a packaged AI agent,
a trained language model, or an independently qualified production runtime.

## Published in this repository

- `native/substrate/`: native execution and bounded-storage substrate.
  P7 adds an opt-in resident-only FMS pin (no cold promotion or waiting
  for an in-flight move). It does not guarantee mutex nonblocking;
  see `docs/FMS_RESIDENT_ONLY.md`.
  P6 adds single-owner FMS cold-root mechanics and bounded crash-orphan
  cleanup; see `docs/FMS_COLD_ROOT.md`.
- `native/structure/`: native HACF and structural primitives.
  P9 adds opt-in hybrid retrieval residency selection with public V1 query
  layout and legacy bounded-wait semantics preserved; see
  `docs/HYBRID_RESIDENCY_COMPAT.md` (DEV migration debt explicitly tracked).
  P8 adds explicitly operator-provisioned fixed-capacity native HGRAM
  storage and association cells. No learning or runtime write authority;
  see `docs/HGRAM_FIXED_CAPACITY.md`.
  P5 additionally publishes an immutable C snapshot-manifest writer with
  content-addressed creation; see `docs/SNAPSHOT_IMMUTABLE.md`.
  Includes an opt-in C ABI entry point for no-retry exact-vector residency
  search (`elpis_vector_index_search_nowait`). Synchronous cold promotion
  remains possible; see `docs/VECTOR_RESIDENCY.md`.
- `native/pipeline/ingress/`: bounded Regex V1/V2 lexical ingress and a native execution adapter; no HACF query bridge or semantic/continuity authority. Requires PCRE2 (`libpcre2-8`) and `pkg-config`.
- `native/ECS_G/`: geometric ECS mathematics, executor, K1 and FMS adapters.
- `native/ECS_C/memory/`: independent, model-free typed memory mechanics.
  This component has **no** published continuity authority yet. The original
  mixed `native/ECS/` tree has been retired without changing numerical laws.

The memory API is `native/ECS_C/memory/include/elpis/ecs_memory.h` with implementation in
`native/ECS_C/memory/src/ecs_memory.c`. OBSERVE, read-only LOOKUP, INSPECT, and
snapshot/restore have standalone mechanical tests. Its recurrent LEARN/FAST
capability remains **scientifically unqualified** and must not be enabled as
production authority. CONSOLIDATE/SLOW is not provided.

## Continuity retirement (publication correction, October 2026)

The earlier `native/continuity/` Rust crate was a **standalone historical
continuity mechanism**, not the current Elpis continuity authority. It has
been removed from this publication branch and its build, with its historical
source preserved in Git commit
[`100c316`](https://github.com/abraxis717/Elpis/commit/100c31616e051f679c0017fc123e633dfc502099).

In development, `ECS_C` now owns continuity and memory, `ECS_G` owns geometry,
and RuntimeCore composes them. Standalone continuity was retired at RuntimeCore
ABI v7; see the audited development PR
[#64](https://github.com/abraxis717/Elpis_DEV/pull/64).
**That ECS_C authority, RuntimeCore, and native operator host are not part of
this publication slice.** Their absence is deliberate, not a compatibility
promise. In particular, this repository currently publishes **no integrated
continuity or recoverable-cognition runtime**.

The ECS_C authority implementation in DEV presently declares
`license = "UNLICENSED"`. This publication change does not redistribute or
relicense that implementation. Any later source publication requires an
explicit license and scope review, plus independent build and CI evidence.

## Build and mechanical tests

Requires CMake >= 3.20, C/C++ toolchain, Rust/Cargo where a retained target
requires it, SQLite3 and other dependencies of the native targets.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure --parallel 2
```

Build/test success concerns only the published source and its mechanical
contracts. It does **not** qualify general intelligence, semantic reasoning,
trained inference, recurrent memory superiority, power-loss durability, or a
continuity authority. Source provenance and exclusions are recorded in
[`docs/PUBLICATION_SCOPE.md`](docs/PUBLICATION_SCOPE.md).

Root source license: Apache-2.0, subject to separately retained attribution
and licensing such as `LICENSES/MULATTICE_MIT.txt`.
