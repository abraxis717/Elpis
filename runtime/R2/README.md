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

`runtime_admission = false` remains the authority state during this wiring phase.

## Packaging boundary

R2 is a standalone internal package. It is deliberately not inserted into the
top-level `elpisai` package during the wiring tranche. Importing `elpis_runtime_r2`
does not import Torch or the learned feedback implementation. The learned path is
resolved lazily only when `execute_feedback_transaction()` is invoked.

Admission promotion is a separate later gate.
