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
