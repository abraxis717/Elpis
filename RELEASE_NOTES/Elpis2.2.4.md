# Elpis2.2.4

## Version: v2.2.4

Elpis2.2.4 is a bounded publication-workflow contract-test corrective successor.

The local Elpis2.2.3 candidate correctly repaired the PyPI workflow and added a
bounded `workflow_dispatch` recovery path, then passed canonical assembly,
focused release tests, normal/candidate repository identity, the expected
pre-tag negative gate, and mutation 22/22. Its full root suite exposed two stale
tests in `tests/test_pypi_trusted_publishing_contract.py`.

Those tests still required the old release-event-only literal
`${{ github.event.release.tag_name }}` archive expression. More importantly, one
test literally required the malformed `git rev-list` shell string whose unmatched
quote/parenthesis caused the already-published Elpis2.2.2 release-event workflow
to fail before artifact construction.

Elpis2.2.4 preserves the sealed local Elpis2.2.3 manifest unchanged and updates
the publication-contract tests to the repaired semantics:

- both `release: published` and explicit `workflow_dispatch` are admitted;
- manual recovery requires a `release_tag` input;
- both event paths resolve one `RELEASE_TAG`;
- checkout uses that immutable release tag with full history;
- VERSION and detached HEAD must match the resolved tag;
- strict repository identity runs before archive export;
- `git archive` exports exactly the resolved immutable tag;
- Git-less verification, build and `twine check` precede publication;
- the publish job remains isolated behind environment `pypi` with
  `id-token: write`;
- no password/token secret publication path is admitted.

No model, ECS, Grid81, learned-guidance, execution-authority,
public-component-admission, or scientific claim changes in this successor.
