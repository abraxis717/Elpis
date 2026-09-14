# Compact release authority (v3)

`elpis.release-manifest.v3` is an additive, explicitly selected authority for
a future ratified successor after 2.2.6. It does not migrate historical
manifests. Elpis2.2.6 keeps v2, and the sealer still defaults to v2 for every
version. A future release owner must ratify the successor's identity and
complete the usual atomic metadata advance before selecting `--schema v3`.

## Record

The normal release identity and runtime-authority fields are unchanged. The
`files` inventory is replaced by these six scalar fields:

| Field | Meaning |
| --- | --- |
| `tree_digest_algorithm` | `elpis.publication-tree.sha256.v1` |
| `publication_policy` | `elpis.publication-membership.v1` |
| `publication_tree_sha256` | Lowercase 64-digit aggregate digest |
| `file_count` | Number of included regular files and symlinks |
| `git_tree_oid` | Native Git tree object identity of the publication projection |
| `git_object_format` | `sha1` or `sha256` |

Both Git fields are null if the record was created without Git metadata.
A Git checkout requires both to match its actual publication projection.
A Git-less verifier validates their syntax but explicitly cannot prove Git
identity or ancestry. The SHA-256 tree digest remains independently mandatory.
Unknown fields, including any `files` array or substitute inventory, are
rejected. There is no secondary database or generated evidence dependency.
No additional per-file diagnostic pins are stored.

## Canonical SHA-256 algorithm

`u64(n)` denotes exactly eight bytes, unsigned big-endian. Paths are normalized
POSIX relative paths, encoded in strict UTF-8. Absolute paths, backslashes,
NULs, `..` components, redundant separators, and `.` components are rejected.
There is no Unicode normalization: different UTF-8 path identities remain
different files. Paths are sorted lexicographically by their UTF-8 bytes,
independently of locale and filesystem enumeration order. Duplicates fail.

Let `N` be the number of included paths. Start the hash input with the literal
ASCII bytes `elpis.publication-tree.v1`, one NUL byte, then `u64(N)`.
For each sorted path append this record:

```
u64(path_byte_length) || UTF8(path) || kind || u64(content_byte_length)
    || SHA256(content).raw_32_bytes
```

`kind` is the single ASCII byte `F` for a regular file or `L` for a symlink.
Regular-file content is its exact bytes; symlink content is the UTF-8 encoded
link target text, without dereferencing it. Symlinks escaping the release root
and traversal through symlink parents fail. Hash the complete framed stream
with SHA-256 and encode the result as lowercase hexadecimal.

Count, fixed-width lengths, the one-byte type, and the fixed-width inner hash
make the encoding uniquely parseable. File size plus content SHA-256 binds
content; path bytes bind membership and names. Additions, deletions, renames,
one-byte changes, and regular-file/symlink substitutions change the digest.
Empty directories, modes, mtimes, ownership, and other filesystem metadata
are not aggregate inputs. The Git identity independently binds Git modes.

The implementation and independent framing-vector test live in
`tools/release_tree_digest.py` and `tests/test_compact_release_manifest_v3.py`.

## Publication membership and safety

The two exclusions are the selected release record itself and the root
`PUBLISHED_RELEASES.json`. Any path with a `.git` component is ignored.
Historical manifests and every other tracked publication file are included.
This preserves the existing self-seal and post-publication registry boundaries.

In Git, included membership comes from stage-zero tracked index entries;
untracked/ignored clone-local files are not publication authority. In an
export, membership is all physical regular files and symlinks except the
explicit exclusions. Unknown export junk changes the digest. Missing tracked
files, unresolved index entries, submodules, and unsupported special files fail.

