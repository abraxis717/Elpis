# FMS resident-only acquisition — native publication boundary (P7)

**Classification:** additive C storage/residency mechanism. This change does
not publish a scheduler, continuity authority, learning subsystem, or
production latency guarantee.

## API and precise guarantee

`fms_acquire_resident(fms_ctx *, fms_id, int want_tier, unsigned mode,
void **ptr)` is an opt-in addition to `native/substrate/include/elpis/fms.h`.
Existing `fms_acquire()` retains its synchronous promotion behavior.

- When an object is already in the requested tier or a faster tier, a valid
  resident-only request pins it and returns its actual tier (nonnegative).
  Release the pin using `fms_release()`.
- When the object is demoted below the effective requested tier, or when a
  move is in flight, the new operation returns `FMS_E_NOT_RESIDENT` (`-12`)
  before pinning the object, reading cold storage, or initiating a promotion.
- Failed/lost states retain `FMS_E_STATE`; invalid arguments, missing objects,
  and unsupported requested tiers retain their corresponding FMS errors.
- A successful `FMS_WRITE` pin retains the existing write semantics, including
  invalidating the previous cold replica.
- The public FMS ABI version remains **2**; this change adds a single C
  export and error-code enumerator without removing existing exports.

This is **not** a general nonblocking call. It acquires the existing FMS
context mutex and may wait for mutex availability; the test evidence does
not establish worst-case latency or mutex lock-freedom. It is also an
**unfenced** pin, not an accelerator fence-bound lease.

## Frozen source, qualification, and exclusions

- Public source base: `ee390ef84c394f842eea0843ceb385f0a95cb5ac`.
- DEV source authority: `2c7588733180d1ab2e8e978cf277c30f9e4ab371`.
- Only two DEV files: `native/substrate/include/elpis/fms.h` and
  `native/substrate/src/fms_core.c`.
- Exact source patch SHA-256:
  `a3bf5eb5b6447f435d3e17318513af55267d64a037be5138b2f50ecd7a862fdd`.
- P7 R0 had a *mechanical build HOLD*, caused by five C enum-comparison
  warnings in the isolated qualification probe treated as errors.
- P7 R1 corrected only those five probe casts; the two DEV source files
  and the source patch remained byte-identical. R1 qualified **112/112**
  normal CTests (including the private probe) and **three focused
  ASan/UBSan CTests**: resident-only, standard FMS, and cold-root recovery.
- Frozen P7 R1 report SHA-256:
  `7d02bf1263350640b259b15b5bd202a8e051c02ab79efb6739f81c1162b0ef4a`.
- The independent `test_fms_resident_r1.c` regression and its temporary
  CMake registration were **isolated build overlays**. They are not published
  by this slice. No Python code, ECS_C authority or RuntimeCore is imported.

The qualification addresses resident vs cold access, unchanged cold-read
counts on refusal, pin/release and write semantics, and an in-flight move
refusal. It is a mechanical contract, not a claim of zero overall latency,
model quality, scientific cognition or continuity.
