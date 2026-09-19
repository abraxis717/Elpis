# Elpis

**A deterministic structural-reasoning architecture for bounded learned proposals, explicit authority, and falsifiable runtime composition.**

**Release line: Elpis2.2.21**

Elpis is a systems-research project about a narrow question: can learned components contribute useful structural proposals while deterministic machinery retains ownership of representation, admissibility, authority, validation, and terminal action?

The repository is intentionally decomposed. It contains several qualified public surfaces that coexist under one release boundary but are **not automatically one runtime pipeline**: typed semantic and Grid81 control machinery, bounded learned structural guidance, native lexical/retrieval components, historical offline runtime integrations, a runnable public FPRM reference-model path, a separately frozen ECS Structural Authority R0 contract, and release/provenance enforcement.

That decomposition matters. A component can be present, qualified, and useful without being runtime-admitted into every other component. Evidence can establish a mechanism without granting that mechanism authority. A proposal can improve without becoming executable. A structural contract can be public and executable while still lacking a qualified semantic binding into another subsystem.

Elpis therefore presents itself as a falsifiable research artifact rather than a general intelligence claim. It does **not** claim solved alignment, trusted natural-language understanding, general Grid81 satisfiability, unrestricted autonomous execution, autonomous implementation synthesis, cross-process attestation, AGI, or ASI.

## Release Notes

**Elpis2.2.21** adds the isolated native inference-driver host and a bounded Needle3 proposal-only provider while preserving deterministic Elpis/ECS execution and state authority.

The isolated lane binds exact wheel bytes and canonical runtime context before loading provider code inside the qualified sandbox. It does not use the trusted installed-driver registry, does not automatically fall back between lanes, and does not grant R2 provider-resolution authority.

Needle3 is admitted only through the globally disabled `tool-proposal.needle3` port with `ON_DEMAND`, `PROPOSAL_ONLY`, network-denied and remote-code-denied semantics. The `elpisai` distribution does not bundle the Needle3 model artifact or separately qualified native wheel; ECS remains the execution, state, validation, and terminal-action authority.

The 2.2.x line includes:

- physical-tree-aware release manifests and immutable-tag `git archive` build provenance;
- lifecycle-aware repository identity, full-history hosted ancestry proofs, and annotated-tag object enforcement;
- repository-level immutable-evidence, append-only release-record, and model/checkpoint identity gates;
- canonical identity v1 receipt framing with an explicit direct SHA-256 sink census;
- portable root/package-derived inter-code bindings with Git-less relocation qualification;
- E0R3 whole-column participation referents with a qualified ECS R0 production consumer;
- qualified ECS Kernel -> topology projection -> topology analysis read-only composition;
- DurableApplicationLedger schema v2 consumed by the qualified G5.3C application path;
- the qualified Grid81 authority-to-publication chain: capability authority -> consumption compiler -> durable application -> promotion planner/authority -> isolated candidate constructor -> durable/atomic publisher;
- complete five-node writer-chain binding coverage while the legacy public assembly remains unchanged;
- bounded Regex/HACF/query-local proposal ingress with separate non-public coverage authority;
- current secret/private-path, static-language, runtime-boundary, and plugin-trust hardening;
- Branch36-40 science artifacts retained as evidence, not promoted to runtime API.

The immutable `Elpis2.2.0`, `Elpis2.2.9`, `Elpis2.2.12`, `Elpis2.2.15`, `Elpis2.2.16`, and `Elpis2.2.18` tags are retained as failed-not-published release evidence under `FAILED_RELEASES.json`.

- Current notes: [`RELEASE_NOTES/Elpis2.2.21.md`](RELEASE_NOTES/Elpis2.2.21.md)
- Public component registry: [`manifests/PUBLIC_COMPONENT_REGISTRY.json`](manifests/PUBLIC_COMPONENT_REGISTRY.json)
- Qualified writer-chain registry: [`manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json`](manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json)
- Qualified ingress-trio coverage: [`manifests/INGRESS_TRIO_COVERAGE_R0.json`](manifests/INGRESS_TRIO_COVERAGE_R0.json)
- Inference-plugin trust boundary: [`docs/INFERENCE_PLUGIN_TRUST_BOUNDARY.md`](docs/INFERENCE_PLUGIN_TRUST_BOUNDARY.md)
- 2.2 qualified-internal adoption policy: [`manifests/ELPIS_2_2_0_ADOPTION_POLICY_R0.json`](manifests/ELPIS_2_2_0_ADOPTION_POLICY_R0.json)
- Release-note archive: [`RELEASE_NOTES/`](RELEASE_NOTES/)
- ECS authority and science: [`ECS/`](ECS/)

## Install and quick start

The Python distribution project name is **`elpisai`**. The console command remains **`elpis`**, and the existing Python import-package names remain unchanged.

The PyPI name `elpis` belongs to an unrelated project. Do **not** use `pip install elpis` to obtain this repository.

### From a source checkout

Base installation uses only the base dependency set:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

The learned/reference-model path requires the optional `trm` extra:

```bash
python -m pip install ".[trm]"
```

### From PyPI

For a release that is available on PyPI, the distribution commands are:

```bash
python -m pip install elpisai
python -m pip install "elpisai[trm]"
```

PyPI publication is release-specific. If the requested version is not present on PyPI, install from the corresponding tagged source checkout rather than substituting the unrelated `elpis` distribution.

### Reference-model example

With the `trm` extra installed:

```bash
elpis model fetch
elpis model verify

elpis sudoku solve \
  --puzzle '.34678912672195348198342567859761423426853791713924856961537284287419635345286179' \
  --device cpu
```