Before selecting membership, the compact helper scans the physical tree,
including ignored/untracked paths and empty directories. Components named
`build`, `dist`, `__pycache__`, `.venv`, `.pytest_cache`, `.mypy_cache`, or
`.ruff_cache`, and any component ending in `.egg-info`, fail. They are never
silently omitted. Directory symlinks are not traversed; escaping links fail.
The normal verifier's binary, private-data, runtime, and public-boundary scans
remain independently required. The compact hash is integrity authority, not
proof that the contents are safe or correct.

## Git identity and the self-reference boundary

A tracked record cannot contain the hash of the complete root tree that
contains that very record: that requires a cryptographic fixed point. Storing
a pre-seal commit instead introduces a separate lifecycle identity and does
not authenticate a Git-less export.

V3 therefore binds the exact **publication projection** of `HEAD`: remove only
the policy exclusions and compute the native Git tree object identity for the
remaining paths, blob identities, and modes. This is explicitly not
`HEAD^{tree}` when excluded files are present. Tree hashing follows Git's
native object framing and directory ordering. No object or temporary index is
written; the projected root object need not be stored in the object database.

Sealing and verification require equality of the included HEAD entries,
stage-zero index entries, and physical file contents/modes. The recorded
projected tree must match as well. Commit included changes before sealing;
then commit the write-once record. Adding that record or updating publication
fact does not change the publication projection. A different included tree,
uncommitted included bytes, staged membership changes, or changed Git modes
fail. There is no tag prerequisite at this stage.

Candidate repository identity still independently resolves HEAD and every
ratified authority commit, and proves authority ancestry to HEAD and any
existing release tag. Strict identity additionally requires the release tag
at HEAD. Empty commits with the same publication tree can pass the tree check
but still fail strict tag identity. Missing/shallow history is not excused.
Git-less normal verification prints repository identity as not applicable;
explicit candidate/strict identity commands continue requiring Git.

## V2 and publication compatibility

The public verifier dispatches v3 to the compact helper and keeps the v2 /
distribution-v1 inventory checker isolated with its existing digest and exact
membership rules. The historical 2.1.2 base-authority exception and
distribution-manifest precedence remain intact. A v3 record is rejected for
2.2.6 or earlier; provisional overrides cannot migrate schema versions.

`PUBLISHED_RELEASES.json` continues binding the exact manifest SHA-256, manifest
path, version, release tag, and peeled commit, independently of its payload
schema. Its exclusion from the aggregate avoids the existing publication
cycle. None of its tag, history, or byte-integrity checks are relaxed.

## Future adoption

After the successor's implementation, identity, and metadata are qualified
and committed, run `python tools/seal_release.py --schema v3`. Commit the
resulting record, verify the candidate, and follow the existing hosted-green,
tag, strict verification, and archive-verification ordering. Do not run this
for 2.2.6. Source archives must preserve the complete publication tree; a
package-only archive that omits source-only components is not that tree.
Wheel/package discovery remains unchanged. Verification belongs before
package construction, as in the existing export workflow.

The legacy `tools/mutation_suite.py` is still a v2 provisional resealing
harness. V3 has independent tiny-tree mutation and export tests, with no
persistent qualification directory or whole-repository reseal requirement.

## Integration boundary

With the approved scope extension, `tools/verify_canonical_assembly.py` now
authenticates component bytes through the aggregate for v3. It verifies the
complete publication tree, then checks each component manifest's membership
in that independently derived tree. Untracked component files cannot acquire
authority from a valid tracked-tree digest. V2 retains its original per-file
hash checks. No replacement inventory is synthesized or persisted.
Assembly structure is still recomputed independently, including when a valid
aggregate binds structurally incorrect JSON. Normal public verification
remains responsible for the independently ratified release identity fields.
The assembly tests use tiny synthetic successor fixtures for both schemas,
without creating an Elpis2.2.6 record.

The legacy mutation harness also indexes `data["files"]` and requests default
v2 provisional sealing. Future v3 release-wide qualification must explicitly
adapt that harness or retain its v2 fixtures separately from the compact
mutation suite. It cannot simply reseal a v3 record using the default v2
command. `tools/mutation_suite.py` is also outside the owned-file list.
This remaining harness integration is an adoption blocker, not a reason to
synthesize a hidden full inventory or weaken assembly byte authentication.

