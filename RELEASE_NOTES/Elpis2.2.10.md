# Elpis2.2.10

## Version: v2.2.10

Elpis2.2.10 is the qualified red-team hardening and release-lifecycle release for the Elpis 2.2 line.

The release strengthens deterministic authority boundaries, rollback integrity, identity framing, replay behavior, durable state validation, scheduler fairness, and hosted release qualification while preserving the repository's frozen authority contracts.

## Highlights

- Promotion Planner and Structural Adjudicator gates recompute structured evidence instead of trusting human reports or vacuous truthiness checks; import-boundary enforcement is AST-based.
- Checkpoint replay enforces the valid local checkpoint as a rollback floor while preserving full replay as authority.
- Production fail-closed invariants outside frozen authority no longer depend on optimization-removable Python `assert`.
- Frozen structural-guidance authority is protected by exact path-set and SHA-256 verification rather than rewritten by generic hardening.
- ECS tests and deterministic qualification are hosted-CI release gates.
- Canonical identity v1 provides one cross-component UTF-8, compact-JSON, domain-NUL-payload SHA-256 framing.
- Trusted live-kernel topology projection can avoid redundant full replay while the public projection path retains authoritative replay and coherence checks.
- DurableApplicationLedger v2 uses incremental steady-state validation while external database commits force full validation and cache refresh.
- Scheduler v2 removes grindable permanent entity-id priority for fresh histories while historical v1 histories remain auto-detected and replayed without rewriting events.
- Hosted reference-runtime verification distinguishes immutable tagged releases from pre-tag candidates.
- The imported 2.2.7 red-team report is sanitized to remove host-local private-path literals.

## Preserved boundaries

- The complete structural-guidance `_authority` subtree remains byte-identical to sealed Elpis2.2.7.
- The `${ELPIS_CANON}` source-binding fixture, implementation, and regression guard remain byte-identical to sealed Elpis2.2.7.
- Release-manifest v3 remains opt-in future infrastructure; Elpis2.2.10 uses the historical v2 manifest contract.
- Scheduler-v1 historical genesis/root compatibility and historical event bytes remain preserved.
- Full topology replay remains authoritative on the public replay path.
- No model/TRM authority, terminal execution authority, or public-component runtime admission is broadened.
- Existing performance, external-source, and documentation backlog remains non-release work.

## Release integrity

Elpis2.2.10 adds an explicit current-release hygiene regression requiring the README `## Release Notes` section itself to open with the active VERSION. This closes the stale-summary failure mode without changing runtime or scientific behavior.

`PUBLISHED_RELEASES.json` remains unchanged in this pre-publication candidate. Tag creation, tag CI, GitHub Release publication/readback, publication-registry materialization, and PyPI Trusted Publishing remain separate later gates.
