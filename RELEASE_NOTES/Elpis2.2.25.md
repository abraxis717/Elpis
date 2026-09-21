# Elpis2.2.25

## Version: v2.2.25

Elpis2.2.25 carries the qualified inference infrastructure R0 into the successor release line after exact-SHA main closure and deterministic performance characterization.

## Qualified inference infrastructure R0

- Add sparse associative addressing with frozen scheme identities, split-feed invariance, EOS-reset semantics, and no row substitution.
- Add bounded file-backed asset access with page integrity, partial-read failure, stale-metadata rejection, lease safety, and bounded staging.
- Add exact row retrieval with bank/content/shape/dtype/packing validation and deterministic semantic-order restoration.
- Add context lifetime and compaction machinery with canonical-history preservation and clean speculative-overlay retirement.
- Keep structural guidance proposal-only and prefetch acceleration-only; neither acquires admission, mutation, execution, semantic, or governance authority.
- Add exact expert selection, local/global context state, and the compact deterministic neural target infrastructure.

## Packaging boundary

`src/elpis/inference` is shipped through the existing `elpis*` package discovery. Runtime R3 remains source-only because `runtime/R3/src` is not part of root package discovery. This release therefore does not silently widen the public wheel to include `elpis_runtime_r3`.

## Qualification

- Closed P12 adversarial base: 14/14 PASS.
- Source-level mutation sensitivity: 11/11 mutants caught and restored.
- Independent DS4 oracle: 432 exact row IDs and all 10 split points exact.
- Full root regression and repository gates: PASS.
- Final performance characterization: PASS with deterministic bounded measurements and no resource/budget failures.
- Speculative execution remains target-exact; no speculative speedup claim is made from the tiny CPU fixture.

## Claim boundary

This release does not claim a production DeepSeek V4.1 implementation, production Qwen trained-table compatibility, production-scale MoE throughput, GPU performance, external donor runtime dependency, or new execution authority for learned/proposal layers. Donor provenance and retained license texts remain explicit. Elpis2.2.24 remains immutable historical release authority.