The reference runtime verifies the pinned model identity and state ABI before loading. This demonstrates a reproducible model-integrity and Sudoku inference path. It does not establish generalized reasoning: **Sudoku capability is evidence of Sudoku capability.**

---

## 1. Research question

The central question is:

> **Can a learned component contribute useful structural search, proposal, or ordering information while a deterministic substrate retains ownership of representation, admissibility, authority, validation, and terminal action?**

Let `x` denote a typed request, `S` a structural state, `M` a learned proposer, `p = M(x, S)` a proposal, and `J` a deterministic adjudicator operating under an explicit contract `C`. The intended separation is:

```math
\begin{aligned}
p &= M(x,S),\\
S' &= J(x,S,p;C).
\end{aligned}
```

`M` must not be able to redefine `C`, widen its writable scope, grant itself capability, convert confidence into permission, or treat its own output as proof of admissibility.

Elpis uses **authority** operationally: the explicit capability to admit, reveal, consume, mutate, validate, execute, or otherwise advance a state transition. Authority is not synonymous with model confidence, heuristic usefulness, semantic plausibility, provenance evidence, or a successful test result.

Four separations recur throughout the project:

1. **Representation is not proposal.** A learned component does not silently own the task representation it later proposes against.
2. **Proposal is not admissibility.** Candidate material is not accepted merely because a model or producer emitted it.
3. **Validation is not execution.** A source artifact may pass a static policy while execution authority remains false.
4. **Evidence is not capability.** Receipts, digests, witnesses, and terminal results can prove bounded facts without becoming reusable permission.

---

## 2. Repository architecture: multiple bounded surfaces

The current public repository should not be read as one monolithic agent loop. Its major surfaces are better represented as follows:

```math
\begin{array}{c}
\boxed{\mathrm{ELPIS}}
\\[1em]
\begin{array}{ccc}

\boxed{
\begin{array}{c}
\text{Native semantic / retrieval}\\
\text{substrate}\\[0.35em]
\text{Streaming Regex}\\
\text{HACF retrieval}\\
\text{Query-local ingress}\\
\text{Semantic Spine}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Structural control / guidance}\\
\text{path}\\[0.35em]
\text{Semantic IR}\\
\text{Deterministic Projector}\\
\text{Grid81}\\
\text{TRM guidance}\\
\text{P1 / adjudication}\\
\text{Validated-source path}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Reference-model}\\
\text{path}\\[0.35em]
\text{FPRM authority}\\
\text{Pinned checkpoint}\\
\mathrm{elpis\ CLI}\\
\text{Sudoku inference}
\end{array}
}

\end{array}
\\[1em]
\Downarrow
\\[-0.1em]
\boxed{\text{Explicit authority / capability boundaries}}
\\[1.2em]
\begin{array}{ccc}

\boxed{
\begin{array}{c}
\text{ECS Structural Authority R0}\\[0.25em]
\text{Separate frozen structural contract}\\
\text{not silently identified with}\\
\text{Grid81 or Semantic IR}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Historical runtime integrations}\\[0.25em]
\mathrm{runtime/R0}\\
\mathrm{runtime/R1}\\
\text{Earlier qualified offline compositions}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Release / provenance authority}\\[0.25em]
\text{Manifests}\\
\text{Verifier and mutation tests}\\
\text{CI, tags, and releases}
\end{array}
}

\end{array}
\end{array}
```

**Repository coexistence does not imply runtime integration.** This is especially important for ECS Structural Authority R0, the native ingress components, canonical Grid81 state, historical R0/R1 integrations, and the public reference-model path.

### 2.1 Canonical public component registry

[`manifests/PUBLIC_COMPONENT_REGISTRY.json`](manifests/PUBLIC_COMPONENT_REGISTRY.json)
is the canonical 16-component public assembly registry. Every entry now carries
a machine-readable source URL plus documentation path/URL.

**Status vocabulary is explicit:**

- **public-registry admitted**: one of these 16 canonical public assembly entries;
- **qualified**: bounded implementation/evidence exists for the stated mechanism;
- **runtime admitted**: a separate property, still false for every public-registry component.

