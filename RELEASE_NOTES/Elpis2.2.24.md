# Elpis2.2.24

## Version: v2.2.24

Elpis2.2.24 is the corrective active-assembly and release-lifecycle successor.

## Active component assembly R2

- Make `manifests/ACTIVE_COMPONENT_ASSEMBLY.json` the explicit moving-tree component-assembly selector.
- Use an exact 16-canonical / 16-public identity set with no canonical-only component exception.
- Retain the earlier R1 assembly bytes only as closed historical authority rather than current component state.
- Keep ECSContextProjector separately distributed and read-only without automatically granting canonical, public-registry, mutation, or execution authority.

## Release-guard CI lifecycle correction

- Route hosted release-guard CI through `tools/run_mutation_suite_ci.py`.
- Preserve the underlying release-wide mutation suite and its refusal to provisional-reseal an already published current VERSION.
- Accept the published-version not-applicable state only when return code 2 carries the exact VERSION-bound guard diagnostic and no stderr.
- Treat every other mutation-suite return code or diagnostic mismatch as a CI failure.
- Execute the full mutation suite normally when VERSION names an unpublished successor.

## Preserved authority

The Elpis2.2.23 annotated tag, sealed v3 manifest, GitHub Release, PyPI file observations, and publication assertion remain immutable historical release authority. Grid81 successor R0 and legacy R1 byte bindings remain preserved while current component assembly authority advances to R2.
