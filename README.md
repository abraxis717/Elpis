# Elpis — Native foundation (publication development)

This repository contains the independent native ECS mathematical/runtime foundation, HACF structural substrate, and minimal continuity mechanisms. The code is a **development publication**, not a released AI system, language model, or demonstrated generally intelligent agent.

The mechanically tested model-free ECS memory API is under `native/ECS/include/elpis/ecs_memory.h` and `native/ECS/src/ecs_memory.c`. In this publication stage it is **free-standing and non-authoritative**: OBSERVE, read-only LOOKUP, INSPECT, and snapshot/restore mechanics can be tested independently. The recurrent LEARN / FAST capability is **not scientifically qualified**; it must not be treated as admitted or integrated into a cognitive runtime. Do not grant it by enabling the capability bit in production. CONSOLIDATE / SLOW is absent from canonical memory.

This publication slice does **not** include the composite ECS envelope, managed RuntimeCore, or continuity v3 described by newer DEV work; those require a separately reviewed, versioned end-to-end integration. See `docs/PUBLICATION_SCOPE.md` for exact source provenance, exclusions and validation commands.

## Native build and tests

Requirements: CMake >= 3.20, C/C++ compiler, Rust/Cargo, SQLite3 development headers, POSIX/Linux toolchain as applicable.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

All tests are mechanics only; no cognitive, semantic, trained-model, scientific or production-continuity qualification is claimed. Root licensing is Apache-2.0; the mathematical donor's separate MIT attribution is retained in `LICENSES/MULATTICE_MIT.txt`.
