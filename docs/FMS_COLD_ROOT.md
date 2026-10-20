# Exclusive FMS POSIX cold-root ownership — P6

**Classification:** native C storage mechanics for the existing FMS POSIX PAL. This is an isolated runtime-source publication, not a general durability, cognition, autonomous recovery, or authority qualification.

## Scope and behavior

`native/substrate/src/fms_pal_posix.c` now opens the cold-root directory with an exclusive, non-blocking `flock` held for the POSIX PAL instance's lifetime. A second concurrent owner of the **same** directory is refused. A different directory can have a separate owner. The lock is released when the PAL instance closes its directory descriptor.

When a new owner acquires the lock, it scans the directory for precisely recognized PAL-generated regular filenames: committed cold blobs with the SHA-256-and-serial `.blob` form, and six-character `.fms-tmp-` files left by interrupted commits. Those files can be reclaimed because cold tokens are process-local, and no API re-adopts a preceding process's cold token. Objects with unrelated names, and directory or symlink entries, must not be deleted by this reclamation path. Recognized names are not authentication: a trusted, dedicated directory and filesystem access controls are prerequisites.

The change is **not** a persistent cold-cache reattachment feature. Existing public C API headers and FMS core remain unchanged; the PAL constructor may now refuse a second owner that previously would have opened the same path. Do not share a cold-root directory across independently live FMS contexts. No inference-time learning policy or external controller is added.

## Source provenance and test-fixture correction

The following three production/test/build paths come directly and byte-identically from `abraxis717/Elpis_DEV` at `2c7588733180d1ab2e8e978cf277c30f9e4ab371`:

- `native/substrate/src/fms_pal_posix.c` — exclusive ownership and bounded orphan cleanup
- `native/substrate/tests/test_fms_cold_reclaim.c` — crash orphan, non-owned-file preservation, second-owner refusal, put/drop cycling
- `native/substrate/CMakeLists.txt` — registers the additional native test

The fourth source path, `native/substrate/tests/test_fms.c`, is a **public-only mechanical test-fixture fix**, not a DEV blob. The existing two-context test called `mkroot` twice, but `mkroot` returns the same static buffer each time. Its two supposed independent paths therefore aliased, which the new exclusive lock correctly refused. The isolated R1 correction stores the two paths independently and asserts their distinctness. The production POSIX PAL implementation was not changed to satisfy the test.

## Qualification and exclusions

- Public baseline: `21a82af8d71ebbbe61d7a66ebb405b929c0a6a4e` (merged P5).
- Frozen P6 R0 qualification stopped at a **mechanical HOLD**: `substrate.test_fms`, one failed assertion in the existing two-context fixture. R0 remains preserved separately.
- P6 R1, with the four-path patch, reported **111/111 normal CTests**, **321/321 FMS assertions**, and focused **ASan/UBSan 1/1 cold-root plus 1/1 FMS** regression checks. These were not a full sanitizer-suite run.
- R1 source patch SHA-256: `87dd12f8cba84fa84eb806a514052c21aa236928ce11feb4d1f9b441f4a8f059`.
- R1 immutable report SHA-256: `b5c5d4ac10f2b7103d90aeb85a1776c6312a2eb48c0e0532ade77c1961ef90f3`.

Neither a physical power-loss durability guarantee nor cross-process availability while the original owner lives follows from these tests. The test creates and deletes only isolated build-local scratch data. No Python source, DEV-only FMS API expansion, model runtime, or ECS_C/RuntimeCore authority is imported. Machine-local evidence stays under `/mnt/primesauce/`, not in this repository.
