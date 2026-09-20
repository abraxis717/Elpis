# ECSContextProjector

Deterministic, read-only projection over committed Elpis ECS history.

Component identity: `ECSContextProjector`.
Qualified Python package/API identity: `elpis_ecs_context`.

Authority boundary:

- read-only projection only;
- no ECS mutation or transition authority;
- no model, network, tool, or execution authority;
- `project_history` is the replay-backed arbitrary-history path;
- `project_verified_events` requires an already-qualified exact ordered stream;
- `HistoryBinding` is identity data, not authentication.

The runtime files under `src/elpis_ecs_context/` are byte-identical to the
qualified standalone projector. The focused test suite is carried forward with
only the old standalone-layout subprocess path resolution adapted to this
component layout.

## Kernel adapter

`elpis_ecs_context.kernel_adapter.project_kernel_history(kernel, request)` is a
read-only integration adapter for a live `elpis_ecs.kernel.Kernel`. It consumes
only public Kernel surfaces, materializes committed history through
`Kernel.events()`, derives the bound genesis descriptor from the public genesis
label and scheduler protocol, and delegates to replay-backed `project_history`.

The adapter deliberately does **not** use `project_verified_events`: the Kernel
does not yet expose a single public committed-history binding/cursor contract
for that fast path. A transition committed after `Kernel.events()` returns is
simply outside the returned projection's source prefix.
