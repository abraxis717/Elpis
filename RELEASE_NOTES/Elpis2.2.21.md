# Elpis2.2.21

## Version: v2.2.21

Elpis2.2.21 adds the isolated native inference-driver host and a bounded Needle3 proposal-only provider while preserving deterministic Elpis/ECS execution and state authority.

## Isolated native inference boundary

- Add an explicit isolated-wheel driver host with exact wheel-byte authority, canonical runtime-context binding, bounded framed IPC, lifecycle ownership, and fail-closed activation.
- Keep isolated providers outside the trusted installed-driver registry. There is no automatic fallback between trusted and isolated lanes and no automatic isolated discovery.
- Apply the qualified Linux sandbox before loading the isolated wheel factory, with `no_new_privs`, seccomp, bounded resources, no networking, and no child-process creation.
- Preserve R2 as a consumer of already-resolved execution/residency ports rather than a provider-resolution authority.

## Needle3 bounded admission

- Add the `cactus.needle3.native.v1` isolated driver contract and freeze the qualified Linux x86-64 runtime authority.
- Admit `Cactus.Needle3` only through the globally disabled `tool-proposal.needle3` port with `ON_DEMAND`, `PROPOSAL_ONLY`, network-denied, remote-code-denied semantics.
- Canonicalize Needle3 output to the semantic proposal fields `type`, `success`, `function_calls`, and `confidence`; native timing, RAM, and reasoning diagnostics do not participate in portable proposal identity.
- Keep the legacy pickle-based Needle entry quarantined and non-loadable.

## Distribution and authority boundaries

The `elpisai` distribution does not bundle the Needle3 model artifact or the separately qualified native Needle3 wheel. Those remain exact caller-supplied artifacts bound by their recorded SHA-256 identities. Needle3 proposes tool calls only; ECS retains execution, state, validation, and terminal-action authority.

Historical release manifests, publication registries, primitive closure identity, and the original distribution baseline remain immutable.
