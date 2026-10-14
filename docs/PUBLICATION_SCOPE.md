# Publication scope: native ECS memory mechanics R0

**Classification:** mechanically tested source component / no runtime authority / no semantic, cognitive, or production release claim. The `Elpis` repository is distinct from `Elpis_DEV`.

## Frozen source identity

This slice was copied **byte-for-byte** (no source-law edits) from the public development repository `abraxis717/Elpis_DEV`, pinned to Git commit `81b738ec8b9d63cb6cba7d13f98f569129561218`. The same eight source/test files have Git blob identities identical to the files at DEV commit `b2cb96307797eb065eddb7debd8e3b883f190128`, whose CI run #220 passed all 14 jobs. That DEV result is **not** a substitute for testing the publication build.

* `native/ECS/include/elpis/ecs_memory.h` — memory C ABI and capability contract.
* `native/ECS/src/ecs_memory.c` — deterministic bounded evidence storage and gated recurrent law.
* `native/ECS/tests/ecs_memory_test_util.h` — deterministic fixture helper.
* `native/ECS/tests/test_ecs_memory.c` — mechanics.
* `native/ECS/tests/test_ecs_memory_capability.c` — admission and refusal.
* `native/ECS/tests/test_ecs_memory_snapshot.c` — snapshot and corrupt-input checks.
* `native/ECS/tests/test_ecs_memory_concurrency.c` — concurrency boundary.
* `native/ECS/tests/test_ecs_memory_alloc.c` — allocation discipline (non-sanitized Linux linker wrappers).

The source header references DEV's composite and scientific records; these are **provenance/continuation references** and do not imply those facilities are present in this publication branch.

## Precisely supported claims

* Mechanically bounded, native C11 model-free data representation with explicit typed observation and identity fields.
* OBSERVE, exact read-only LOOKUP, INSPECT and snapshot/restore have reproducible native tests.
* Recurrent LEARN and FAST are capability-gated and unqualified. Setting the bit does not constitute scientific or deployment admission.
* CONSOLIDATE/SLOW is unavailable. All state on this publication branch remains free-standing and has **no managed writer, composite continuity, durable checkpoint publication, or canonical runtime execution authority**.
* The donor-inspired residual mathematics is not a trained model. Fixed hash-derived feature codes do not establish semantics, meaning, robust generalization or intelligence.

## Scientific limitation

The independent DEV MF-R0 synthetic study recorded H1/H2/H3/H5 PASS and **H4 NONPASS**: byte-matched exact keyed storage outperformed the recurrent FAST memory at retention under interference. These results are **not reproduced or qualified by this publication slice**. The present staged code must not claim superior memory retention, broad semantic reasoning or continuity.

## Deferred / not copied

* New composite envelope `ELPISEC1`, continuity v3 and RuntimeCore (these form a dependent authority transition; never copy part of the set).
* Python runtime facade, codec and inference.
* Research laboratories, private/unreleased evidence, checkpoint data, pretrained weights and donor training runtime.
* DEV-only canonical qualification statements, whose frozen historical evidence does not live in this repository.

## Publication qualification

A pre-merge local gate builds and runs the entire existing publication native suite, then compiles and executes the ECS memory tests under ASan+UBSan. New `.github/workflows/native.yml` repeats those two independent qualification lanes for pushes and pull requests; a green CI job is a prerequisite for merge, not proof of cognitive efficacy. The staged source files are verified by their Git blob identities against the pinned DEV commit before compilation. Publication's original CMake and source variants are **not overwritten**; the memory targets are appended to the publication-native build.

Every status is scoped: passing mechanics tests means the component functions under the tested contract, not that the whole Elpis architecture is scientifically or operationally complete.

## Provenance

Mathematical inspiration and frozen reference family: `eelbaz/mLattice`, MIT, source commit `873dfcab5c9fc29a5d974f74c2a1ab6511c026e1`. The applicable MIT notice is preserved in `LICENSES/MULATTICE_MIT.txt`. The development repository records derivation and adversarial comparisons. No donor model, learned tensors or weights are included.
