# Elpis native cognitive substrate — public source candidate

- ELPIS LLM COMPUTES AND COMMUNICATES
- GEODOME ORGANIZES AND TRANSPORTS
- CGC ADAPTS AND LEARNS
- ECS_C REMEMBERS AND BINDS EVIDENCE AUTHORITY
- RUNTIMECORE GOVERNS EXECUTION
- FMS MATERIALIZES RESOURCES

See `docs/ELPIS_MISSION.md` (historical text plus Amendment 4) and `ELPIS_SYSTEM.json` (live successor authority). The sealed CR6 compatibility profile retains its own contracts.

The native C/Rust runtime is a separate bounded, volatile system. No neural model is required to build it. See [offline build and CI](docs/BUILD.md) for a clean source export and a portable Linux build under a 4 GiB/no-swap scope. This is a development build, not a launcher or deployment contract. The production host needs trusted supervisor pipe capabilities; genesis is empty. No production enrollment wire exists.

## Qualification scope

- actual_neural_inference: NOT_TESTED
- collective_learning: NOT_TESTED
- deployment: NOT_AUTHORIZED
- fms_generic_allocator: NOT_IMPLEMENTED
- fms_immutable_assets: NOT_TESTED
- geometry_advantage: NOT_ESTABLISHED
- host_reconnect: NOT_IMPLEMENTED
- independent_mock_execution: PASS_MOCK_ONLY
- model_authentication: TRUSTED_SUPERVISOR_CAPABILITIES_ONLY
- native_core: PASS_CR7_P3A
- neural_augmentation_utility: NOT_TESTED
- production_enrollment: NOT_IMPLEMENTED
- runtime_model_loss: PASS_OBSERVED_PROCESS_LOSS
- warm_ram_residency: PASS_NONMOVING

First-party Apache-2.0 licensing authorized within owner rights. Source export is authorized; main promotion requires successful hosted CI. Installation and deployment remain unauthorized. See `docs/PUBLICATION_CANDIDATE.md`.

## Contributors and licensing

- [@abraxis717](https://github.com/abraxis717) (Alpharius) — Elpis development and HexaFlake computational implementation.
- [@Akitti](https://x.com/Akitti) — contributor to Elpis through the original HexaFlake concept and geometric architecture.

Geodome derives from [HexaFlake](https://github.com/abraxis717/HexaFlake). See [contributors](CONTRIBUTORS.md), [native licensing and provenance](LICENSES/NATIVE_PROVENANCE.md) and [NOTICE](NOTICE).
