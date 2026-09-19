# Elpis2.2.20

## Version: v2.2.20

Elpis2.2.20 establishes publication-authority v2 while preserving the qualified runtime, scientific authority boundaries, historical release bytes, and externally published Elpis2.2.19.

## Publication-authority changes

- `PUBLISHED_RELEASES.json` is frozen as immutable legacy v1 publication history. Its former `--append-tag` mutation surface fails closed.
- `PUBLICATION_ASSERTIONS.json` is the append-only successor publication authority. Its assertions are created only from explicit external-observation receipts rather than inferred from semantic tag existence.
- Git-bearing verification binds each v2 assertion to an actual annotated tag object, its peeled commit, and exact release-manifest bytes read from the tagged commit tree.
- Git-less verification retains structural, receipt, manifest-byte, ordering, uniqueness, failed-release, and frozen-v1 checks without pretending to re-prove unavailable Git objects.
- Registry append uses exclusive locking, prevalidation, compare-before-replace semantics, file fsync, atomic replacement, and parent-directory fsync.
- Publication-observation facts remain separate from repository mutation authority; the v2 registry tool performs no network discovery.

## Compact release authority

Compact publication membership is explicitly versioned. Historical `elpis.publication-membership.v1` retains its original exclusion semantics. Successor `elpis.publication-membership.v2` excludes both `PUBLISHED_RELEASES.json` and `PUBLICATION_ASSERTIONS.json`, preventing post-publication closeout from changing the publication-tree digest of the release that necessarily preceded it.

The release-wide mutation harness refuses to provisional-reseal a version already represented in publication history. Once `VERSION` names an unpublished successor, its full mutation suite executes normally and preserves independent negative-branch diagnostics.

## Preserved boundaries

This release changes release and publication authority mechanics only. It does not widen runtime admission, generated-source execution authority, model authority, terminal execution authority, public-component admission, or the scientific claim surface.
