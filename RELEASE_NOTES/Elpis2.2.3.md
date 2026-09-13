# Elpis2.2.3

## Version: v2.2.3

Elpis2.2.3 is a bounded publication-workflow repair successor.

The immutable Elpis2.2.2 GitHub Release was published successfully, but its
release-event `pypi-publish` workflow failed before artifact construction because
the `Verify checked-out tag identity` shell command contained an unmatched quote
and parenthesis around `git rev-list`.

This successor repairs that syntax defect and adds an explicit
`workflow_dispatch` recovery input, `release_tag`. Both release-triggered and
manual-recovery executions resolve one `RELEASE_TAG`, check out that immutable
tag with full Git history, require `VERSION` and Git HEAD to match it, run strict
repository identity, export the exact tag with `git archive`, verify the Git-less
release tree, build and `twine check` the distributions, and only then pass the
artifact to the isolated `pypi` OIDC publish job.

The manual recovery path exists to finish publication of an already-published
immutable GitHub Release without deleting, recreating, or moving its tag. It does
not permit publishing arbitrary working-tree state: the requested value must be
an immutable Elpis release tag whose own strict repository identity passes.

No model, ECS, Grid81, learned-guidance, execution-authority, public-component
admission, or scientific claim changes in this successor.
