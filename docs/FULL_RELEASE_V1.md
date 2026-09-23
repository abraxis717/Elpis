# Full release v1

`tools/full_release.py` is the normal operator entry point once development
changes are committed and the working tree is clean.

```sh
python tools/full_release.py
python tools/full_release.py --execute
```

The first command is a zero-effect plan. `--execute` owns the complete lifecycle:

1. qualify the clean committed development successor before any release seal exists;
2. create and commit the write-once v3 seal under a durable outer mutation intent;
3. re-run the complete qualification suite against the exact sealed commit;
4. invoke the lower crash-safe release orchestrator for main/tag/Release/PyPI;
5. commit only the append-only publication assertion under outer mutation journaling;
6. separately commit `RELEASE_RATIFICATIONS/Elpis<version>.json`;
7. rerun publication verification, release verification, and full root;
8. CAS fast-forward public main from the immutable seal to the ratification commit
   using the fixed canonical repository URL;
9. require every release-required main workflow green on the exact closeout SHA,
   using the lower boundary's bounded paginated workflow census;
10. write a Git-private terminal `CLOSED.json`.

The pre-seal and exact sealed qualification suites both cover root tests, release
lifecycle tests, negative mutation tests, a real wheel build/install/import
qualification built from a private `git archive HEAD` export rather than the
authority worktree, and exact native/R3 executed-node qualification. The lower release
orchestrator receives only the exact sealed qualification report.

State, logs, intent, qualification reports, the hash-chained outer mutation
journal, and terminal receipt live under the common Git directory in
`elpis-full-release-v1/<version>/`. A repository-wide `full-release.lock` covers
the outer lifecycle. The lower orchestrator retains its own independent lock and
journal for remote publication mutations.

The outer journal writes durable `intent -> returned -> complete` events for the
seal commit, publication-assertion commit, ratification commit, and final-main
push. Resume reconciles exact repository/remote reality before deciding whether a
mutation must run, so a crash after a successful mutation does not authorize a
blind replay.

`release_orchestrator.py` remains authoritative for the main/tag/Release/PyPI
publication sequence and remains available for recovery/forensics. Ordinary
releases use only `full_release.py --execute`.


## Current-version lifecycle-neutral test contract

The permanent root suite for the active release version must not contain a
version-specific `*_prep.py` test. The one-shot release driver runs repository
qualification across multiple lifecycle states, including before and after the
write-once manifest exists and again after publication closeout.

Current-version release tests therefore must be lifecycle-neutral: they may
validate identity, write-once authority, and the manifest when present, but
must not require the manifest, tag, publication assertion, or publication
artifacts to be absent merely because the test was authored during successor
preparation.

`tests/test_current_release_lifecycle_neutrality.py` enforces this rule and is
part of `tools/full_release.py` lifecycle qualification.
