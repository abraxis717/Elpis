# Elpis red-team review — abraxis717/Elpis @ b8d86e0 (VERSION 2.2.7)

Scope: full repository. PyPI/pip publication path excluded per instruction.
Method: clean shallow clone, local execution, five adversarial probes.
Epistemic labels: **[executed]** verified by running code here; **[read]** verified
by source inspection; **[inferred]** reasoning not directly executed.

---

## 0. Verification base

| Action | Result |
|---|---|
| `pytest ECS/tests` | **520 passed** [executed] |
| `pytest tests/` | fails only on: absent `torch`, shallow clone (`REPOSITORY_HISTORY_INCOMPLETE`), and `__pycache__` created by this run. No substantive failure. [executed] |
| `grep -rn <private-project-root>` | **0 hits** — prior remediation item closed [executed] |
| Probes | rollback, starvation, ECS cost, ledger cost, canonicalization divergence [executed] |

### What is correct and should not be touched

- `_commit` as a single centralized transition boundary; `causing_event_id` excluded
  from `state_root_projection()` so the after-root has no digest cycle. Attempted to
  break the live/replay convergence; it holds. [executed]
- `replay._apply_event` recomputes founding identity from
  `(next_founding_index, label, genesis)` instead of trusting the payload. [read]
- `EntityPort` sender attribution — correct repair of the M1A caller-selectable-sender
  defect. No sender parameter reaches the entity-facing API. [read]
- `persistence.py` retracting the syscall-atomicity overclaim in favour of
  "recoverable framed append + complete-frame recovery". Honest scoping. [read]
- `src/elpis_reference/ecs_r0.py::verify_authority` — **the strongest verifier in the
  repository.** Symlink rejection on every ancestor, no verification cache, exact
  manifest entry set and manifest/header digests pinned in source, NaN/Inf rejected by
  exponent-bit inspection without float parsing. [read]

The existence of `verify_authority` matters for finding **F1**: the project demonstrably
knows how to write a real verifier. The promotion planner simply did not.

---

## F1 — CRITICAL — Promotion-planner gates assert self-reports, not recomputation

`components/Grid81DeterministicCanonicalPromotionPlanner/src/elpis_grid81_promotion_planner/gates.py`

Five of twenty gates in `_GATE_FUNCTIONS` do not check what their docstring claims. [read]

| Gate | Docstring claim | Actual body |
|---|---|---|
| `_check_dispositions` | phase disposition valid | `if not phase.disposition` — non-empty string test. A `*_FAILED` disposition **passes**. |
| `_check_artifact_identity` | "G5.3C receipts must reference artifacts produced by G5.3B.1" | `if not chain.g53c.artifact_digest` — truthiness. No cross-phase comparison exists. |
| `_check_capability_identity` | "capability digests must be consistent" | truthiness. No comparison exists. |
| `_check_compiler_identity` | "G5.3C compiler must reference G5.3B.1 upstream identity" | two `os.path.exists` calls. Neither file is opened. |
| `_check_no_executable_authority` | planner has no executable authority | `if f"import {mod}" in content` over `.py` text |

`_check_no_executable_authority` additionally **excludes `gates.py`, `verifier.py`,
`adversarial_matrix.py`** from its own scan — the three largest files in the package
(672 of 1,542 non-`__init__` lines). The substring form is defeated by `__import__`,
`importlib.import_module`, `from subprocess import run`, or `import  socket`.

`_verify_file_hashes` and `_check_receipt_integrity` **do** recompute correctly. That
makes the vacuous five worse, not better: the gate table reads as uniformly rigorous
and is not. A gate that cannot fail still consumes a `REJECTION_PRECEDENCE` slot and
still emits a passing receipt.

### F1b — the pattern has already propagated

`components/Grid81DeterministicStructuralAdjudicator/src/elpis_grid81_adjudication/verifier.py:216`
carries the same `f"import {imp}" in content` scan. Its `FORBIDDEN_IMPORTS` list
includes `"CUDA"`, `"llama.cpp"`, `"scheduler"`, `"router"`, `"capability_issuer"`,
`"capability_consumer"` — none of which can ever appear as `import <token>` in valid
Python. Those six entries are **unmatchable by construction**; the guard reports clean
regardless of file contents. [read]

### F1c — disposition is scraped from a human document

`source_binding._find_disposition` derives a gate input by scanning
`G53*_FINAL_REPORT.md` for the first line matching `startswith("G53") and "_" in line
and not startswith("#")`. A markdown report is an authority input. [read]

