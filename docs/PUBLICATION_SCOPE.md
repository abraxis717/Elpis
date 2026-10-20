# Publication scope: independent native mechanics; continuity retired

**Classification:** selected mechanically testable native components. No
production continuity authority, composite ECS runtime, cognition/semantic
qualification, trained-model release, or end-to-end AI capability is claimed.
The publication repository `abraxis717/Elpis` is distinct from `Elpis_DEV`.

## Physical source inventory after this correction

Present:

* `native/substrate/`: bounded native substrate.
* `native/structure/`: HACF and structural facilities.
* `native/ECS_G/`: geometric ECS code moved byte-for-byte from the historical
  `native/ECS/` publication tree; its K1 ABI remains the publication-era law.
* `native/ECS_C/memory/`: model-free typed memory source moved byte-for-byte
  from that tree, independently tested and with LEARN/FAST unqualified.

Retired from this publication branch:

* `native/continuity/`: old standalone continuity code, its header, build,
  tests and deterministic historical vectors. Git history preserves it at
  publication commit `100c31616e051f679c0017fc123e633dfc502099`.

**Not imported:** `native/ECS_C/authority/`, `native/runtime/`, the current
DEV geometric K1 upgrades and ECS_C continuity authority, RuntimeCore's native host, Python
facades, model runtimes, and all private or frozen qualification materials.
No source from DEV's current ECS_C authority is copied or relicensed here.
The independent physical ECS_G/ECS_C memory split is now present; it does not
imply that the later DEV numerical/runtime upgrades have been imported.

## Existing memory-source provenance

The independent ECS memory component was copied byte-for-byte from public
`abraxis717/Elpis_DEV` at commit
`81b738ec8b9d63cb6cba7d13f98f569129561218`, with original independent
source/test Git blob identities matching the DEV source at
`b2cb96307797eb065eddb7debd8e3b883f190128`:

* `native/ECS_C/memory/include/elpis/ecs_memory.h`
* `native/ECS_C/memory/src/ecs_memory.c`
* `native/ECS_C/memory/tests/ecs_memory_test_util.h`
* `native/ECS_C/memory/tests/test_ecs_memory.c`
* `native/ECS_C/memory/tests/test_ecs_memory_capability.c`
* `native/ECS_C/memory/tests/test_ecs_memory_snapshot.c`
* `native/ECS_C/memory/tests/test_ecs_memory_concurrency.c`
* `native/ECS_C/memory/tests/test_ecs_memory_alloc.c`

This is historical provenance for the memory component, not a claim that the
publication branch is synchronized with all of DEV.

## Mechanical and scientific bounds

* Bounded native typed observations, exact LOOKUP, INSPECT and
  snapshot/restore are independently exercised by the native memory tests.
* Recurrent memory LEARN/FAST is capability-gated and **not scientifically
  admitted**. Setting an option bit does not qualify it. CONSOLIDATE/SLOW is
  not provided.
* The independent DEV MF-R0 synthetic study reported H1/H2/H3/H5 PASS and
  **H4 NONPASS**: keyed exact storage outperformed recurrent FAST retention
  under interference. Those findings are not requalified here.
* No published component in this branch manages an authenticated continuity
  store, writes a composite checkpoint, or authorizes cognition publication.
* The DEV ECS_C authority uses a fixed five-file physical storage envelope,
  no append history, and fixed recovery work, but **none of its code or tests
  is part of this publication change**.

## Development continuity context — not publication qualification

Development PR
[#64](https://github.com/abraxis717/Elpis_DEV/pull/64) retired the
standalone continuity implementation under RuntimeCore ABI v7. ECS_C now owns
continuity and memory; ECS_G owns geometry; RuntimeCore composes the two.
DEV's ECS_C Recovery Q0 RUN PASS applies to its exact source commit
`117b41ad8a1a1fd25963489d4b29a66b284c4632` under ABI v6 only. That
qualification does **not** transfer to ABI v7 or to this publication branch.
This branch neither embeds the DEV instrument nor republishes its immutable
evidence. Process-death results are not power-loss durability results.

The DEV ECS_C Rust crate currently specifies `license = "UNLICENSED"`.
Consequently the crate is not silently included in this Apache-2.0 publication
or granted a new license. An explicit licensing/provenance decision is required
before any selective successor-source publication.

## Publication mechanical verification

The publication's own native CI builds the source in this repository and runs
its CTest suite, with an independent sanitizing memory-test lane. The CMake
build must no longer include `native/continuity`; no replacement continuity
library is declared or linked. A green publication CI run establishes only
mechanics of the included components; it does not inherit DEV qualification.

## Historical provenance and attribution

Mathematical inspiration/reference family: `eelbaz/mLattice`, MIT license,
source commit `873dfcab5c9fc29a5d974f74c2a1ab6511c026e1`. The relevant
MIT attribution is retained in `LICENSES/MULATTICE_MIT.txt`. The present
change does not upload model weights, training data, private sources,
experiments, authority records, keys or frozen qualification evidence.
