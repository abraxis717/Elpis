# Elpis2.2.22

## Version: v2.2.22

Elpis2.2.22 is the corrective hosted-CI successor to the untagged, unpublished Elpis2.2.21 sealed candidate. It preserves the complete isolated-native-driver and bounded Needle3 authority introduced by 2.2.21 while correcting the stale P0 model-port load-policy regression exposed by the hosted main-push Component attribution workflow.

## Corrective change

- Update the P0 `model_ports.toml` regression to recognize exactly two explicit `ON_DEMAND` admissions: `FPRM.Samsung_TRM` and `Cactus.Needle3`.
- Bind the Needle3 regression to `tool-proposal.needle3`, `cactus.needle3.native.v1`, `needle3-tool-proposal.v1`, `BOUNDED_NEEDLE3_TOOL_PROPOSAL_V1`, and `PROPOSAL_ONLY`.
- Continue requiring both admitted ports to remain globally disabled, network-denied, and remote-code-denied.
- Continue requiring every model port outside those two explicit admissions to use `load_policy = "NEVER"`.

## Failed predecessor preservation

Elpis2.2.21 remains immutable sealed evidence at commit `777618ef554afb0280e91a119eb38c8bea541a82` with manifest SHA-256 `d686403898069afa0729cea59b01208a949e9db23d7b79663dbf437d8636f065`. Public `main` advanced to that exact seal, but hosted Component attribution run `35464070472` failed only the stale P0 load-policy regression. Elpis2.2.21 was not tagged, was not published as a GitHub Release, and was not published to PyPI.

## Preserved runtime boundaries

- The qualified `model_ports.toml` bytes are unchanged.
- The Needle3 model, native wheel, qualified-runtime authority, sandbox behavior, semantic output identity, and proposal-only authority are unchanged.
- The legacy pickle Needle entry remains quarantined and non-loadable.
- ECS retains execution, state, validation, and terminal-action authority.
- Historical manifests, publication registries, primitive closure identity, and the original distribution baseline remain immutable.

This preparation does not create an Elpis2.2.22 release manifest, tag, GitHub Release, PyPI publication, or publication assertion.
