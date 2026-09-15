# Elpis2.2.8

## Version: v2.2.8

Elpis2.2.8 is the red-team hardening and release-lifecycle successor to the published Elpis2.2.7 release.

The release carries the qualified hardening developed after the 2.2.7 red-team review:

- Promotion Planner and Structural Adjudicator authority gates recompute structured evidence instead of trusting human reports or vacuous truthiness checks; import-boundary enforcement is AST-based.
- Checkpoint replay enforces the valid local checkpoint as a rollback floor while preserving full replay as authority.
- Production fail-closed invariants no longer depend on Python `assert`; optimized `python -O` execution preserves the hardened behavior.
- ECS tests and deterministic qualification are hosted-CI gates.
- Canonical identity v1 ratifies one UTF-8, compact-JSON, domain-NUL-payload SHA-256 framing for cross-component identity use.
- Trusted live-kernel topology projection can avoid redundant full replay while the public projection path retains authoritative replay and coherence checks.
- DurableApplicationLedger v2 uses incremental steady-state validation while external database commits force full validation and cache refresh.
- Scheduler v2 removes grindable permanent entity-id priority for fresh histories while historical v1 histories remain auto-detected and replayed without rewriting events.

Release engineering is hardened at the same boundary. The frozen structural-feature authority pin is refreshed to the qualified source bytes. Hosted reference-runtime verification now distinguishes lifecycle state: when the VERSION-selected release tag exists it verifies the immutable tag tree; before that future tag exists it verifies the current candidate tree and candidate repository identity. This preserves the required order of candidate push, hosted-CI acceptance, immutable tag creation, and publication.

The imported 2.2.7 red-team report is also sanitized to remove host-local scratch/authority path literals. The technical findings remain intact, while the public shipping tree again satisfies its private-path scanner and mutation-suite clean control.

Preserved boundaries:

- release-manifest v3 remains opt-in future infrastructure; Elpis2.2.8 uses the historical v2 manifest contract;
- scheduler-v1 genesis/root compatibility and historical event bytes are preserved;
- full topology replay remains authoritative on the public replay path;
- no model/TRM authority, terminal execution authority, or public-component runtime admission is broadened;
- the state-root/copy-cost work remains performance debt rather than a correctness blocker;
- the external mathematical-source issue remains source-blocked rather than being repaired from an unratified substitute;
- external phase-manifest anchoring remains backlog.

`PUBLISHED_RELEASES.json` remains unchanged in the pre-tag candidate. Immutable tag creation, GitHub Release publication, publication-registry materialization, and PyPI Trusted Publishing remain separate later gates.
