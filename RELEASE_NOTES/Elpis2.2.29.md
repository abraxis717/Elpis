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