**Ruling:** this is the G2 defect recurring inside the promotion-authority path — the
exact failure `reference_kernels/qualification_verifier.py` was authored to prevent
("verification is recomputation, never trust"). Every one of the five gates must either
recompute or be deleted. Deletion is preferable to a gate that cannot fail.

---

## F2 — CRITICAL — Quadratic commit cost; hard ceiling near 10^3 events

[executed] Same host, no other load.

**ECS kernel**

| events | commit total | per-event | `topology_analysis()` |
|---|---|---|---|
| 404 | 1.33 s | 3.3 ms | 0.43 s |
| 804 | 4.76 s | 5.9 ms | 1.56 s |
| 1604 | 19.18 s | 12.0 ms | 5.77 s |

**`DurableApplicationLedgerV2.append`** marginal cost:

| n | 100 | 200 | 400 | 800 | 1200 |
|---|---|---|---|---|---|
| ms/append | 3.5 | 6.7 | 11.9 | 21.3 | 34.1 |

1,200 ledger entries = 25.6 s cumulative. Both curves are linear-in-`n` marginal,
i.e. quadratic total.

### Causes — ECS

- `_clone_state` is `copy.deepcopy` of the entire projection, per commit.
- `KernelState.state_root()` canonical-serializes and SHA-256s the **whole** entity
  registry plus **all** mailbox contents. `_commit` computes it **four times** per
  transition: `before_root`, `after_root`, and once more inside each of the two
  assertions at `kernel.py:313` and `:316`.
- `topology_projection()` re-reads and re-verifies the full log and re-runs full replay
  on every call. `topology_analysis()` calls it again.
- Mailbox entries are created lazily and **never removed**. A drained mailbox persists
  in the state root as an empty record, so the root grows monotonically with distinct
  receivers and never shrinks. [read]

### Causes — ledger

