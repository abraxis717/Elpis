# Elpis2.2.26

## Version: v2.2.26

Elpis2.2.26 is the corrective successor to published Elpis2.2.25. It closes the hosted native-qualification and Runtime R3 integrity gaps identified during independent post-publication review without widening the public wheel or changing learned/proposal authority.

## Hosted native inference qualification

- Add a dedicated hosted workflow that builds `native/hacf/file_assets_r0` and supplies explicit `ELPIS_INFERENCE_WORKSPACE` and `ELPIS_FMS_FILE_LIBRARY` authority.
- Require the native provider sentinel to execute exactly 7/7 tests with zero skips, failures, or errors.
- Require the complete native-backed inference + Runtime R3 locus to execute exactly 149/149 tests with zero skips, failures, or errors.
- Keep the workflow contract regression-tested so silent provider removal, skip/cardinality weakening, or locus drift fails closed.

## Runtime R3 corrective hardening

- Normalize malformed latent caller inputs into deterministic typed `FAILED` receipts while preserving the original state atomically.
- Use a deterministic invalid-request identity envelope only for non-canonical failure receipts; valid requests retain their normal canonical request digest.
- Verify all historical `StepReceipt` provenance fields by deterministic target replay for previously unknown state digests.
- Persist per-step external latent inputs required for replay and cache state digests produced or already replay-validated by the current Runtime R3 instance, avoiding historical replay on normal same-runtime continuation.
- Treat this as deterministic internal provenance validation, not external cryptographic attestation.

## Qualification

- Runtime R3 corrective regressions: 17/17 PASS.
- Native-backed Runtime R3/inference locus: 149/149 PASS, zero skips.
- Inference compatibility locus: 13/13 PASS.
- Hosted native-workflow contract: 5/5 PASS.
- Full repository regression: 1895 tests, 0 failures, 0 errors, 32 established skips.
- Repository hygiene and exact corrective commit scope: PASS.

## Packaging and authority boundary

`src/elpis/inference` remains shipped through the existing `elpis*` distribution surface. Runtime R3 remains source-only because `runtime/R3/src` is outside root package discovery; this corrective release does not silently add `elpis_runtime_r3` to the public wheel.

Elpis2.2.25 remains immutable published authority. This preparation creates no `Elpis2.2.26` manifest, tag, publication assertion, GitHub Release, or PyPI publication fact.
