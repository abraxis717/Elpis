# Elpis2.2.0

## Version: v2.2.0

Elpis2.2.0 is a qualified successor to Elpis2.1.27 focused on release integrity, portability, repository hygiene, and bounded internal capability integration.

## Release-integrity hardening

The public release boundary is strengthened in several independent layers:

- release-file exactness detects packageable physical files that are untracked or ignored instead of trusting Git membership alone;
- PyPI publication builds from an immutable `git archive` export of the exact release tag rather than from a mutable checkout;
- canonical assembly verification recomputes component inventories, public identifiers, dependency edges, runtime flags, and current manifest byte bindings from shipped authority;
- the structural-guidance runtime boundary recursively scans the full shipped package and detects additional alias, dynamic-import, `getattr`, and execution-policy bypass classes;
- repository identity verification independently checks ratified commit identities, commit existence, ancestry, and release-tag ancestry;
- secret scanning recognizes current credential shapes with bounded false-positive controls.

These controls are release guards. They do not broaden runtime authority or claim that arbitrary Python is safe to execute.

## Portable Elpis binding

Elpis2.2.0 establishes a portability invariant for inter-code binding:

- code may bind to paths internal to the Elpis tree when those paths are derived from the current Elpis root or package location;
- foreign host-specific filesystem locations are not binding authority;
- the public shipping tree contains no host-specific workstation paths and carries no private-path allowlist debt;
- root package discovery no longer depends on an externally prepared `PYTHONPATH`;
- a relocated Git-less copy of Elpis passes the complete non-Git root test surface, while repository-provenance tests remain explicitly Git-bound.

Closed scientific evidence that previously recorded host-local authority locations is represented portably, with its affected checksum authority advanced consistently. Historical published release manifests remain immutable.

## Qualified internal additions

The following qualified additions ship as internal capabilities in 2.2.0:

- E0R3 whole-column participation referents;
- deterministic ECS topology projection;
- deterministic ECS topology analysis;
- DurableApplicationLedger schema v2.

The frozen `ELPIS_2_2_0_ADOPTION_POLICY_R0` explicitly does not promote these modules to stable package-root public API and does not change runtime admission.

In particular:

- E0R3 does not authorize E1 or E2 and does not write canonical Grid81 state;
- ECS topology does not create a topology ledger, federation layer, or cross-process transport;
- topology analysis does not mutate ECS state, inspect payload semantics, or persist analysis state;
- DurableApplicationLedger v2 does not silently migrate v1 ledgers, does not provide whole-database rollback protection, and does not imply publisher adoption.

## Scientific evidence boundary

Branch36–40 successor evidence remains evidence rather than runtime API. This release changes portability and checksum representation where required by repository hygiene; it does not manufacture new scientific results or reinterpret historical published release authority.

## Release lifecycle ordering

Repository identity is now lifecycle-aware rather than circular:

- an untagged Git candidate proves that ratified identity commits exist and are ancestors of the candidate `HEAD`;
- the absence of the future `Elpis2.2.0` tag does not make the pre-tag candidate invalid;
- strict tagged identity requires the VERSION-selected tag to exist and resolve exactly to checked-out `HEAD`;
- main-push CI runs fast lifecycle-contract tests before release publication;
- the immutable-tag PyPI path retains strict repository identity before `git archive` export.

This preserves the required order: qualify locally, push exact candidate SHA, require hosted main CI green, create the annotated tag at that SHA, require tag qualification, then publish the GitHub Release/PyPI artifact.

Hosted ancestry proofs also require complete Git history. The `CI` public-release verifier job and `reference-runtime-smoke` now check out with `fetch-depth: 0`; shallow proof checkouts fail explicitly as `REPOSITORY_HISTORY_INCOMPLETE` rather than being misclassified as missing ratified commits. A permanent workflow-wide contract prevents any verifier-invoking Actions job from silently returning to shallow history.

## Publication boundary

`PUBLISHED_RELEASES.json` remains unchanged in the pre-tag candidate.

The pre-seal release manifest is qualified from a Git-less physical-tree snapshot so every current qualified DEV file is represented even before Git admission. Immutable tag creation, publication-registry admission, GitHub Release publication, and PyPI upload remain separate later gates.
