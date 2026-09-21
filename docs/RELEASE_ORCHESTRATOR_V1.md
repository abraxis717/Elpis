# Release orchestrator v1

`tools/release_orchestrator.py` implements release closeout as a deterministic
state machine. `tools/release_orchestrator_io.py` supplies the production
Git/Actions/GitHub Release/PyPI adapter. Importing either module has no effects.
The default CLI validates an intent and prints a plan without invoking a command,
opening a network connection, creating a journal, or mutating the checkout.

## Authority and entry boundary

The existing release guard policy, compact v3 authority, and publication authority
v2 remain authoritative. All releases through 2.2.25 are explicitly excluded from
this new mutation surface. No historical manifests, notes, registries, failed
dispositions, or tags are migrated.

V1 starts from a **locally qualified, committed, sealed successor**. The release
owner still prepares atomic version metadata, runs implementation qualification,
uses the existing write-once `seal_release.py --schema v3`, and commits the seal.
`LOCAL_QUALIFIED` admits the explicit qualification report; `SEALED_CANDIDATE`
revalidates the committed seal and candidate repository identity. These are
admission transitions, not an alternate sealer or permission to reseal. This
boundary keeps provisional sealing and version preparation outside a process
authorized to publish. It also allows the complete intent to name its candidate
SHA and manifest digest before any network mutation.

The 2.2.19 notes identify the original crash window: remote mutations need a
journal acknowledgment before follow-up verification. They also record how
2.2.18 was tagged but unpublished. The 2.2.20 publication primitive separates
observation from assertion and makes v1 history frozen. The 2.2.22 notes record
2.2.21's main SHA and failed Component attribution run, with no tag or publication.
The 2.2.23 and 2.2.24 assertion commits (`8c81500`, `ba3c3db`) follow their seal
commits (`d0e90f7`, `f75ea4f`). The 2.2.25 seal at `37fdac9` and its existing tag
remain immutable. These facts require independent main, tag, and publication
states; none can stand in for the next.

## State model

```text
LOCAL_QUALIFIED
  -> SEALED_CANDIDATE
  -> MAIN_PUSHED
  -> MAIN_HOSTED_GREEN
  -> ANNOTATED_TAG_LOCAL_CREATED
  -> ANNOTATED_TAG_CREATED
  -> TAG_HOSTED_GREEN
  -> GITHUB_RELEASE_PUBLISHED
  -> RELEASE_EVENT_GREEN
  -> PYPI_WORKFLOW_GREEN
  -> PYPI_EXTERNALLY_OBSERVED
  -> PUBLICATION_RECEIPT_READY
  -> PUBLICATION_ASSERTION_APPENDED
  -> CLOSED
```

The additional local-tag transition makes a crash between local tag creation and
remote tag push explicit. Both happen only after the exact public main SHA's four
required workflows pass. The annotation bytes, object ID, and peeled commit are
deterministic from the intent. A local tag uses create-only `update-ref` with an
all-zero expected old value. A remote tag push never uses a force option.

Main publication proves `main_before` is an ancestor of `candidate_sha`, then
pushes exactly that SHA with an explicit expected-old-value lease. The lease is
a compare-and-swap constraint; the independent ancestry check prohibits a
non-fast-forward change. `--no-follow-tags` prevents an incidental tag push.
The explicit GitHub repository URL is used instead of an ambient remote alias.

All four workflows (CI, reference-runtime, Component attribution, platform-matrix)
must be green independently for main and tag. The exact workflow path, name,
repository, event, head ref, SHA, run ID, attempt, status, conclusion, and timestamps
are recorded. Pagination is explicit and capped censuses fail closed. Multiple
matching runs are ambiguous; reruns are forbidden. A failed required workflow
durably terminates this intent even if someone later deletes or reruns it.

The GitHub Release must match the tag, exact candidate target, title, and note
bytes, and be published rather than a draft/prerelease. The returned Release ID
is recorded before its subsequent GET and must match that observation. The
release-event CI and PyPI workflow are separate required witnesses. Workflow
dispatch is not substituted for publication authority v2's release-event witness.
This orchestrator never uploads to PyPI or dispatches/retries a publication job;
the existing release-published workflow is the sole publication trigger.

PyPI observation requires exactly one wheel and one sdist for `elpisai` and the
exact version, with filenames, SHA-256s, upload timestamps, and false yanked flags.
Release-event run creation and file upload times cannot predate the release.
Tag qualification completion cannot postdate release publication. The v2 receipt
is validated before its identity is durably recorded, and the existing locked,
atomic `append_receipt` is the only registry mutation operation.

`CLOSED` means external publication and the local v2 assertion agree. The assertion
is deliberately left as a reviewable worktree change. Committing/pushing that
closeout change is outside this command's authority; the release candidate remains
the immutable main/tag identity throughout the machine.

## Versioned data contracts

All JSON digests use SHA-256. Intent/report file digests hash their exact file
bytes; journal links, receipt identities, and assertion identities hash sorted-key,
compact UTF-8 JSON with one trailing newline (`publication_assertions_v2`'s
canonical encoding). Git object IDs use the repository's SHA-1/SHA-256 format.

An `elpis.release-orchestrator.intent.v1` has exactly these fields:

| Field | Meaning |
| --- | --- |
| `schema` | `elpis.release-orchestrator.intent.v1` |
| `repository` | Exactly `abraxis717/Elpis` |
| `version` | Explicit semver newer than 2.2.25 |
| `candidate_sha` | Full committed seal SHA, also required local HEAD |
| `manifest_sha256` | Exact candidate-tree manifest bytes |
| `main_before` | Full expected old public main SHA |
| `tagger` | Git ident `Name <email> epoch +HHMM`, fixed across retries |
| `qualification_sha256` | Exact local qualification report file digest |
| `notes_sha256` | Exact successor release-note file digest |