| Component | Source / docs | Qualification disposition | Admission | Role / boundary |
|---|---|---|---|---|
| [`HACF_R3`](native/hacf/README.md) | [`native/hacf/`](native/hacf/) | `SEALED_AND_PROMOTABLE` | `runtime_admission=false` | Native deterministic HACF substrate. |
| [`Semantic_Structural_Spine_V1`](native/semantic-spine/README.md) | [`native/semantic-spine/`](native/semantic-spine/) | `SEALED_AND_PROMOTABLE` | `runtime_admission=false` | Native semantic/structural spine over HACF. |
| [`Grid81_Structural_Semantics`](components/Grid81StructuralSemantics/README.md) | [`components/Grid81StructuralSemantics/`](components/Grid81StructuralSemantics/) | `QUALIFIED` | `runtime_admission=false` | Typed structural semantics for the Grid81 family. |
| [`Grid81_Typed_Projection_Compiler`](components/Grid81TypedProjectionCompiler/COMPONENT_MANIFEST.json) | [`components/Grid81TypedProjectionCompiler/`](components/Grid81TypedProjectionCompiler/) | `QUALIFIED` | `runtime_admission=false` | Deterministic typed projection. |
| [`G50b_Structural_Group_Projection_Compiler`](components/Grid81StructuralGroupProjectionCompiler/README.md) | [`components/Grid81StructuralGroupProjectionCompiler/`](components/Grid81StructuralGroupProjectionCompiler/) | `QUALIFIED` | `runtime_admission=false` | Structural group projection. |
| [`Grid81_Canonical_Substrate`](components/Grid81/README.md) | [`components/Grid81/`](components/Grid81/) | `QUALIFIED` | `runtime_admission=false` | Canonical Grid81 generation substrate and production reader. |
| [`TRMFractalSpine_Structural_Modules`](components/TRMFractalSpine/README.md) | [`components/TRMFractalSpine/`](components/TRMFractalSpine/) | `QUALIFIED` | `runtime_admission=false` | Structural TRM contracts and refinement surfaces. |
| [`G51b_Deterministic_Structural_Adjudicator`](components/Grid81DeterministicStructuralAdjudicator/README.md) | [`components/Grid81DeterministicStructuralAdjudicator/`](components/Grid81DeterministicStructuralAdjudicator/) | `QUALIFIED` | `runtime_admission=false` | Deterministic structural adjudication. |
| [`DarwinianMatrix`](components/DarwinianMatrix/README.md) | [`components/DarwinianMatrix/`](components/DarwinianMatrix/) | `QUALIFIED` | `runtime_admission=false` | Structural clamp, Projector, and bounded refinement mechanisms. |
| [`P0ControlProtocol`](components/Pipeline/P0ControlProtocol/README.md) | [`components/Pipeline/P0ControlProtocol/`](components/Pipeline/P0ControlProtocol/) | `QUALIFIED` | `runtime_admission=false` | P0 control, Semantic IR, projection, and validation contracts. |
| [`elpis_header`](native/elpis-header/src/elpis_header/observer/README.md) | [`native/elpis-header/`](native/elpis-header/) | `QUALIFIED` | `runtime_admission=false` | Header/runtime-side Grid81 observation contract. |
| [`G52b_Capability_Authority_Evaluator`](components/Grid81DeterministicCapabilityAuthorityEvaluator/COMPONENT_MANIFEST.json) | [`components/Grid81DeterministicCapabilityAuthorityEvaluator/`](components/Grid81DeterministicCapabilityAuthorityEvaluator/) | `QUALIFIED` | `runtime_admission=false` | Capability-authority evaluation. |
| [`G53b_Capability_Consumption_Compiler`](components/Grid81DeterministicCapabilityConsumptionCompiler/COMPONENT_MANIFEST.json) | [`components/Grid81DeterministicCapabilityConsumptionCompiler/`](components/Grid81DeterministicCapabilityConsumptionCompiler/) | `QUALIFIED` | `runtime_admission=false` | Capability-consumption compilation. |
| [`G53c_Capability_Application_Executor`](components/Grid81DeterministicCapabilityApplicationExecutor/COMPONENT_MANIFEST.json) | [`components/Grid81DeterministicCapabilityApplicationExecutor/`](components/Grid81DeterministicCapabilityApplicationExecutor/) | `QUALIFIED` | `runtime_admission=false` | Bounded capability application and ledger surfaces. |
| [`G53e_Canonical_Promotion_Planner`](components/Grid81DeterministicCanonicalPromotionPlanner/COMPONENT_MANIFEST.json) | [`components/Grid81DeterministicCanonicalPromotionPlanner/`](components/Grid81DeterministicCanonicalPromotionPlanner/) | `QUALIFIED` | `runtime_admission=false` | Advisory canonical promotion planning. |
| [`CNumPyCortex`](components/CNumPyCortex/README.md) | [`components/CNumPyCortex/`](components/CNumPyCortex/) | `QUALIFIED` | `runtime_admission=false` | Optional telemetry-to-Grid81 transport/recursion surface. |

The registry count remains **16**. Later qualified writer-chain components are
not silently inserted here because their manifests explicitly declare
`public_registry_admission=false`.

### 2.2 Additional qualified ingress components

These are qualified public repository surfaces but not entries in the 16-component
canonical public registry:

| Component | Surface | Qualified claim | Boundary |
|---|---|---|---|
| [`StreamingRegexIngress`](components/StreamingRegexIngress/) | Native bounded Regex producer | Stable bounded lexical ingress under the qualified carry/data profile. | Output remains `PROPOSED_UNADMITTED`; not arbitrary incremental-regex completeness. |
| [`RegexHACFQueryIngress`](components/RegexHACFQueryIngress/) | Regex + HACF query composition | Bounded lexical ingress, HACF lookup, provenance-bound proposal construction, and query-local publication. | No persistent Semantic Fabric mutation, semantic truth, Grid81 mapping, or execution authority. |
| [`QueryLocalProposalIngress`](components/QueryLocalProposalIngress/) | Query-private proposal overlay | Provenance-bound proposal envelopes publish atomically to a private query overlay. | Semantic/admission/execution authority remains zero. |

### 2.3 Post-2.1.16 canonical-writer engineering successor — qualified chain

The repository now contains a **qualified in-repository Grid81 canonical writer
chain**. This corrects the older README claim that no such qualified writer existed.

The three qualified successor writer components are **not yet entries** in the
16-component canonical public registry. Their separate successor registry
retains `public_registry_admission=false` and `runtime_admission=false`.

The publisher path includes a **durable publication-ledger reservation** before
the canonical namespace visibility exchange. That reservation is not itself the
filesystem exchange and does not make publication ambient runtime behavior.

Machine-readable authority:
[`GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0`](manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json)

