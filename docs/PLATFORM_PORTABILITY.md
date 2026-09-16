# Platform portability

Elpis public source is developed under a platform-neutral architecture rule.

Platform-neutral code owns semantic and structural behavior. Platform-specific
logic is restricted to bootstrap, native build, and injected execution /
residency providers.

The current public learned reference remains the pinned Samsung MLP-T TRM.
Portability is provided by injection boundaries, not by making model semantics
aware of accelerator families.

- Semantic task-residual and reverse-trace contracts: pure Python.
- FMS/PAL owns memory residency, capability reporting, fold-down/reject policy,
  physical-domain accounting, leases, and device fences.
- TRMFractalSpine owns the Python residency/execution port contracts.
- Reference TRM runtime keeps a temporary direct `device=` compatibility path;
  new integrations inject execution/residency providers.
- CPU is the universal fold-down execution target; accelerators are optional
  provider implementations.
- HACF native code: CMake-selected macOS/Linux build paths.
- Windows: portable Python/reference surface is exercised by CI; native HACF
  remains explicitly unqualified.
- Qualification scripts may be workstation-specific and are not runtime
  architecture.

`tools/setup.py` performs platform discovery and derives the build plan. It
contains no developer-workstation absolute paths.

## Checkpoint-artifact FMS adapter

The first FMS inference adapter owns only the verified checkpoint byte object.
It registers those bytes with FMS, obtains a real FMS lease, and exposes the
lease through the existing inference port. The CPU reference executor consumes
that lease-backed reader.

This does not claim that decoded PyTorch parameters, activations, or
accelerator allocations are FMS-resident. Those allocations remain outside FMS
until a PAL/backend actually owns them. Proxy accounting for memory owned
elsewhere is forbidden.

Under the POSIX PAL, HOT is unavailable. HOT + FOLD_DOWN therefore resolves
through FMS to actual WARM CPU-addressable residency.


## Model-port provider activation

`models.toml` identifies `FPRM.Samsung_TRM` and requests logical `HOT` residency. `model_ports.toml` binds the bounded profile to `fms.checkpoint.v1` / `fprm.sudoku-feedback.v1` with `ON_DEMAND` while remaining globally `enabled = false`.

`InferenceDriverRegistry` is caller-owned. The base repository contains no builtin physical-accelerator map and performs no arbitrary import from TOML. Missing or duplicate registration fails closed. FMS/PAL remains the authority for actual residency, fold-down/reject, byte accounting, and leases.

Automatic installed-wheel discovery is a later plugin-boundary phase.