The tag name is the strict version-derived `Elpis<version>`, not a branch, search,
latest release, or fuzzy version selector. Tag content is specified by
`tag_bytes()`; the dry-run prints its exact expected object identity. The tagger
timestamp is object identity, not proof of hosted qualification or creation order.

The `elpis.release-orchestrator.qualification.v1` report has exactly `schema`,
`candidate_sha`, `manifest_sha256`, and `checks`. Checks must contain exactly
`root_tests`, `release_lifecycle`, `negative_mutations`, `installed_artifact`, and
`native`; each contains its explicit `argv`, zero `exit_code`, and `output_sha256`.
Retain the underlying qualification logs with this report. This is trusted local
operator evidence, not a signature or a claim to rediscover test results remotely.
The normal verifier and candidate identity verifier run again during seal admission.

An `elpis.release-orchestrator.journal.v1` has exactly `schema`, the full immutable
`intent`, and `events`. Each event has `seq`, `previous`, `state`, `kind`, `data`,
and `sha256`. `previous` is the previous event digest (initially the intent digest).
The state order and event grammar are validated on every read. The chain detects
accidental editing/corruption; it is not a cryptographic signature against an
attacker with write access to the journal directory.

`elpis.release-orchestrator.receipt.v1` is an envelope containing `schema`,
`receipt_sha256`, and the complete publication-authority v2 `receipt`. The envelope
is journal evidence. The separate digest-named receipt file contains only the
existing v2 receipt shape, as required by `append_receipt`.

## Durability and reconciliation

The journal, receipt, and advisory lock live in
`<git-common-dir>/elpis-release-orchestrator-v1/`. All worktrees use the same lock.
The CLI holds that lock for the entire run, including observation waits. The OS
releases it after process death; no persistent lock-file deletion is needed.
Direct library users must hold this same lock around `Journal` and `Orchestrator`.

Before a mutation, an `intent` event is flushed, fsynced, atomically replaced, and
the containing directory fsynced. Immediately after successful command return,
the `returned` event follows the same durability protocol **before any subsequent
verification**. Only the next exact observation can create the `complete` event.
A failed write/fsync aborts execution. Successful remote writes are never undone.

On every invocation, including after `CLOSED`, the machine revalidates local
identity and reobserves every completed state. It then considers the next state:

| Journal / observation | Decision |
| --- | --- |
| No action record; exact effect already present and prerequisite evidence exists | Reconcile completion; do not repeat |
| Pending/returned action; exact effect present | Reconcile completion; compare returned identity where applicable |
| Completed action; effect absent or different | Fail with state-specific conflict; no recreation |
| Pending/returned action; effect absent | `AMBIGUOUS_MUTATION_OUTCOME`; no retry |
| Unattempted action; prerequisite facts proven; effect absent | Persist intent, perform once, persist return, verify |
| Read-only prerequisite pending | Wait, or exit 75 at deadline; resume same intent |
| Failed required workflow | Persist terminal `failed`; successor required |

An existing tag without recorded main qualification, or an existing release
without recorded tag qualification, is not adopted into a new journal. Losing the
whole journal is not equivalent to an ordinary process restart. A rolled-back
journal can reconcile remote progress only while retaining the prerequisite
qualification evidence. A main SHA that has advanced beyond the candidate is a
conflict, even if the new SHA is a descendant. The tool never guesses why it moved.

The absence case is intentionally conservative: a timed-out network request may
still be executing server-side. No generic client can prove exactly-once execution
using only an eventual 404 after a lost response. Restore observation/access and
resume when the exact fact appears. If the request provably never committed, an
operator investigation is needed; v1 supplies no journal-edit, force, reset,
rehabilitation, or retry-ambiguous-write switch.

The registry append has the same recovery rule. If atomic v2 replacement finished
before the acknowledgment, an exact existing entry completes the transition.
Different receipt identities fail; an old registry prefix or frozen-v1 change
fails. Neither a tag nor a successful workflow can synthesize an append receipt.

## Invocation

Keep intent, report, and logs under Git-private state or outside the publication
tree. The candidate checkout must remain clean except for this release's validated
postpublication registry append. Use a complete, dedicated checkout with its
historical authority objects already available; the verifier never fetches them.

```sh
python tools/release_orchestrator.py --intent /path/to/intent.json
```

That is a zero-command dry-run. After release authorization, the same command with
`--qualification /path/to/qualification.json --execute` enables effects. Execution
waits up to 3600 seconds, polling every 30 seconds. `--wait-seconds 0` requests one
observation pass; `--poll-seconds` accepts 1–60. Exit 0 means closed, 75 means pending,
and 1 means a conflict or failed qualification. Resume with identical input files
and checkout; do not construct a new intent to evade a failed release.

## Operational limits

Production requires Git, an authenticated `gh` against github.com, network access
to GitHub/PyPI, POSIX durable filesystem semantics, and an exclusive release window.
The local advisory lock does not coordinate different machines or human writers.
External concurrent deletion/recreation cannot be made atomic with GitHub Release
creation by a client-side journal; reserve the release namespace and main while
running. V1 fails on observed conflicts and offers no repair operations.

Live service publication has deliberately not been exercised during implementation.
Recorded-response adapter tests verify the expected API contract, not credentials,
branch protections, server availability, or deployment-specific workflow settings.
Run dry-run and inspect the fully qualified successor intent before enabling live
execution. The tool does not prepare metadata, generate the initial seal, execute
the operator's implementation qualification suite, or publish the local closeout
commit. Those entry/exit responsibilities remain explicit.

See `RELEASE_ORCHESTRATOR_QUALIFICATION.md` for this implementation's tests,
mutation evidence, source revision, and exact results.