| Component | Source / docs | Qualification | Admission | Qualified boundary |
|---|---|---|---|---|
| [`Grid81_Canonical_Promotion_Authority`](components/Grid81DeterministicCanonicalPromotionAuthority/README.md) | [`components/Grid81DeterministicCanonicalPromotionAuthority/`](components/Grid81DeterministicCanonicalPromotionAuthority/) | `QUALIFIED_LOCAL_SUCCESSOR` | `public_registry_admission=false`; `runtime_admission=false` | Issues one-use promotion authority from explicit external approval binding. |
| [`Grid81_Canonical_Candidate_Constructor`](components/Grid81DeterministicCanonicalCandidateConstructor/README.md) | [`components/Grid81DeterministicCanonicalCandidateConstructor/`](components/Grid81DeterministicCanonicalCandidateConstructor/) | `QUALIFIED_LOCAL_SUCCESSOR` | `public_registry_admission=false`; `runtime_admission=false` | Builds a complete isolated immediate-successor candidate. |
| [`Grid81_Atomic_Canonical_Publisher`](components/Grid81DeterministicCanonicalPublisher/README.md) | [`components/Grid81DeterministicCanonicalPublisher/`](components/Grid81DeterministicCanonicalPublisher/) | `QUALIFIED_LOCAL_SUCCESSOR` | `public_registry_admission=false`; `runtime_admission=false` | Reserves and atomically publishes an authority-gated candidate with monotonic recovery. |

The explicit flow is:

```text
G53e advisory planner
  -> promotion authority + external approval binding
  -> one-use ATOMIC_GRID81_CANONICAL_PROMOTION
  -> isolated candidate constructor
  -> durable reservation + namespace lock
  -> atomic canonical publisher
  -> production-reader verification
```

Normal consumers remain read-only. The writer chain is not public-registry
admitted, not runtime-admitted, not self-authorizing, and not background ECS or
canonical mutation.

### 2.4 Qualified internal modules shipped by the 2.2 line

The 2.2 adoption policy ships four **qualified internal** modules without
promoting them to stable package-root API and without changing runtime admission:

| Internal qualification | Source | Disposition | API/admission boundary | Qualified mechanism |
|---|---|---|---|---|
| `E0R3_PARTICIPATION_REFERENT` | [`src/elpis_reference/structural_guidance/e0r3_participation.py`](src/elpis_reference/structural_guidance/e0r3_participation.py) | `SHIP_INTERNAL_QUALIFIED` | `stable_package_root_api=false`; `runtime_admission_change=false` | Deterministic whole-column participation referents, reverse binding, and R0 delegated disable/restore. |
| `ECS_TOPOLOGY_PROJECTION` | [`ECS/runtime/elpis_ecs/topology.py`](ECS/runtime/elpis_ecs/topology.py) | `SHIP_INTERNAL_QUALIFIED` | `stable_package_root_api=false`; `runtime_admission_change=false` | Deterministic ECS topology projection. |
| `ECS_TOPOLOGY_ANALYSIS` | [`ECS/runtime/elpis_ecs/topology_analysis.py`](ECS/runtime/elpis_ecs/topology_analysis.py) | `SHIP_INTERNAL_QUALIFIED` | `stable_package_root_api=false`; `runtime_admission_change=false` | Deterministic topology analysis without ECS mutation/payload semantics/persistence. |
| `DURABLE_APPLICATION_LEDGER_V2` | [`components/Grid81DeterministicCapabilityApplicationExecutor/src/elpis_grid81_application_executor/durable_ledger_v2.py`](components/Grid81DeterministicCapabilityApplicationExecutor/src/elpis_grid81_application_executor/durable_ledger_v2.py) | `SHIP_INTERNAL_QUALIFIED` | `stable_package_root_api=false`; `runtime_admission_change=false` | Durable schema-v2 CAS/replay exclusion with artifact binding. |

---

## 3. Structural-control path

---

## 3. Structural-control path

### 3.1 Canonical relational Semantic IR

`P0SemanticRequestV1` is a canonical relational task representation independent of Grid81. It can represent entities, operations, constraints, relations, dependencies, quantities, and declared outputs with canonical identifiers, validation rules, serialization, and digest-bound identity.

It does **not** parse natural language. It does not, by itself, establish a complete semantic mapping into Grid81. C2R7-A established the relational graph contract; C2R7-B binds that graph's identity as a sidecar through the structural path while preserving the distinction between semantic identity and Grid81 structural meaning.

Trusted natural-language -> Semantic IR compilation remains unqualified.

### 3.2 Grid81

Grid81 is an explicit bounded structural control space. The current P0 projection family uses an 81-cell topology organized as nine ranks across nine lanes with typed structural state, lane/rank/locus relations, invariants, writable/frozen boundaries, residual state, semantic sidecar identity, deterministic traces, and digest-bound output.

The earlier C2R6-P0 greedy rank/locus allocator was independently shown incomplete over its bounded audited `ROUTE`/`state_feeds` subset by FuryanLocusOracle R0. That historical defect is **not a current frontier item**: Elpis2.1.8 replaced the incomplete strategy with deterministic joint finite-domain rank/locus allocation and differentially qualified the supported subset against Furyan's 44,005-case canonical core.

The successor allocator also carries a deterministic search-entry budget. `SEARCH_BUDGET_EXHAUSTED` is distinct from UNSAT or decomposition. The bounded qualification is not a theorem of universal Grid81 satisfiability.

### 3.3 Canonical Grid81 reader is read-only; explicit writer chain is qualified

The released **Elpis2.1.16** public runtime boundary remains read-only; the
2.2.x repository adds a qualified explicit writer transaction without making
that writer a normal runtime path. Repository coexistence does not imply runtime
integration. Canonical publication remains an explicitly authorized transaction.

The planner is non-executable and non-authoritative. Promotion authority binds
explicit external operator approval into one-use write authority. The candidate
constructor builds the successor outside live canonical state. The publisher
uses durable reservation, a project-root-derived namespace lock, Linux/POSIX
filesystem primitives, atomic directory exchange, monotonic recovery metadata,
and production-reader verification.

