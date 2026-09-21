# Astra orchestrator qualification

Starting revision: `37fdac9` (`release: seal Elpis2.2.25 v3 manifest`).
Scope: release tooling, its three dedicated test modules, two new documents,
and registration of those tests in the existing hosted release-lifecycle gate.
No real release operation or remote mutation was executed. All new mutation
tests use in-memory effects, recorded HTTP responses, or isolated local Git
repositories. The real checkout's release tags and registries were not mutated.

## Commands and results

Commands run from the repository root use this environment:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$PWD/.git/astra-qualification/tmp"
```

This keeps all qualification scratch inside the requested checkout. The sandbox's
ambient temporary directory is read-only. Every pytest invocation uses
`-o addopts='' -q -p no:cacheprovider` and a distinct `--basetemp` beneath
`.git/astra-qualification/`. Full output is retained there and excluded from Git.

| Qualification | Result |
| --- | --- |
| Dedicated engine/adapter/mutation tests | **135 passed**, 13.65 s, exit 0 |
| Final focused tests plus child-process hermeticity audit | **149 passed**, 17.54 s, exit 0 |
| Guard-disable mutation run | **12 passed**, 0.26 s, exit 0 |
| Existing release lifecycle suite | **151 passed, 1 failed**, 50.63 s, exit 1 |
| Starting-revision hygiene positive control | **1 passed**, 0.44 s, exit 0 |
| Starting-revision scanner reproduction | **15 failed, 11 passed**, 0.21 s, exit 1 |
| Final repository root suite | **1842 passed, 16 failed, 32 skipped**, 239.89 s, exit 1 |
| Protected-file byte comparison against starting HEAD | **501 files checked, zero changes**, exit 0 |
| `git diff --check` | Pass, exit 0 |

Initial focused command (`focused-qualified.log`):

```sh
python -m pytest -o addopts='' -q -p no:cacheprovider \
  tests/test_release_orchestrator.py \
  tests/test_release_orchestrator_io.py \
  tests/test_release_orchestrator_mutations.py \
  --basetemp=.git/astra-qualification/pytest-focused-qualified
```

Final focused command (`final-qualified.log`) repeats those three files, adds
`tests/test_child_process_hermeticity_audit.py`, and uses
`--basetemp=.git/astra-qualification/pytest-final-qualified`. It includes the final
preflight guards against deletion of a previously recorded tag/release during an
uninterrupted run, and an explicit source-root environment for the lock-test child.

Mutation command (`mutations-final.log`):

```sh
python -m pytest -o addopts='' -q -s -p no:cacheprovider \
  tests/test_release_orchestrator_mutations.py \
  --basetemp=.git/astra-qualification/pytest-mutations-final
```

Existing lifecycle command (`lifecycle.log`):

```sh
python -m pytest -o addopts='' -q -p no:cacheprovider \
  tests/test_release_lifecycle_ordering.py tests/test_release_tag_qualification.py \
  tests/test_release_repository_identity.py tests/test_publication_assertions_v2.py \
  tests/test_published_releases_registry.py tests/test_release_sealer_guards.py \
  tests/test_seal_release_mutations.py tests/test_release_immutability_gate_integration.py \
  tests/test_compact_release_manifest_v3.py tests/test_current_release_hygiene.py \
  tests/test_tag_disposition_closure.py \
  --basetemp=.git/astra-qualification/pytest-lifecycle
```

Final root command (`root-final.log`), with no test-file exclusions:

```sh
python -m pytest -o addopts='' -q -p no:cacheprovider tests/ \
  --basetemp=.git/astra-qualification/pytest-root-final
