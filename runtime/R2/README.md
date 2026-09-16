# Elpis Runtime Integration R2 — bounded Sudoku feedback successor

R2 is the first successor runtime seam after the historical R0/R1 offline
integration layers.

Its only executable profile is:

`SUDOKU_FEEDBACK_V1`

The profile wraps the already-qualified bounded traversal:

task-bound diagnostic
→ task residual
→ reverse trace
→ state-bound DarwinianMatrix Projector RELEASE
→ revised ClampState
→ pinned Samsung learned re-proposal
→ hard-given / surviving-clamp validation
→ deterministic runtime receipt

## Authority boundary

R2 does **not**:

- parse natural language into semantic authority;
- synthesize `TaskDiagnosticV1`;
- synthesize `ReverseTraceIndex`;
- synthesize `ReleaseBindingTableV1`;
- create canonical Grid81 write authority;
- mutate runtime-admission status;
- grant semantic truth;
- run in the background;
- use network authority.

The learned model remains proposal-only.

`runtime_admission = true` applies only to the qualified bounded `SUDOKU_FEEDBACK_V1` profile. It does not grant whole-runtime, public-registry, generalized component, semantic-truth, writer, network, or background-execution authority.

## Memory / execution portability hook

R2 does not own accelerator selection. The feedback call accepts optional
`execution_port` and `residency_port` injections. The residency contract
speaks only logical `HOT` / `WARM` / `COLD` / `ABSENT` tiers and
`FOLD_DOWN` / `REJECT`; physical backend and device identities are opaque
provider metadata.

The current direct `device=` path remains only as a compatibility path
until the dedicated FMS/PAL adapter tranche is qualified. New integrations
should use the injected ports rather than adding device-specific branches
to R2.

## Packaging boundary

R2 is a standalone internal package. It is deliberately not inserted into the
top-level `elpisai` package during the wiring tranche. Importing `elpis_runtime_r2`
does not import Torch or the learned feedback implementation. The learned path is
resolved lazily only when `execute_feedback_transaction()` is invoked.

The bounded profile was admitted only after the pinned real FPRM checkpoint qualification. Hosted CI remains regression-only: it uses deterministic dud/fake solvers and must not require model weights, CUDA, GPU access, checkpoint download, or real inference.

### R0 checkpoint-artifact FMS adapter

The first concrete residency provider binds the pinned checkpoint bytes to the
existing FMS/POSIX PAL. R2 itself remains hardware-agnostic and receives the
provider through residency_port / execution_port.

R0 coverage is intentionally limited to checkpoint-artifact residency. Live
PyTorch tensor/parameter memory is not claimed as FMS-managed.


### Explicit model-port provider activation

`FPRM.Samsung_TRM` has a bounded, globally-disabled `ON_DEMAND` port using driver id `fms.checkpoint.v1`. R2 does not resolve hardware or import providers from TOML. A caller explicitly registers a local factory and passes the resolved provider through the qualified `execution_port` / `residency_port` hooks. No registration means no model load and no inference.
