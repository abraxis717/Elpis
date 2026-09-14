# Elpis2.2.5

## Version: v2.2.5

Elpis2.2.5 is the bounded runtime-composition integration successor to the
2.2.4 publication-contract corrective baseline.

The central change is not the invention of another orchestration layer. It is
the qualification of real typed handoffs between components that were already
present and individually qualified.

## Qualified composition

The Grid81 authority/application/publication path is now qualified as:

`G5.2B capability authority`
-> `G5.3B capability consumption`
-> `G5.3C durable shadow application`
-> `promotion source binding / promotion authority`
-> `isolated candidate construction`
-> `durable atomic canonical publication`

The qualified path preserves exact StructuralInfluenceCapabilityV1 identity,
single-use capability consumption, exact ApplicationReceiptV2 identity,
separate aggregate receipt-chain identity, promotion source bindings, exact
candidate evidence, one durable publication reservation, and idempotent exact
replay as `ALREADY_COMMITTED`.

## Other production consumers

This successor also connects trusted ECS `Kernel` event history to verified
topology projection/analysis read-only, ECS R0 `Candidate` to E0R3
participation while R0 remains mutation authority, and G5.3C application to
`DurableApplicationLedgerV2`.

These paths remain separate typed authority surfaces. Elpis2.2.5 does not claim
that all public components now form one universal runtime pipeline.

## Hardening retained

The release retains the F1-F11 hardening work, including source-root isolation,
release-boundary checks, portability repairs, exact receipt identity, and the
bounded AST-policy scope. Fresh-child tests declare minimal source roots
explicitly rather than depending on ambient `PYTHONPATH` leakage.

## Claims not made

Elpis2.2.5 does not claim unrestricted autonomous execution, generalized
semantic understanding, cross-process attestation, solved alignment, AGI, or
ASI. Learned/evidence surfaces do not acquire authority merely because they
participate in a qualified composition path.

The write-once release manifest is created only after pre-seal qualification.
The candidate commit, hosted-main qualification, annotated tag, package build,
GitHub Release, and PyPI publication remain later release-lifecycle gates and
are not implied by local engineering qualification or local sealing.
