# Publication authority v2 — R0

## Scope

This R0 introduces a successor publication-authority primitive without modifying
historical `PUBLISHED_RELEASES.json` v1 bytes.

The model separates three authorities:

- **release identity authority:** the exact annotated `refs/tags/Elpis<semver>`
  object and the exact commit it peels to;
- **publication fact authority:** an explicit external-observation receipt that
  is durably recorded only after local release identity has been proven;
- **legacy publication history:** the frozen byte identity of
  `PUBLISHED_RELEASES.json` v1.

A semantic Git tag is not publication evidence. A publication assertion is not
inferred from the set of tags.

## Tag/tree/manifest binding

For every v2 assertion the verifier requires:

1. `refs/tags/<release>` exists;
2. the ref itself resolves to an object whose type is exactly `tag`;
3. `refs/tags/<release>^{commit}` resolves to an object whose type is exactly
   `commit`;
4. the release manifest is read from that exact commit tree with `git show`;
5. the manifest's `release_tag` and `version` agree with the tag;
6. the recorded manifest SHA-256 is the SHA-256 of those tagged-tree bytes;
7. the current checkout copy of that immutable manifest is byte-identical to
   the tagged-tree object.

This closes the ambiguity where a current-worktree manifest digest and an
independently peeled commit could both validate without proving that the commit
contained those manifest bytes. It also makes annotated-tag identity explicit
rather than accepting a lightweight tag that happens to peel to the same
commit.

## External publication witnesses

The v2 registry stores an explicit receipt containing:

- GitHub Release repository, release ID, tag and publication timestamp;
- successful tag-event CI, reference-runtime, component-attribution and
  platform-matrix run identities;
- successful release-event CI identity;
- successful PyPI publication workflow identity;
- PyPI project/version and the exact wheel/sdist filenames, SHA-256 digests,
  upload timestamps and yanked state.

The registry tool itself performs **no network access**. An orchestrator or
operator observes external state and supplies a receipt. The tool validates the
receipt structurally and binds every GitHub Actions witness to the locally
proven peeled release commit before mutation.

Accordingly, offline v2 verification proves that the durable publication
assertion is internally coherent, remains bound to exact local Git authority,
and has not changed. It does **not** claim to re-query or independently re-prove
GitHub/PyPI state while offline. Online observation and durable repository
assertion remain distinct authorities.

## Legacy v1 history

`PUBLISHED_RELEASES.json` remains historical v1 evidence. R0 does not rewrite
its existing records or reinterpret its `source_of_truth` label as the current
publication model.

`PUBLICATION_ASSERTIONS.json` records the exact SHA-256 of the legacy v1 file.
Any later mutation of the v1 bytes invalidates v2 verification. New v2 records
must be strictly newer than the final v1 version and may not duplicate a v1
published tag/version.

## Append transition

A v2 append is serialized by an exclusive repository-private lock. While the
lock is held the tool:

1. reads the original registry bytes;
2. validates the current registry and local Git authority;
3. constructs the candidate assertion;
4. validates the complete candidate;
5. compares current registry bytes with the originally read bytes;
6. writes a temporary file in the registry directory;
7. flushes and `fsync`s the temporary file;
8. atomically replaces the registry;
9. `fsync`s the parent directory on POSIX.

This provides an atomic registry transition rather than only an atomic file
replacement. The lock is stored under Git-private state, not in the worktree.

## R0 boundary

This phase establishes the v2 primitive and records the already externally
published Elpis2.2.19 fact. It does not:

- modify the immutable Elpis2.2.19 tag or release bytes;
- claim that Elpis2.2.19 had v2 authority at publication time;
- modify release/version metadata for Elpis2.2.20;
- integrate v2 into every repository immutability/lifecycle verifier yet;
- publish Elpis2.2.20;
- modify runtime, model, ECS, Grid81, FMS, inference or scientific authority.

Integration into repository-wide immutable-evidence and release-lifecycle gates
is a subsequent qualified phase.
