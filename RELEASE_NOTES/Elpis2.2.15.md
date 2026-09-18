# Elpis2.2.15

## Version: v2.2.15

Elpis2.2.15 is the corrective hosted-CI convergence successor to the untagged, unpublished Elpis2.2.14 sealed candidate. It preserves the complete 2.2.14 authority and integrity changes while correcting two release-gate integration defects exposed only by the hosted main-push workflow.

## Corrective changes

- **V3 mutation-suite qualification:** provisional mutation copies select compact schema v3 for successor releases, and content mutations rebind the v3 aggregate publication-tree record without invoking unrelated semantic guards. The negative-branch suite therefore reaches the intended guard instead of failing during setup.
- **Bytecode-free hosted verification:** the fast public-release verifier job disables Python bytecode/user-site side effects and pins pytest to the qualified CI baseline, preventing `tests/__pycache__` from contaminating the physical publication-tree check.
- **Reusable successor declarations:** repository immutability predeclares the 2.2.15 manifest as `FIRST_COMMITTED_BLOB_IMMUTABLE`; runtime-admission temporality binds the corresponding historical release snapshot while preserving the materialized 2.2.14 snapshot.
- **Publication closeout compatibility:** published-release history remains prefix-immutable, while a post-publication append is admitted only when `refresh_published_releases.py --check` proves the exact semantic-tag-derived projection.

## Preserved boundaries

- Elpis2.2.14 remains untagged and unpublished; no tag is created or retroactively moved for it.
- The Elpis2.2.14 manifest remains byte-identical historical evidence.
- The ratified primitive-closure commit and original distribution-baseline commit remain unchanged.
- Historical published and failed release records remain immutable.
- The sixteen-component public registry, non-public ingress/writer coverage, plugin trust boundary, and verification-only Furyan status remain unchanged.
- No learned proposal or verification result acquires execution authority through this corrective successor.