For scale, the existing Elpis2.2.5 v2 record is 261,663 bytes for 1,523 paths.
The equivalent compact JSON shape, keeping its identity fields and count and
using the fixed-width v3 digests, is 971 bytes (99.63% smaller, about 269x).
This is an in-memory size comparison, not a replacement historical manifest.

## Implementation validation and handoff

Starting seed: `13bef1e8d96b62044c592f96d02383e3482fbd64`, on
`agent/astra-hard-20260914`, initially clean. All pytest runs disabled bytecode
and pytest's cache provider (`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`).
Temporary fixture trees stayed under `.astra_tmp/compact-tests` and were
removed afterward. They were synthetic repositories or archive exports, never
clones or additional worktrees.

| Run | Outcome |
| --- | --- |
| Initial Git boundary, hygiene, registry, repository identity baseline | 22 passed, 2 failed, 1 deselected |
| Initial compact + Git boundary + hygiene | 40 passed |
| Expanded compact/lifecycle focus | 63 passed, 1 deselected |
| Canonical assembly with pre-seal fixture | 7 passed |
| Expanded focus including assembly and shallow-boundary regression | 75 passed, 1 deselected |
| Broader release and packaging-boundary contracts | 121 passed, 2 deselected |
| Final combined release suite including registry | 137 passed, 2 failed, 2 deselected |
| Repository secret scan, separately after fixture cleanup | 1 passed |
| Authorized v3 assembly integration + compact core | 72 passed |
| Assembly integration, guard-disable regression, and release lifecycle | 100 passed, 1 deselected |

The two baseline and final failures are unchanged registry requirements:
the local tag set lacks `Elpis2.2.2`, and the failed-release authority test
cannot resolve `Elpis2.2.0^{tag}`. No fetch or tag repair was attempted.
The clone/fetch-based shallow-history test was excluded to respect this track's
no-clone/no-network boundary; a tiny local shallow-boundary regression exercises
the same fail-closed diagnostic. The whole-repository secret scan was excluded
from fixture-producing runs and passed afterward. Historical v2 compatibility
uses the unchanged `Elpis2.1.26` archive and catches a subsequent byte mutation.
The real candidate identity command passed. `git diff --check` and a diff over
all protected paths passed.

The final combined run covered these modules:

```
test_compact_release_manifest_v3.py
test_release_manifest_git_boundary.py
test_current_release_hygiene.py
test_canonical_assembly_verifier.py
test_release_repository_identity.py
test_release_lifecycle_ordering.py
test_release_tag_qualification.py
test_release_runtime_boundary_expansion.py
test_release_secret_scanner_modern.py
test_root_pytest_bootstrap.py
test_2_2_0_preseal_candidate.py
test_2_2_0_adoption_policy.py
test_2_2_1_release_information_coherence.py
test_2_2_2_release_information_coherence.py
test_2_2_3_pypi_workflow_repair.py
test_2_2_5_integration_release_prep.py
test_published_releases_registry.py
```

The assembly integration's initial test invocation encountered a missing
parent directory for its workspace-local pytest basetemp (7 passed, 65 setup
errors). Creating that parent resolved the invocation issue; the runs above
then passed. Its fixtures used `.astra_tmp/compact-assembly-tests` and were
removed after qualification.

The requested implementation commit and the post-approval retry were blocked before staging:
`.git/index.lock` could not be created because Git metadata is read-only in
this environment. No commit was created. HEAD remains the seed; the scoped
working changes are intentionally retained for review. Resume only with Git
metadata write access and resolve the remaining mutation-harness scope boundary above
before claiming complete successor-release adoption. No real seal, version
advance, publication, or historical authority change is part of this work.