The guarantees are bounded: SQLite reservation and filesystem exchange are not
one atomic transaction; hostile filesystem replacement, mixed incompatible
publisher versions, and stronger operator authentication remain outside the
claim. The writer chain is not public-registry/runtime admitted and is not a
background mutation loop.

### 3.4 Bounded learned structural guidance

The qualified learned structural-guidance path keeps the model behind an explicit request-level gate that defaults OFF. The admissible checkpoint identity is pinned while the host supplies the checkpoint path. The semantic binding envelope remains outside model input. Model authority is zero.

Candidate legality and transition execution remain deterministic. The frozen TRM can affect bounded proposal/search ordering only inside an already admitted space. Failure to admit guidance returns explicit fallback control rather than silently widening the model's authority.

### 3.5 Authority-preserving improvement witness

Elpis2.1.11 added the closed Authority-Preserving Improvement Witness R0 (APW R0). Its bounded deterministic fixture demonstrates proposal quality improving exactly as the literal witness `27 -> 54 -> 81/81`:

```math
27 \;\longrightarrow\; 54 \;\longrightarrow\; 81/81
```

across three proposal cycles while proposer authority, feedback authority, and accumulated authority remain zero.

The positive terminal fixture is built through public Semantic IR, deterministic P0 projection, and P1-owned transition authority. Exactly one P1-legal strict improvement is certified on the `MUTATION_HAZARD` fixture (`cost 1 -> 0`). The same final proposal packet presented to an already-optimal fixture yields explicit abstention.

This is evidence that repeated proposal improvement can coexist with authority separation. It is **not** a claim of autonomous self-improvement, generalized competence, arbitrary learned-model safety, or execution authority.

### 3.6 Validated-source composition

The public structural-guidance runtime under `src/elpis_reference/structural_guidance/` composes already-qualified stages into a terminal static-validation result:

```math
\begin{aligned}
\mathrm{Semantic\ IR}
&\longrightarrow \mathrm{Deterministic\ structural\ projection}\\
&\longrightarrow \mathrm{Bounded\ guidance\ admission}\\
&\longrightarrow \mathrm{Resolved\ topology}\\
&\longrightarrow \mathrm{Zero\!-\!authority\ observation}\\
&\longrightarrow \mathrm{One\!-\!shot\ materialization}\\
&\longrightarrow \mathrm{Deterministic\ planning}\\
&\longrightarrow \mathrm{Decoder\!-\!plan\ normalization}\\
&\longrightarrow \mathrm{Deterministic\ source\ construction}\\
&\longrightarrow \mathrm{Canonical\ Python\ AST\ policy}\\
&\longrightarrow \mathrm{Authority\!-\!zero\ terminal\ result}.
\end{aligned}
```

The composition binds major intermediate identities and emitted-source digest. Terminal results retain:

```text
authority_granted     == 0
validation_authorized == false
execution_authorized  == false
```

No generated source is executed by this path.

---

## 4. Static Python policy and the implementation-synthesis boundary

Elpis contains a canonical static Python AST policy used by the validated-source path. The policy rejects imports, ambient scope mutation, classes, decorators, `with`/`async with`, indirect call surfaces, unapproved attributes, selected introspection families, and other bounded prohibited forms. Canonical restrictions are non-subtractive.

A result of:

```text
validation_code = AST_VALID
```

means only that source parsed and passed the configured static policy. It does **not** establish functional correctness, task fidelity, sandbox safety, or permission to execute.

A separate blind `merge_intervals` experiment made this boundary concrete: the composition produced AST-valid source while all 7/7 functional checks failed because the emitted function returned `None`. A known-correct positive-control body passed the same downstream source/functional-validation path.

Therefore autonomous implementation synthesis remains unqualified even when upstream semantic, structural, materialization, planning, source, and static-validation mechanisms are functioning.

The synchronous-language closure is also not complete. Undecorated async functions, `await`, async iteration, generators, and `yield`/`yield from` do not yet have a fully resolved synchronous-language contract in the canonical policy.

---

## 5. ECS Structural Authority R0

Elpis2.1.12 published and sealed a separate prospectively defined ECS structural contract:

```text
MICROSCOPIC_COLUMN_PARTICIPATION_MASK_R0
```

The contract applies to a frozen cubic ECS reference family. It treats microscopic column slots as operational gauge addresses rather than intrinsic semantic entities.

For each exact nonzero frozen whole column, the writable structural state is binary:

```text
ACTIVE
DISABLED
```

Exact-zero frozen columns are:

```text
FROZEN_ZERO
```

and are non-writable.

The mutation grammar is limited to:

```text
ABSTAIN
DISABLE_COLUMN
RESTORE_COLUMN
```

`DISABLE_COLUMN` materializes six exact binary64 positive-zero values in the existing slot without changing width. `RESTORE_COLUMN` reproduces the exact retained frozen column bytes. Continuous column bytes, primitive law, and width remain frozen.

Column indices are operational addresses. Simultaneously permuting frozen columns and their participation statuses is an equivalence. `S3` is an external scientific observation and is **not** edit identity. No pairwise graph, adjacency, or module structure is introduced by this authority.

### 5.1 Executable authority and fail-closed installed behavior

Elpis2.1.13 made the published R0 contract executable through `elpis_reference.ecs_r0` while retaining explicit authority ownership.

Installed-package behavior remains fail-closed. If no explicit authority root is supplied and no valid source-colocated authority is available, the installed runtime raises:

```text
AUTHORITY_ROOT_REQUIRED
```

Repository-owned tests/tools bind repository authority explicitly. The package must not invent authority or rely on broad source-tree `PYTHONPATH` compensation to make installed-package tests pass.

### 5.2 E0R2 diagnosis and E0R3 referent closure

E0R2 correctly closed at `SEMANTIC_IR_INSUFFICIENT`, identifying the missing
executable writable referent for one frozen whole-column participation primitive.

