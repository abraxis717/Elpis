# Immutable native semantic snapshot publication — P5

**Scope:** compiled C storage and identity mechanics within the existing semantic snapshot runtime. This is not a semantic-admission policy, a continuity authority, a new learning capability, or proof of power-loss durability.

## Public native API

`native/structure/semantic/include/elpis_semantic/snapshot_publication.h` adds `semantic_snapshot_publish_cas(const semantic_snapshot_manifest *, const char *directory, char hex_out[65])`. It derives `<manifest_digest>.snapshot` from the finalized snapshot identity and delegates to the immutable snapshot writer. The existing `native/structure/semantic/include/elpis_semantic/snapshot.h` remains byte-for-byte unchanged (ABI v1).

The established `semantic_snapshot_write()` now validates the finalized manifest, creates and synchronizes a temporary file in the destination directory, and publishes it without replacing an existing destination. An existing path, including a dangling symlink, is refused as a duplicate. Publication is **explicit and blocking**, not a per-token operation. The destination directory must be trusted and on the same filesystem as the temporary file. Neither write API authorizes a semantic transition or admission decision.

## Failure and durability boundary

After linking the temporary file into the destination name, a later failure may return I/O error even though the destination is already present. The caller must reconcile by verified readback; do not treat a failed return as proof of absence. The implementation uses file and directory `fsync` and preserves no-overwrite semantics, but its tests are **not** a physical power-loss or cross-filesystem durability qualification. Immutable publication does not establish global semantic novelty or historical uniqueness.

## Provenance and dependency closure

Exactly three DEV files were admitted byte-identically at `abraxis717/Elpis_DEV` commit `2c7588733180d1ab2e8e978cf277c30f9e4ab371`:

- `native/structure/semantic/include/elpis_semantic/snapshot_publication.h`
- `native/structure/semantic/src/graph/snapshot_manifest.c`
- `native/structure/semantic/tests/graph/test_segment_snapshot.c`

No DEV ECS_C authority, RuntimeCore, Python, model weights, generated evidence, or third-party storage backend is imported. Existing public semantic/runtime dependencies and snapshot ABI are retained.

## Mechanical qualification boundary

Against public base `7c934cf90d5636b31cdeba531f87eaee0a550def`, the frozen P5 R0 qualification reported 110/110 normal native CTests, 1/1 ASan/UBSan snapshot-regression test, and 1/1 ASan/UBSan content-addressed publication C probe. No existing public snapshot C export was removed. The additional probe was run in an isolated test overlay and is **not** publication source. Machine-local evidence is retained outside this repository.

Source publication does not claim cognition, semantic inference, historical authority, cross-host atomicity, or crash/power-loss recovery beyond the narrowly specified filesystem operations.
