# HGRAM fixed-capacity native storage — publication boundary (P8)

**Classification:** independently qualified native storage mechanics only. This
component is not a learning policy, memory-quality demonstration, admission
engine, autonomous persistence service, or complete Elpis runtime.

## API and operator responsibilities

The native C header is
`native/structure/hacf/include/elpis/hgram_store.h`. Implementation resides in
`native/structure/hacf/src/kernel/hgram_store.c`. The operator-only
`elpis_hgram_init` utility is built on Linux and must be deliberately invoked;
ordinary reads do not provision files. A trusted operator selects an absolute
file path and a size in MiB. Initialization validates an owner-controlled
parent directory, checks available filesystem headroom, physically preallocates
the requested fixed extent, and commits a versioned header. Existing files are
not resized, silently repaired, or overwritten.

Four C entry points are added to the existing cascade library:

- `elpis_hgram_probe`: read-only validation of a previously provisioned file;
- `elpis_hgram_init_once`: explicit, one-time operator provisioning;
- `elpis_hgram_assoc_get`: lookup of a 32-byte key in fixed-width association
  cells, without creating storage;
- `elpis_hgram_assoc_store_preapproved`: direct bounded association writes,
  requiring a trusted caller to have already authorized the key and value.

The associated record contains a fixed 128-byte value and generation. Each
bucket has two fixed-size slots. A collision is refused; there is no automatic
eviction, dynamic capacity increase, append-only sidecar, or learning-based
update decision. The implementation retains one prior valid copy across
certain detected incomplete writes and uses ordinary filesystem sync calls.
This is **not** a power-loss durability or recovery guarantee.

**Critical security boundary:** `store_preapproved` is an exported C function,
not a permission check. It does not authenticate callers or determine whether a
model-produced write should be allowed. Only a separately qualified,
operator-controlled broker may grant actual write access, and access to the
storage file itself must be restricted by OS controls. No autonomous inference
path is wired to the writer in this publication.

## Exact source boundary

The P8 reviewed candidate modifies six native paths:

1. `native/structure/hacf/include/elpis/hgram_store.h`
2. `native/structure/hacf/src/kernel/hgram_init.c`
3. `native/structure/hacf/src/kernel/hgram_store.c`
4. `native/structure/hacf/tests/kernel/test_hgram_assoc.c`
5. `native/structure/hacf/tests/kernel/test_hgram_store.c`
6. `native/structure/CMakeLists.txt`

The first five are byte-for-byte the DEV source at
`2c7588733180d1ab2e8e978cf277c30f9e4ab371`. The sixth is a narrow
public-build integration from the DEV HGRAM CMake section, with the DEV-only
`_elpis_register` invocation replaced by public `elpis_warnings`. Existing
native source and cascade C exports are retained. The test-only Linux
linker mutation trap is registered only for `test_hgram_assoc`.

## Frozen qualification and limits

- Public base: `f7eafe317879246ecce94578157f65d0731aff47`.
- R0 was held for a private CMake helper unavailable in the public build;
  that mechanical failure was preserved, not reclassified as scientific evidence.
- R1 fixed **only** the CMake integration, retaining the five DEV blobs.
- R1 source patch SHA-256:
  `cb25793dda4a5208427a22850c3de1fa71f831514c0bf14d894be5305631bb73`.
- R1 report SHA-256:
  `2b40da0411bab72f6a96178a75277d88b8c8402a4b2c26eef523b682f4ae7512`.
- R1 mechanical evidence: **113/113 native CTests** and focused
  **ASan/UBSan 1/1** `test_hgram_store`, **1/1** `test_hgram_assoc`.
- Four new native C exports; no existing cascade C exports removed.

Qualification targets the stated storage behaviors and filesystem mechanics
on the tested Linux host. It does not establish safety against hostile
same-UID processes, durability during sudden power loss, full filesystem
portability, model learning quality, semantic admission, or autonomous runtime
authority. Qualification evidence remains in the local frozen
`/mnt/primesauce/Elpis_PUBLICATION_HGRAM_FIXED_CAPACITY_P8_R1_20261020/evidence/`
workspace; it is not copied into the public repository.
