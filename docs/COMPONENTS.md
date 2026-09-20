# Components

The active R2 assembly contains 16 canonical components and the same 16 components in the public registry. The earlier R1 17/16 assembly is retained only as historical closed authority.

FuryanLocusOracle R0 is separately qualified as an independent verification
component, outside those historical assembly counts. Its
[manifest](../components/FuryanLocusOracle/COMPONENT_MANIFEST.json) binds the
frozen mathematical falsifier, reference, certificate validator, and qualification
gates. It has no allocation, execution, model, or runtime admission authority.
Run `python tools/verify_furyan_locus_oracle.py` for the complete qualification;
see [the qualification contract](../components/FuryanLocusOracle/QUALIFICATION.md).

| Component | Version | Path | Status | Runtime |
|-----------|---------|------|--------|---------|
| HACF R3 | R3 | native/hacf | SEALED | N/A |
| Semantic Structural Spine | V1 | native/semantic-spine | SEALED | N/A |
| Grid81 Structural Semantics | R1.1.1 | components/Grid81StructuralSemantics | QUALIFIED | FALSE |
| Grid81 Typed Projection Compiler | production | components/Grid81TypedProjectionCompiler | QUALIFIED | FALSE |
| Grid81 Structural Group Projection | production | components/Grid81StructuralGroupProjectionCompiler | QUALIFIED | FALSE |
| Grid81 Canonical Substrate | generation_000001 | components/Grid81 | SEALED | FALSE |
| Grid81 Deterministic Adjudicator | production | components/Grid81DeterministicStructuralAdjudicator | QUALIFIED | FALSE |
| Grid81 Capability Authority Evaluator | production | components/Grid81DeterministicCapabilityAuthorityEvaluator | QUALIFIED | FALSE |
| Grid81 Capability Consumption Compiler | production | components/Grid81DeterministicCapabilityConsumptionCompiler | QUALIFIED | FALSE |
| Grid81 Capability Application Executor | production | components/Grid81DeterministicCapabilityApplicationExecutor | QUALIFIED | FALSE |
| Grid81 Canonical Promotion Planner | production | components/Grid81DeterministicCanonicalPromotionPlanner | QUALIFIED | FALSE |
| TRM Fractal Spine | production | components/TRMFractalSpine | QUALIFIED | FALSE |
| Darwinian Matrix | production | components/DarwinianMatrix | QUALIFIED | FALSE |
| P0 Control Protocol | P0.3 | components/Pipeline/P0ControlProtocol | QUALIFIED | FALSE |
| CNumPy Cortex | 0.1.0 | components/CNumPyCortex | QUALIFIED | OPTIONAL |
| Elpis Header | 0.1.0 | native/elpis-header | SEALED | FALSE |