```

The first root run (`root.log`) was **17 failed, 1841 passed, 32 skipped** in
236.56 s (exit 1). One failure was introduced by the process-lock test's missing
explicit child source roots. That was fixed and the 14-test hermeticity audit
passes in the final focused run. It was not waived or excluded.

The final full run has exactly the 15 baseline-reproduced scanner failures and
the preserved-seal hygiene failure described below. No orchestrator test or
hermeticity-audit failure remains. The root suite is **not green** in this sandbox;
the implementation is not represented as a fully qualified new release.

Fifteen scanner failures are reproduced on the untouched starting-revision export
(`baseline-scanners.log`): 14 in `test_ci_secret_scan.py` (11 positive secret/path
fixtures, two binary fixtures, and `TestRunScan::test_dirty_repo`) and
`test_public_path_hygiene.py::test_generic_scanner_still_detects_synthetic_host_paths`.
The existing scanner excludes any absolute path containing a `.git` component,
including these sandbox-local temporary fixtures. Its results are empty, so the
tests expecting a detection fail. The baseline reproduction command runs those
two targets with the same pytest/environment options and
`--basetemp=../pytest-baseline-scanners`. Those scanner controls were not modified.

The lifecycle failure is
`test_current_release_hygiene.py::test_current_manifest_and_published_registry_are_truthful_when_present`:
`PUBLICATION_GIT_WORKTREE_HEAD_MISMATCH`. The starting checkout contains the 2.2.25
manifest and tag, but its v2 registry ends at 2.2.24. The existing check therefore
compares the changed development tree to the preserved 2.2.25 seal. This guard
was not weakened and no publication fact was invented. An untouched
`git archive 37fdac9` export passes the same hygiene test, as recorded in
`baseline-hygiene.log`. That positive control ran under
`.git/astra-qualification/baseline` with its own temporary directory.

## Negative and interruption matrix

The dedicated suite exercises lost mutation responses at all five effectful
transitions; interruption after every `complete` and every `returned` record;
fsynced acknowledgment before first verification; duplicate full invocation;
stale backup reconciliation; absence after ambiguous requests; journal ahead of
reality; stale intent and corrupt journal chains; unexpected main SHA; wrong tag
object, lightweight tag, wrong peeled commit/type; existing correct tag without
main qualification; failed/cancelled/skipped workflows at all four gates;
wrong workflow SHA/ref/event/path/repository; reruns; duplicate run witnesses;
changed GitHub Release ID; draft/prerelease/tag/notes/target mismatches; incomplete
or truncated workflow censuses; HTTP authentication/rate-limit/server/transport
errors; incomplete/wrong/yanked PyPI observations; malformed receipt; conflicting
assertion; frozen-version rejection; disabled execution; and journal fsync failure.

The production v2 append test uses a real isolated Git repository, the exact
deterministic annotated object, and the existing publication authority validator.
It crashes after registry replacement but before journal acknowledgment, resumes
without another append, and proves the legacy file unchanged. It also exercises
production preflight against the legitimate postappend dirty registry. A separate
test proves local tag compare-and-swap refuses an existing lightweight ref.
The process-lock test proves a second process cannot acquire the common lock
until the first releases it. The durability test records file fsync, replacement,
and parent-directory fsync in that order.

## Guard-disable evidence

Qualified orchestrator source SHA-256:
`769f6b2711ad6ac0ff1e69ec372e4fca39e0a958e8375e50099aed7b28077c24`.
Final adapter source SHA-256:
`dbe614a67dc86660c29163361ee93740ea5a588227dc7ff442938c3a4ba23352`.

Each mutation runs the negative input against the original source and requires
the named diagnostic, then disables that precise `require` condition in an
isolated AST copy. The permanent diagnostic regression must detect the removal.
The harness records outcome codes: 1 = intended rejection, 0 = input accepted,
2 = a different guard fired. These are harness outcomes; the encompassing pytest
process exited 0 because all 12 removal-detection assertions passed.

| Disabled guard / original diagnostic | Original outcome | Disabled outcome |
| --- | --- | --- |
| `ANNOTATED_TAG_REQUIRED` | 1 | 2: `TAG_OBJECT_MISMATCH` |
| `TAG_PEELED_COMMIT_MISMATCH` | 1 | 2: `TAG_OBJECT_MISMATCH` |
| `TAG_OBJECT_MISMATCH` | 1 | 0: accepted |
| `MAIN_SHA_MISMATCH` | 1 | 0: accepted |
| `SEALED_CANDIDATE_MISMATCH` | 1 | 0: accepted |
| `WORKFLOW_SHA_MISMATCH` | 1 | 0: accepted |
| `WORKFLOW_REF_MISMATCH` | 1 | 0: accepted |
| `REQUIRED_WORKFLOW_FAILED` | 1 | 0: accepted |
| `WORKFLOW_RUN_ID_DUPLICATE` | 1 | 0: accepted |
| `PUBLICATION_RECEIPT_IDENTITY_MISMATCH` | 1 | 0: accepted |
| `PUBLICATION_ASSERTION_CONFLICT` | 1 | 0: accepted |
| `HISTORICAL_RELEASE_IMMUTABLE` | 1 | 0: accepted |

The two redundant-tag cases are explicitly **WRONG_GUARD_FIRED** in the disabled
copy, not successful qualification of the missing guard. JSON lines in
`mutations-final.log` retain every source digest, mutation, outcome and diagnostic.

## Readiness boundary

This qualifies the orchestration engine and its injected I/O contract, not a new
Elpis release. The current VERSION, all sealed release evidence and frozen history
remain unchanged. A real successor still needs metadata preparation, independent
implementation/installed/native qualification, a committed write-once seal, and
the explicit intent/report. The v1 command handles publication closeout from that
entry point and leaves its final local assertion for a separate reviewed commit.

No live-service smoke publication was performed. GitHub credentials, protections,
workflow deployment settings and PyPI availability remain operational preflight
responsibilities. A lost request with no observable outcome intentionally needs
investigation; the tool supplies no unsafe ambiguous-write retry. See the v1
contract for exclusivity and durable-filesystem assumptions.