Elpis2.2 subsequently qualified E0R3. E0R3 provides deterministic participation
referents bound to the verified R0 candidate digest and gauge slot, validates
the complete reverse binding, rejects stale/forged address tables, resolves a
referent to the exact R0 `EditAddress`, and delegates only `DISABLE_COLUMN` /
`RESTORE_COLUMN` to the existing R0 mutation authority.

This closes the bounded missing-referent mechanism. It does **not** claim general
`SemanticOperationV1` representation of ECS participation, and E1/E2 remain
unauthorized.

E1 and E2 have not executed.

---

## 6. Native semantic and retrieval surfaces

---

## 6. Native semantic and retrieval surfaces

The `native/` tree contains public C/C++ substrate work including HACF, the HACF bridge, Semantic Structural Spine, and the Elpis header integration. These are not all required by the base Python/reference install and should not be described as a single stable native deployment ABI.

Current public qualification supports the HACF native path on Linux and macOS through the existing build branches. Windows native HACF is not qualified by the current public evidence.

The native surface and bounded Regex/HACF ingress components are useful because they demonstrate another version of the same architectural discipline: lexical/retrieval evidence may be produced and composed without automatically gaining semantic truth, Grid81 mapping, or execution authority.

For host-capability inspection use the repository setup tooling rather than copying historical runtime build commands blindly:

```bash
python tools/setup.py --profile full --dry-run
```

Compiled native artifacts are build products, not repository authority.

---

## 7. Historical offline runtime integrations

`runtime/R0/` and `runtime/R1/` preserve historical qualified offline integration layers. They are **not equivalent** to the current top-level learned reference runtime under `src/elpis_reference/`.

R0 composes a deterministic structural transaction approximately of the form:

```text
RequestContext
-> P0 projection
-> Grid81 / scope
-> StructuralOracle
-> adjudication
-> Darwinian episode
-> deterministic decoder
-> AST validator
-> receipt
```

R0 deliberately excluded learned-model inference when it was qualified.

R1 prepends bounded read-only HACF retrieval/evidence and delegates the structural transaction to R0.

These directories are retained for reproducibility and architectural history. Their component-local commands may reflect the environments in which they were originally qualified and are not the current universal setup interface.

---

## 8. Public reference-model path

The public FPRM reference path is separate from the frozen structural-guidance TRM research path. It exists to prove that a pinned public model can be fetched, verified, strictly loaded, and executed for a real task.

The Python package carries FPRM authority/configuration data and verifies model identity and ABI before loading. The current public example is CPU Sudoku inference.

The reference path does not convert the model into an authority root and does not establish general reasoning. Model performance on Sudoku must not be used as evidence for unrelated semantic, structural, coding, or agent capability.

---

## 9. Distribution and installed-artifact contract

The distribution rename is intentionally narrow:

```text
PyPI / distribution project: elpisai
console command:              elpis
Python import API:            unchanged
```

Base package dependencies are NumPy and SciPy. Torch and the model-oriented dependencies are under the explicit `trm` extra; the package does **not** have a hard base Torch dependency.

The intended installed import surfaces include:

```text
elpis
elpis_reference
DarwinianMatrix
elpis_p0
elpis_fractal_spine
elpis_grid81_semantics
elpis_grid81_typed
elpis_grid81_groups
elpis_grid81_adjudication
elpis_grid81_capability_authority
elpis_grid81_consumption_compiler
elpis_grid81_application_executor
elpis_grid81_promotion_planner
c_numpy_cortex
elpis_header
elpis_runtime_r0
elpis_runtime_r1
```

Installed-artifact qualification must distinguish source-tree imports from package imports. A clean installed-package check should establish that intended surfaces are absent before installation, resolve from `site-packages` afterward, report distribution metadata under `elpisai`, preserve the `elpis` console entry point, and keep installed ECS authority fail-closed unless explicit authority is supplied.

---

## 10. Qualified claim surface

“Qualified” means bounded implementation/evidence exists for the stated
mechanism. It is not synonymous with public-registry or runtime admission.

| Capability | Qualified claim | Boundary |
|---|---|---|
| Canonical relational Semantic IR | Typed relational requests can be validated, canonicalized, and digest-bound. | No trusted natural-language parser. |
| Semantic identity propagation | Relational semantic identity can propagate as a bound sidecar. | Not complete graph-to-Grid81 semantics. |
| Semantic -> Grid81 projection | Supported structure is deterministically projected under pinned rules. | No universal satisfiability theorem. |
| Joint rank/locus allocator | Repaired allocator matches the frozen Furyan oracle over the qualified 44,005-case core. | Bounded audited model only. |
| Structural TRM guidance | Pinned model may influence bounded proposal/search ordering when explicitly admitted. | Gate defaults OFF; model authority zero. |
| Deterministic adjudication | Candidate legality and transition ownership remain deterministic. | Not arbitrary task correctness. |
| APW R0 | Proposal quality improves in the closed witness while proposer/feedback authority remains zero. | Not autonomous self-improvement. |
| Static Python validation | Source can be checked against the bounded AST policy. | Not correctness, sandboxing, or execution permission. |
| Generated-source boundary | Generated source does not execute. No generated source is executed by this path. | Validation and terminal result materialization do not grant execution authority. |
| Terminal validated-source result | Digest-bound authority-zero terminal results are emitted. | Generated source does not execute. |
| FuryanLocusOracle R0 | Independent bounded finite-placement oracle with checkable certificates. | Not a general Grid81 solver. |
| ECS Structural Authority R0 | Whole-column participation/restore semantics are specified and executable. | No intrinsic column identity or efficacy claim. |
| E0R3 participation referents | Verified referents/reverse binding make the bounded R0 participation primitive addressable. | Not general SemanticOperationV1 integration; E1/E2 remain unauthorized. |
| ECS topology projection | Qualified internal deterministic topology projection ships. | No topology ledger/federation/transport. |
| ECS topology analysis | Qualified internal deterministic topology analysis ships. | No mutation, payload semantics, or persistence. |
| DurableApplicationLedger v2 | Durable schema-v2 CAS/replay exclusion binds artifact digest. | No silent v1 migration or whole-database rollback protection. |
| Canonical writer chain | Explicit promotion authority, isolated construction, durable reservation, atomic publication, recovery and reader verification compose. | Not public-registry/runtime admission; filesystem/operator-auth boundaries remain. |
| Regex/HACF/query-local ingress | Bounded lexical/retrieval/proposal composition preserves provenance. | Not semantic truth or execution authority. |
| FPRM reference path | Pinned model fetch/verify/load and CPU Sudoku inference. | Sudoku evidence only. |
| Release integrity | Physical-tree manifests, immutable archive builds, repository identity, CI/tag gates, path/secret hygiene and registry projections are checked. | Documentation coherence is now a first-class release gate. |