`append` calls `_require_valid` twice; `_require_valid` runs `PRAGMA integrity_check`
over the whole database plus a full chain walk plus a full association set-comparison.
The class docstring is honest about this ("append cost is not characterized as merely
linear in entry count"), which does not make it usable.

### Required work (new code, not a patch)

1. Incremental state root: per-entity subtree digests folded through a Merkle tree;
   recompute only the touched entity and the touched mailbox.
2. Copy-on-write projection in place of `deepcopy`.
3. Cache `TopologyProjection` keyed on `(log head digest, event_count)`.
4. Ledger: move `PRAGMA integrity_check` out of `append` into an explicit
   `verify_chain()`. On append verify only the tail link — the chain is already
   inductively verified at open.

This is the single item that decides whether the ECS is a runtime or a demonstration.

---

## F3 — HIGH — The anti-rollback anchor is built, written, read, verified, then discarded

[executed] 14 committed events; `checkpoint()` at index 13; `ftruncate` the log to a
**complete** frame boundary dropping the last two events; reopen.

```
REOPEN AFTER SILENT TRUNCATION: OK
  events before: 14   after: 12
  root before  : 210448aae4ff10f3
  root after   : f00608ea2bc50e4a
  checkpoint on disk claimed event_index: 13 clock: 14
```

`Kernel.open` reads the checkpoint and passes it to `replay_with_checkpoint`, whose
entire body is `return replay_from_events(genesis_digest, events, mailbox_capacity)`.
The `checkpoint` argument is never referenced. The truncated chain verifies because a
prefix of a valid chain is a valid chain.

`ECS/README.md` nonclaims "detection of a wholly rewritten valid history without an
external trusted head" — fair, and this finding does not dispute it. But this is not a
rewrite. It is `ftruncate`, it is the cheapest possible attack, and the anchor that
catches it is already on disk, already field-validated by
`verify_checkpoint_fields`, and already in scope at the call site.

### Patch — surgical, replaces `replay.replay_with_checkpoint` entire

```python
def replay_with_checkpoint(
    genesis_digest: str,
    events: Sequence[Mapping[str, Any]],
    checkpoint: Mapping[str, Any] | None,
    mailbox_capacity: int = DEFAULT_MAILBOX_CAPACITY,
) -> KernelState:
    """Full replay, anchored against the checkpoint marker.

    The checkpoint cannot skip replay work and is not an alternate
    authority. It is a monotonic floor: a history that no longer
    contains the checkpointed event has been rolled back and is
    rejected. Appends after the marker remain legitimate.
    """
    state = replay_from_events(genesis_digest, events, mailbox_capacity)
    if checkpoint is None:
        return state
    index = checkpoint["event_index"]
    if index >= len(events):
        raise WrongAuthorityError(
            "HISTORY_ROLLBACK: checkpoint event_index is ahead of the log"
        )
    if events[index]["event_digest"] != checkpoint["event_digest"]:
        raise WrongAuthorityError(
            "HISTORY_DIVERGENCE: checkpoint event digest absent from this history"
        )
    if index == len(events) - 1 and \
            state.state_root_digest() != checkpoint["state_root_digest"]:
        raise WrongAuthorityError(
            "HISTORY_DIVERGENCE: checkpoint state root mismatch at tail"
        )
    return state
```

`index < len(events) - 1` stays legal, so existing tests are unaffected. Update the
`Checkpoint` docstring: it stops being "advisory" the moment it is load-bearing.

---

## F4 — HIGH — `ECS/tests` never executes in CI

`grep -n ECS .github/workflows/ci.yml` returns four hits, all inside the
`repository-completeness` inline Python for `ecs_r0`. `pyproject.toml` sets
`testpaths = ["tests"]`; `repository-completeness` runs `pytest tests/`. Neither reaches
`ECS/tests` (22 files, 520 tests) or `ECS/qualification/run.py`. [read]

The newest and most authority-bearing runtime in the repository has **zero** CI
coverage, while HACF gets a full ASAN+UBSAN matrix with pinned test counts. The suite
passes today; that is luck, not a gate.

```yaml
  ecs-kernel:
    name: ECS M1A-R1 kernel suite
    runs-on: ubuntu-latest
    env:
      PYTHONDONTWRITEBYTECODE: '1'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install pytest==9.0.2
      - run: PYTHONPATH=ECS/runtime python -m pytest -q -p no:cacheprovider ECS/tests
      - run: PYTHONPATH=ECS/runtime python ECS/qualification/run.py
```

---

## F5 — HIGH — 51 runtime invariants are `assert` statements

`python -O` deletes every one. [executed: count] [read: sites]

Load-bearing examples:

- `ECS/runtime/elpis_ecs/kernel.py:313,316,319` — the commit-boundary root and
  logical-clock invariants.
- `src/elpis_reference/structural_guidance/_authority/c2r6p0/projector.py:237` —
  writable-mask violation check.
- `.../c2r6p0/projector.py:252` — `authority_residual(grid, invariants) == residual_ids`.
- `.../c2r6p0/projector.py:255` — `materialisable(grid, schema)`.
- `src/elpis/logic/account.py:401,404,410,423` — budget conservation
  (`total == initial_val`), i.e. the affine-account invariant.

Against a stated fail-closed-on-divergence posture, an invariant that evaporates under
an optimization flag is not an invariant. Convert every non-test site to an explicit
`raise`, then add a CI grep that fails on `^\s*assert ` outside `tests/`.

For `_commit` specifically the first assertion is also pure cost: nothing mutates
`state` between the two calls, so it recomputes an entire state root to prove a
tautology. Delete it; convert the other two to raises.

---

## F6 — MEDIUM-HIGH — Scheduler is strict priority by `entity_id`, and priority is grindable

`scheduler.py` docstring claims "simple deterministic fairness". The ordering tuple is
`(rank, entity_id, mailbox_index, message_id)`, so the lexicographically lowest receiver
mailbox drains completely before any other mailbox is touched.

[executed] Four entities, capacity 4, producer refilling the low mailbox each step:

```
served order: ['196f51'] x 12
hi mailbox still queued: 1
```

Indefinite starvation. Deterministic, yes. Fair, no.

Worse, the priority class is **grindable**. `entity_id = H(founding_index, label,
genesis)` and `founding_index` is predictable for the first entity a host founds.
20,000 label trials computed offline against the default genesis: [executed]

```
min entity_id prefix: 00028849   (label "L611")
unground "agent"    : 925ac89c   -> grinder permanently outranks
```

A caller who chooses labels obtains permanent scheduling priority over every honest
entity, for the life of the history, at a cost of seconds of offline hashing.

### Coupled constraint — there is currently no migration path

`replay._apply_event` hard-enforces `receiver == ready_receivers[0]` for
`MESSAGE_PROCESSED`, and `PROTOCOL["scheduler"]` is bound into
`genesis_descriptor_digest`. Any scheduler change therefore invalidates **every**
existing history via `WRONG_GENESIS_OR_CAPACITY`. Fail-closed and correct — and it means
the cost of this decision rises monotonically with every history committed.

Options: order by commit clock (arrival) with `entity_id` as tie-break only; or explicit
round-robin across mailboxes with a per-tick quantum. Either needs a protocol-version
migration story written **before** more histories accumulate.

---

## F7 — MEDIUM — Three incompatible canonicalization conventions coexist

[executed] Same domain, same payload, two modules in this repository:

```
ECS canonical_bytes     : b'{"label":"caf\xc3\xa9","note":"na\xc3\xafve"}'
closure canonical_bytes : b'{"label":"caf\\u00e9","note":"na\\u00efve"}'
identical bytes         : False

ECS  domain_digest("x.v1", p) : 1bfb7ce0439a7576...
closure content_checksum(...) : 829f2d7675e75910...
                              : TWO DIFFERENT IDENTITIES
```

Divergence is twofold:

1. **Framing.** `elpis_ecs.canonical.domain_digest` hashes
   `canonical_json({"domain": d, "payload": p})`. `ecs_r0._json_digest`,
   `elpis.contracts.closure.identity.content_checksum`, and the whole
   `structural_guidance` family hash `domain || NUL || canonical_json(p)`.
   `reference_kernels/_canon.py` uses neither — a bare `__record__` tag, no domain.
2. **Byte form.** ECS uses `ensure_ascii=False`; closure uses `ensure_ascii=True`.
   The digests differ even for ASCII-only payloads because of (1), and the *bytes*
   differ for any non-ASCII payload because of (2).

Neither construction is unsound in isolation. The problem is that
`reference_kernels/content_identity.py` was authored precisely to rule on this
("reserialization invariance: equivalent canonical content under different encodings
yields an identical primary digest"), and that ruling has not been applied. Any future
cross-component digest comparison — federation, promotion, evidence binding across
planes — silently produces two identities for one artifact.

Ratify one canonicalization spec and one domain-separation framing; make every module
import it rather than redeclare it.

---

## F8 — MEDIUM — The canonical math spec states the superseded stability condition

`<external-skill-authority>/SKILL.md` §A.19 gives the sufficient local-stability condition as

```
rho(J_x F_{n,k}) < 1 - delta
```

— the spectral **radius**. The project's own ratified position (JSR renamed **JSN-R**,
Jacobian spectral *norm*) is that `rho` is the wrong quantity, and
`reference_kernels/jacobian_spectral_norm.py` carries the executable counterexample:

```
A = [[0.9, 10], [0, 0.9]]   rho(A) = 0.9 < 1 < sigma_max(A) > 10
one-step gain on e2 = 10.04  -> transient amplification
```

A `rho`-qualification passes this operator. A `sigma`-qualification fails it. §A.19
therefore states a condition that does **not** imply the contraction bound §A.19 goes on
to assert two paragraphs later. Correct the spec to `||J_x F||_2 < 1 - delta`.

Secondary, same section: the neighborhood bound `limsup E[||x - x*||] <= C*eps_max/(1-kappa)`
matches `epsilon_floor.delta_floor` numerically, but is written in expectation, whereas
the ratified `epsilon_floor` module states the bound is **deterministic worst-case**
under bounded designed noise and explicitly declines the expectation framing
("no sub-Gaussian or expectation assumptions are used or needed"). Align the wording.

---

## F9 — LOW — Documentation/code divergences

| Site | Divergence |
|---|---|
| `persistence.verify_event_fields` | documents `entity_id (None or str — the nullable/string contract)`, but `validate_payload` runs first and calls `_require_digest(eid, "entity_id")`. The nullable branch is unreachable. Fail-closed direction; the docstring is simply false. |
| `canonical.py` | `DOMAIN_STATE_ROOT = "ecs.state_root.v1"` while `persistence.STATE_ROOT_SCHEMA = "ecs.state_root.v3"`. The domain tag does not move with the schema. Harmless today because the schema string is inside the payload; a real collision risk the moment domain tags are used for routing. |
| `canonical.digest_bytes` | documented "domain-separated"; has no domain tag. |
| `topology_analysis.analyze_projection` | docstring: "does NOT validate authority". First statement: `verify_projection(projection)`. |
| `ECS/README.md` "Deferred milestones" | item 1 is "interaction-derived topology projection", shipped in 2.2.5. List is stale. |
| `EventLog` | `flock` is per-open-file-description (so the same-process double-open case is correctly rejected) but is advisory and unreliable on NFS. Given the local-sovereignty framing this deserves an explicit nonclaim line. |

---

## 10. Component-level assessment

### ECS kernel — the best-engineered code in the repository

Correct: centralized transition boundary, port-bound attribution, complete-frame
recovery, `_decode_record` requiring canonical round-trip (rejects any non-canonical
byte form even when the JSON parses), `AppendRolledBackError` distinguished from
indeterminate outcome, epoch-based port invalidation. Its problems are F2, F3, F5, F6 —
all of which are performance or policy, none of which are correctness of the committed
history.

### `topology.py` / `topology_analysis.py` (new in 2.2.5) — clean

Edge derivation reads only committed envelope attribution, never payload. The stated
threat model ("a payload that says 'I am connected to X' has no effect unless an actual
qualifying committed interaction fact independently establishes the edge") is the right
one and is honoured in `_fold_edges`.

The iterative Tarjan in `_strongly_connected_components` is **correct**. Specifically
checked: the `for succ in it: ... break` frame-resume preserves iterator position across
the `while` loop; the unconditional `lowlink[parent] = min(lowlink[parent],
lowlink[node])` on pop matches the recursive form; isolated nodes are seeded and emitted
as singleton SCCs; `cyclic` correctly distinguishes a self-looped singleton. Output is
sorted twice (members, then component tuples), so it is hash-seed independent.

Only defect is F2 — O(n) full replay per call.

### `durable_ledger_v2` (new in 2.2.5) — good separation, unusable cost

Correct: no inheritance from v1 (so publisher `isinstance` admission cannot accidentally
admit it), distinct `application_id`/genesis domain, refusal to convert an existing
journal mode, `BEGIN IMMEDIATE` for writes, inode-identity re-check on every operation,
`_require_digest` stricter than `int(value,16)`. The `_has_v2_header` raw-header read is
a TOCTOU but only routes ro/rw admission and the rw path re-verifies under the write
lock — acceptable. Cost is F2.

### `ecs_r0.py` — reference quality, one tradeoff

`verify_authority` is called on **every** `FrozenTheta.__post_init__`, re-reading and
re-hashing eight files per object construction. This is deliberate ("there is no
verification cache or caller-supplied trust receipt") and correct for TOCTOU — but it
should be measured before `FrozenTheta` is constructed in any loop.

---

## 11. Priority queue

| # | Item | Class | Effort |
|---|---|---|---|
| 1 | Fix or delete the five vacuous promotion gates (F1) | authority correctness | small |
| 2 | Same for the adjudicator's unmatchable `FORBIDDEN_IMPORTS` (F1b) | authority correctness | small |
| 3 | Land the `replay_with_checkpoint` anchor patch (F3) | fail-closed | one function |
| 4 | Add the `ecs-kernel` CI job (F4) | coverage | one job |
| 5 | `assert` → `raise` across 51 non-test sites + CI grep (F5) | fail-closed | mechanical |
| 6 | Correct §A.19 `rho` → `\|\|J\|\|_2` in the math spec (F8) | theory integrity | edit |
| 7 | Ratify one canonicalization spec; make modules import it (F7) | new code | medium |
| 8 | Incremental state root + COW + projection cache (F2) | new code | large |
| 9 | Ledger `integrity_check` out of the append path (F2) | new code | medium |
| 10 | Scheduler fairness decision **and** protocol-migration story (F6) | policy + new code | large |
| 11 | Anchor phase manifests outside their own directory | new code | medium |

Item 11: `source_binding.census_phase` digests the manifest, and `gates._verify_file_hashes`
recomputes every listed evidence file — that part is sound. But nothing anchors the
manifest itself. A tampered manifest with internally consistent hashes passes every gate.
`ecs_r0.EXPECTED`/`MANIFEST_SHA256` is the pattern to copy: pin the manifest digest in a
sealed authority record outside the phase directory.

---

## 12. Probes

Reproductions were executed in external red-team scratch space and are not shipped in this repository. The original probe filenames were:
`probe1_rollback.py`, `probe2_starve.py`, `probe3_cost.py`, `probe4_ledger.py`,
`probe5_canon.py`. Each is standalone, needs only `sys.path` into `ECS/runtime` and the
relevant component `src`, loads no model, opens no socket.
