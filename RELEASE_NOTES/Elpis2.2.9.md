# Elpis2.2.9

## Version: v2.2.9

Elpis2.2.9 is the release-metadata corrective successor to the failed, untagged Elpis2.2.8 public-main candidate.

Elpis2.2.8 at commit `b515bad2dd503b436635b19e94abf5d4e1eb57c0` passed full local qualification and all required hosted candidate workflows. It is not tagged, released, published to PyPI, amended, resealed, or force-rewritten. Its write-once release manifest and release note remain immutable failed-candidate evidence.

The 2.2.8 candidate's release note contained one incorrect authority statement: it said that the frozen structural-feature authority pin had been refreshed to new source bytes. The qualified candidate did the opposite by design. The structural-guidance `_authority` subtree remained byte-identical to sealed Elpis2.2.7, and the repository `${ELPIS_CANON}` source-binding hook files also remained byte-identical to the sealed 2.2.7 contract.

Elpis2.2.9 corrects that release metadata while carrying the hosted-green 2.2.8 implementation forward without runtime, scientific, or frozen-authority changes.

The carried hardening includes:

- Promotion Planner and Structural Adjudicator authority gates recompute structured evidence rather than trusting reports or vacuous truthiness checks; import-boundary enforcement is AST-based.
- Checkpoint replay enforces the valid local checkpoint as a rollback floor while preserving full replay as authority.
- Production fail-closed invariants outside frozen authority do not depend on optimization-removable Python `assert`.
- Frozen structural-guidance authority is protected by exact path-set/SHA-256 verification rather than rewritten by generic hardening.
- ECS tests and deterministic qualification are hosted-CI gates.
- Canonical identity v1 provides one cross-component UTF-8/compact-JSON/domain-NUL-payload SHA-256 framing.
- Trusted live-kernel topology projection can avoid redundant full replay while the public projection path retains authoritative replay and coherence checks.
- DurableApplicationLedger v2 uses incremental steady-state validation while external database commits force full validation and cache refresh.
- Scheduler v2 removes grindable permanent entity-id priority for fresh histories while historical v1 histories remain auto-detected and replayed without rewriting events.
- Hosted reference-runtime verification distinguishes a published/tagged release tree from a pre-tag candidate tree.
- The imported 2.2.7 red-team report is sanitized to remove host-local private-path literals.

Preserved boundaries:

- the complete structural-guidance `_authority` subtree is byte-identical to sealed Elpis2.2.7;
- the `${ELPIS_CANON}` source-binding fixture, implementation, and regression guard remain byte-identical to sealed Elpis2.2.7;
- release-manifest v3 remains opt-in future infrastructure and Elpis2.2.9 uses the historical v2 manifest contract;
- scheduler-v1 historical genesis/root compatibility and historical event bytes remain preserved;
- full topology replay remains authoritative on the public replay path;
- no model/TRM authority, terminal execution authority, or public-component runtime admission is broadened;
- existing performance/source/documentation backlog remains non-release work.

`PUBLISHED_RELEASES.json` remains unchanged in this pre-tag candidate. Immutable tag creation, tag CI, GitHub Release publication/readback, publication-registry materialization, and PyPI Trusted Publishing remain separate later gates.
