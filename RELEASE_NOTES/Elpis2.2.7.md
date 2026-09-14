# Elpis2.2.7

## Version: v2.2.7

Elpis2.2.7 is the hosted repository-hygiene corrective successor to the sealed
but untagged Elpis2.2.6 candidate.

Elpis2.2.6 passed local provisional qualification and was sealed, committed,
and fast-forwarded to public `main`. Hosted main qualification then failed in
exactly one job: `Repository completeness and installed artifact`. Every other
CI job passed, including public release verification, candidate repository
identity, canonical assembly, release mutation guards, secret/private-path
scanning, native qualification, runtime R0/R1, sanitizer qualification, and
the remaining component suites. No Elpis2.2.6 tag or publication was created.

The failing job exposed two mechanics conflicts with the newly integrated
Hermes hygiene contracts:

1. The normal/root suite was invoked with `PYTHONPATH=""`. An empty value still
   exports the variable, while the isolation contract deliberately requires
   `PYTHONPATH` to be absent.
2. Repository-completeness dependencies were installed from the live checkout.
   The build backend generated untracked `build/` and `elpisai.egg-info`
   directories before `test_real_repository_is_clean`, which correctly
   rejected them.

The corrective job now:
- installs `elpisai[trm]` from a throwaway `git archive HEAD` extraction;
- leaves the checked-out repository pristine;
- invokes the normal/root suite through `env -u PYTHONPATH`;
- retains the three source-only Grid81 downstream integration tests in their
  explicit minimal-root lane;
- retains separate installed-artifact qualification from another pristine
  throwaway source copy.

`tests/test_current_release_hygiene.py` permanently binds these mechanics so
the checkout may not again be polluted before the repository-hygiene suite and
the normal lane may not again export an empty ambient `PYTHONPATH`.

There is no runtime, scientific, package-membership, or authority-semantics
change relative to 2.2.6. Astra's compact release-manifest v3 remains opt-in
future infrastructure. Elpis2.2.7 itself continues to use the historical v2
manifest path so the still-v2 mutation harness is not silently promoted into a
new release contract.

`PUBLISHED_RELEASES.json` remains unchanged until an immutable Elpis2.2.7 tag,
GitHub Release, and PyPI 2.2.7 publication actually exist.
