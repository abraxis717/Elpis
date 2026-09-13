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