Negative results remain part of the claim surface.

## 11. Known limitations and explicit nonclaims

Elpis currently makes no claim of:

- trusted natural-language -> Semantic IR compilation;
- complete mapping from relational Semantic IR into every Grid81 degree of freedom;
- general SemanticOperationV1 ECS participation merely because E0R3 exists;
- E1 or E2 execution;
- general autonomous implementation synthesis or generated-source execution authority;
- arbitrary autonomous tool execution;
- general Grid81 satisfiability or universal allocator completeness;
- public-registry/runtime admission of writer-chain successors;
- background or self-authorized canonical mutation;
- general cross-process one-time capability consumption outside specifically qualified durable mechanisms;
- cross-process/asymmetric receipt attestation;
- hostile same-process isolation;
- unrestricted learned-model authority;
- runtime admission merely because a component appears in the repository;
- generalized held-out competence unless separately qualified;
- learned/Darwinian/scientific efficacy from ECS structural/topology contracts;
- whole-database rollback protection from DurableApplicationLedger v2;
- solved alignment;
- AGI or ASI.

## 12. Current research frontier

The current frontier is defined by unresolved mechanisms, not by old defects that have already been repaired.

### 12.1 E0R3 closes the writable-referent gap

The E0R2 `SEMANTIC_IR_INSUFFICIENT` diagnosis is no longer the immediate
mechanical blocker it was when the older README was written. E0R3 now provides
the qualified bounded participation referent, complete reverse binding, and
R0-delegated disable/restore operation.

The remaining boundary is integration/science: E0R3 is deliberately not a
general SemanticOperationV1 extension, and E1/E2 remain separately gated.

### 12.2 E1 / E2 remain gated

E1 and E2 have not executed. They should not become authorized merely because documentation, packaging, or unrelated runtime tests are green.

### 12.3 Trusted semantic compilation

Natural-language -> canonical relational Semantic IR remains open. A future learned compiler would need independent validation of task representation and must not become self-authorizing merely by producing a plausible graph.

### 12.4 Functional implementation synthesis

The validated-source path has already demonstrated that AST-valid source can be functionally wrong. Any future implementation-synthesis claim therefore requires independent functional evidence in addition to syntax/policy validity.

### 12.5 Authority durability and external attestation

Current security/capability evidence is deliberately bounded. Cross-process durable consumption, asymmetric/external attestation, and hostile same-process isolation remain separate research problems and should not be inferred from deterministic digests or process-local ledgers.

### 12.6 Static-language closure

The canonical Python policy still has unresolved synchronous-language disposition for async/generator forms. Closing that boundary is a policy-definition task distinct from implementation synthesis or execution sandboxing.

### 12.7 Runtime composition and admission

The repository now contains more qualified surfaces than the original README paper described. Future integration work should make connections explicit and independently qualified rather than equating directory presence, canonical registration, build-system admission, or historical integration with current runtime admission.

### 12.8 Learned / Darwinian refinement

Learned and Darwinian refinement remain bounded research paths. APW R0 shows that proposal improvement can coexist with zero proposer authority, but broader search/evolution layers must not move semantic ownership, transition legality, or execution authority into the proposer.

---

## 13. Repository organization

The repository contains several distinct authority and implementation roots:

| Path | Role |
|---|---|
| `src/elpis_reference/` | Portable public reference runtime, CLI, FPRM path, ECS R0 executable boundary, and structural-guidance composition. |
| `src/elpis_reference/structural_guidance/` | Validated-source structural-guidance composition and stage authority boundaries. |
| `src/elpis/` | Shared contracts/policies including the canonical Python AST and capability machinery. |
| `components/Pipeline/P0ControlProtocol/` | P0 control protocol, canonical relational Semantic IR, projection and validation mechanisms. |
| `components/TRMFractalSpine/` | Structural TRM contracts/refinement surfaces. |
| `components/DarwinianMatrix/` | Projector, clamp, search/refinement and related deterministic mechanisms. |
| `components/Grid81/` | Canonical Grid81 substrate, reader, state, and strict read-only boundary. |
| `components/Grid81StructuralSemantics/` | Grid81 structural semantic contracts. |
| `components/Grid81TypedProjectionCompiler/` | Typed Grid81 projection compiler. |
| `components/Grid81StructuralGroupProjectionCompiler/` | Structural group projection compiler. |
| `components/Grid81DeterministicStructuralAdjudicator/` | Deterministic structural adjudication. |
| `components/Grid81DeterministicCapabilityAuthorityEvaluator/` | Capability authority evaluation. |
| `components/Grid81DeterministicCapabilityConsumptionCompiler/` | Capability consumption compilation. |
| `components/Grid81DeterministicCapabilityApplicationExecutor/` | Capability application boundary. |
| `components/Grid81DeterministicCanonicalPromotionPlanner/` | Advisory canonical promotion planning; non-executable and non-authoritative. |
| [`components/Grid81DeterministicCanonicalPromotionAuthority/`](components/Grid81DeterministicCanonicalPromotionAuthority/) | Qualified explicit promotion-authority bridge; not public-registry/runtime admitted. |
| [`components/Grid81DeterministicCanonicalCandidateConstructor/`](components/Grid81DeterministicCanonicalCandidateConstructor/) | Qualified isolated canonical successor construction. |
| [`components/Grid81DeterministicCanonicalPublisher/`](components/Grid81DeterministicCanonicalPublisher/) | Qualified durable/atomic canonical publisher with bounded recovery guarantees. |
| `components/CNumPyCortex/` | Optional telemetry-first Grid81 transport/recursion component. |
| `components/FuryanLocusOracle/` | Frozen independent finite-placement oracle and certificate machinery. |
| `components/StreamingRegexIngress/` | Bounded native Regex lexical ingress. |
| `components/RegexHACFQueryIngress/` | Bounded Regex + HACF + query-local proposal composition. |
| `components/QueryLocalProposalIngress/` | Atomic query-local `PROPOSED_UNADMITTED` proposal overlay. |
| `native/hacf/` | Native HACF implementation. |
| `native/hacf_bridge/` | Native/Python HACF bridge. |
| `native/semantic-spine/` | Native Semantic Structural Spine. |
| `native/elpis-header/` | Header/runtime-side Grid81 observation integration. |
| `runtime/R0/` | Historical deterministic offline structural transaction integration. |
| `runtime/R1/` | Historical bounded HACF retrieval + R0 integration. |
| `ECS/ECS_AUTHORITY/STRUCTURAL_R0/` | Normative public ECS Structural Authority R0 contract. |
| [`ECS/runtime/elpis_ecs/topology.py`](ECS/runtime/elpis_ecs/topology.py) | Qualified internal ECS topology projection. |
| [`ECS/runtime/elpis_ecs/topology_analysis.py`](ECS/runtime/elpis_ecs/topology_analysis.py) | Qualified internal ECS topology analysis. |
| [`src/elpis_reference/structural_guidance/e0r3_participation.py`](src/elpis_reference/structural_guidance/e0r3_participation.py) | Qualified E0R3 participation referent/reverse-binding adapter. |
| [`manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json`](manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json) | Qualified writer-chain successor registry. |
| `ECS/science/` | Closed Branch35–40 scientific evidence and adjudication lineage; evidence bytes remain authority-bound. |
| `tests/` | Mechanism, determinism, integration, mutation, adversarial, and release tests. |
| `manifests/` | Versioned release manifests and public component registry. |
| `docs/` | Architecture, build, qualification, provenance, and release-policy documentation. |
| `.github/` | Hosted qualification workflows. |
| `CHANGELOG.md` | Development/release chronology. |
| `RELEASE_NOTES/` | Release-specific claim and qualification boundaries. |

For current shipped-component truth, prefer `manifests/PUBLIC_COMPONENT_REGISTRY.json` over the broader internal canonical registry. For a component's detailed claim boundary, inspect its local README/manifest and corresponding tests rather than inferring capability from its name.

---

## 14. Reproducibility, falsification, and release integrity

Elpis treats qualification as an attempt to make claims easy to attack. A bounded claim should identify exact source/configuration/input authority, deterministic identities where claimed, intended negative branches, and independent checks where practical.

Representative falsifiers include:

- a forbidden transition succeeds;
- a negative mutation passes because the test swallowed its own assertion;
- equivalent canonical inputs produce different identities where determinism is claimed;
- a terminal artifact widens its own authority;
- a model proposal bypasses deterministic admission;
- generated source executes without a separately authorized execution boundary;
- an independent oracle disagrees with a production claim inside the oracle's qualified domain;
- an installed package only works because a source-tree path is injected;
- a release workflow validates an unrelated run instead of the exact target SHA/event; or
- release bytes no longer match the immutable manifest that claims to describe them.

Mechanical harness failure is classified separately from scientific/security/integrity non-pass. Frozen scientific or structural authority must not be rewritten merely to make a harness green.

### Published releases are immutable objects

A release identity is bound by `VERSION`, canonical declared release text, the exact Git tree, and a version-specific write-once release manifest. Published predecessor manifests remain immutable even when a public release candidate failed before tagging or GitHub Release registration.

Tracked changes after a sealed published release — including documentation-only changes — belong to a successor development/release identity. The historical manifest is not regenerated to describe new bytes.

From a pristine checkout of a sealed release object:

```bash
python tools/verify_public_release.py
python tools/ci_secret_scan.py .
```

Release qualification is intentionally staged: local qualification, release commit, public-main push and exact-SHA hosted CI, annotated tag and tag CI, GitHub Release/readback and release-event CI, and package-registry publication are separate gates unless an explicit release protocol states otherwise.

---

## 15. Licensing

Elpis source code is distributed under the [MIT License](LICENSE) unless an individual file or bundled third-party component states otherwise.

Third-party model, code, and data obligations are separate from the repository's own MIT-licensed source. Consult [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), `LICENSES/`, component-local notices, and model provenance records before redistributing bundled or downloaded third-party artifacts.

The license grants software-use rights; it does not expand the scientific claims, authority boundaries, qualification scope, or safety guarantees described here.
