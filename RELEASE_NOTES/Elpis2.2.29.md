# Elpis2.2.29

## Version: v2.2.29

Elpis2.2.29 is the corrective successor to closed Elpis2.2.28 following the postrelease adversarial review.

## Runtime R3 canonical-admission milestone R0

This first milestone closes two coupled correctness gaps:

- `InferenceRequest.request_id` is an exact non-empty string contract at construction.
- Runtime R3 revalidates the exact request envelope and canonical request digest before a state transition can be accepted.
- `run_speculative` admits the request through the strengthened Runtime R3 validator before draft verification; malformed packets retain typed failure receipts, while a request that cannot establish canonical identity cannot commit or enter `_validated_states`.
- success receipts no longer fall back to `_failure_request_identity`; fallback identities are failure-only evidence.
- Runtime R3 requires exact `DecodeState`, `NeuralState`, and `Snapshot` objects at the replay/cache validation boundary, preventing subclasses from overriding `digest` to hit the validated-state cache.
- direct adversarial tests reproduce the postrelease findings.

## Historical boundary

Elpis2.2.28 is immutable published evidence. Its manifest, tag, GitHub Release, PyPI artifacts, publication assertion, and closeout commits are not rewritten.

## Remaining corrective scope

Separate milestones remain for the file/native trust boundary, numerical-profile stability, compaction verifier parity, exact executed-node-set qualification, release-critical dependency pinning, telemetry adoption, and compatible streaming-digest optimization.

This milestone also adds `tools/full_release.py`, the repository-owned one-shot release driver that owns sealing through terminal hosted closeout while delegating remote publication mutations to the crash-safe lower-level orchestrator.

No Elpis2.2.29 manifest, tag, GitHub Release, or PyPI publication is created by this milestone.

## Numerical profile, compaction parity, and executed-locus milestone R1

"
              "- Version numerical execution identity as `numerical-execution-profile.v2` and derive NumPy build configuration from structured `np.show_config(mode='dicts')` rather than process-global stdout formatting. YAML availability and `platform.processor()` no longer perturb identity; thread environment fields are explicitly labeled declared configuration.
"
              "- Enforce the producer's non-empty compaction policy/reason and summary object-ID non-reuse rules during verification.
"
              "- Execute provider and complete native/R3 qualification through one runner that records the exact node IDs pytest starts, compares ordered set and SHA-256 against committed authority, and independently requires zero failures, errors, and skips.
"
              "- Use the same exact-execution runner in hosted `inference-native-r0` and the repository-owned one-shot full-release qualification.
"
              "- The numerical-profile domain advances to v2; states carrying the 2.2.28 profile are therefore unsupported for bitwise replay under this successor rather than silently accepted.


## Pinned asset and native trust-boundary milestone R2

- Production file-backed inference requires an independently pinned deployment catalog; inspection alone grants no authority.
- Linux strong mode opens assets relative to a retained root capability with `openat2(RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS)` and retains the verified descriptor.
- Native provider bytes are copied to a sealed memfd, ordinary SHA-256 checked against independent authority, and loaded only from that sealed descriptor.
- The native page cache gains an additive RAM-only constructor; no scratch-path COLD capability is used by the production inference provider.
- Synthetic fixture self-authorization is moved to an explicitly named test-only provider.
- Multi-page lease acquisition validates every native tier result and rolls back the current plus all prior leases on an invalid tier.
- Ordinary deployment-byte SHA-256 is centralized in one helper and registered in a forward census; the historical Q0a v1 census remains byte-for-byte unchanged.
- The production trust-boundary adversarial suite is part of the exact native/R3 executed-node authority.

## Truthful staging telemetry and compatible streaming identity milestone R3

- Classify file-provider `staging_high_water` and row `row_staging_upper_bound` as `analytical_bound`, and expert `staging_high_water` as `configured_reservation`; none claims a measured RSS/allocation peak.
- Replace `raw_digest` whole-payload canonical JSON materialization with chunked streaming of the exact Canonical Identity v1 framing for `elpis.inference.raw-bytes.r0`.
- Preserve digest identity across bytes, bytearray, memoryview and chunk boundaries; no `raw-bytes.r1`/V3 migration is performed.
- Keep the non-contiguous memoryview compatibility path identity-preserving while production contiguous page buffers use bounded 64 KiB hex intermediates.
- Add telemetry classification and streaming-identity regressions to the exact executed native/R3 authority.


## One-shot terminal release and supply-chain hardening milestone R4

- Qualify the committed development successor before sealing and re-run the complete suite against the exact sealed commit.
- Replace the source-tree-only installed-artifact check with a real wheel build, isolated target install, installed-path/version smoke, and packaging contract tests.
- Serialize the entire outer release lifecycle with a common-Git-dir lock and hash-chained mutation journal.
- Reconcile exact repository/remote reality after crashes around seal, publication-assertion, ratification, and final-main mutations rather than blindly replaying them.
- Use the canonical repository URL and CAS lease for terminal main publication, and reuse the lower boundary's bounded paginated workflow census for closeout.
- Pin the release build backend to setuptools 84.0.0 and PyPI build/check tooling to build 1.6.1 and twine 7.0.0.
