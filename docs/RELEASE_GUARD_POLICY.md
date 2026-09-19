# Release guard closure rule

No guard merges without a mutation test that demonstrates its negative branch
firing for the intended reason, and that mutation must previously have been
shown to pass against the unpatched guard. Record the source revision, mutation,
exit status, and diagnostic. A nonzero exit for an unrelated reason is
`WRONG_GUARD_FIRED`, never qualification.

Keep a clean positive control. Run the permanent regression in CI. For newly
introduced controls, also disable the specific control in an isolated copy and
show that the regression detects its absence. Unit isolation does not replace
installed-package and native transaction qualification.

Seal only after implementation qualification. A provisional seal is confined to
an explicit throwaway copy and makes no correctness claim. Historical release
manifests and tags are immutable.

## Structural-guidance runtime static tripwire

The structural-guidance source scan is an **enumerated AST regression
tripwire**. It rejects the import roots, builtin calls, `os.system` forms, and
static `getattr` patterns explicitly implemented in
`tools/verify_public_release.py`, recursively across the shipped
`structural_guidance` Python tree.

This control is **not a Python sandbox**, not an allowlist proof, and not a
proof that arbitrary Python execution techniques are impossible. Dynamic
attribute construction, reflection, deserialization, alternate process APIs,
or other execution mechanisms outside the enumerated patterns are not claimed
to be covered merely because this tripwire passes.

Accordingly, historical release wording about detecting execution-policy
"bypass classes" must be read as referring to the specifically enumerated
regression classes, not to complete semantic coverage of Python execution.
Broader execution authority remains controlled by the runtime's separate
authority invariants and negative authorization checks.


## Release lifecycle

Release identity has two distinct repository states and they must not be
collapsed into one check.

1. Qualify and commit the candidate locally. In a Git checkout before the
   release tag exists, candidate repository identity must prove that `HEAD`
   resolves, every ratified release-identity commit exists, and every such
   authority commit is an ancestor of `HEAD`. Absence of the future release tag
   is not a candidate failure.
2. Push the exact qualified candidate commit to public `main` by fast-forward
   only. Require the exact pushed SHA's main-push workflows to pass before any
   release tag is created.
3. Create the annotated release tag only at that exact hosted-green candidate
   SHA. Historical release tags remain immutable.
4. Require tag-triggered qualification to pass. Strict tagged repository
   identity requires the VERSION-selected tag to exist, resolve exactly to the
   checked-out `HEAD`, and contain the ratified identity commits in its ancestry.
5. Publish the GitHub Release only from the qualified immutable tag. Release
   publication may then trigger package build/publication workflows.
6. Package publication must perform strict tagged repository identity before
   exporting the tag with `git archive`; the exported Git-less tree must then
   pass the normal byte/manifest/runtime/public-boundary verifier before build.

The normal public verifier is lifecycle-aware: Git-less release archives treat
repository ancestry as non-applicable; Git checkouts use candidate repository
identity and additionally reconcile a release tag whenever it already exists.
`--verify-candidate-repository-identity` requires Git and performs the candidate
repository identity proof explicitly. `--verify-repository-identity` is the
strict tagged repository identity proof and requires the release tag to resolve
exactly to `HEAD`.

This ordering is itself a tested release contract. A main-push workflow must not
require a tag that policy forbids creating until after the main-push workflow is
green.


Repository-identity ancestry is only meaningful when the local Git object
database contains the ratified authority commits. Any CI job that invokes the
release verifier from a Git checkout must therefore use a full-history checkout
(`actions/checkout` with `fetch-depth: 0`). The verifier must never fetch
history itself. A shallow checkout that cannot resolve a ratified authority
commit fails explicitly as `REPOSITORY_HISTORY_INCOMPLETE`; after the caller
supplies full history, the same proof must pass.

## Current-release hygiene invariant

A VERSION advance is one atomic repository operation, not an informal release
intention. Before a successor may be sealed, the current VERSION must agree
with `pyproject.toml`, `CITATION.cff`, the README release line/current-note
link, `RELEASE_NOTES/README.md`, a current release-note file, the CHANGELOG
head, and a ratified entry in `tools/verify_public_release.py`.

The current-release hygiene test is generic and must remain in the early hosted
release-lifecycle gate. A successor manifest may be absent only during the
explicit pre-seal lifecycle. Once present, its version/tag and required release
files must agree with VERSION.

Publication authority has two explicit generations.

`PUBLISHED_RELEASES.json` is frozen legacy v1 publication history. Its bytes are
immutable after publication-authority v2 admission. `--append-tag` is no longer
an authorized transition and must fail closed.

`PUBLICATION_ASSERTIONS.json` is the append-only v2 publication-fact authority
for Elpis2.2.19 and later publication closeouts. A v2 assertion is created only
from an explicit external-observation receipt after the immutable annotated tag,
tag-triggered qualification, GitHub Release publication, release-event
qualification, PyPI publication, and exact wheel/sdist witnesses have been
observed.

In a Git checkout, v2 verification binds the exact annotated tag object to its
peeled commit and hashes the release manifest bytes read from that tagged commit
tree. The checkout copy must equal those tagged bytes. In a Git-less release
export, the verifier still proves v2 structure, frozen-v1 identity, exported
manifest bytes, witness coherence, ordering, failed-release exclusion, and
witness uniqueness, while explicitly deferring Git-object re-proof.

Do not pre-register an unpublished successor in either registry. Release
closeout is not complete while GitHub Release, PyPI, or the v2 publication
assertion lags the released VERSION. External observation and repository
authority mutation remain separate operations: the v2 registry tool consumes a
receipt and performs no network discovery itself.

Compact successor authority is explicitly opt-in with `seal_release.py
--schema v3` after 2.2.6. Elpis2.2.6 and every historical release retain their
existing manifest schema and bytes. See [Compact release authority](COMPACT_RELEASE_AUTHORITY.md)
for the canonical digest, publication exclusions, and Git tree projection.
V3 requires included HEAD, index, and physical bytes/modes to agree before
sealing. Commit included changes first, seal, then commit the excluded record.
The compact tree check does not replace candidate or strict tagged repository
identity, and never introduces a pre-tag requirement.

Hosted repository-completeness must be reproduced locally before the real
write-once seal. Tests for source-only integration surfaces must declare their
minimal roots explicitly and stay separate from installed-artifact
qualification. Do not repair collection failures by restoring ambient
`PYTHONPATH` leakage or accidentally expanding package discovery.
