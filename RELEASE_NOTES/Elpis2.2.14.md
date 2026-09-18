# Elpis2.2.14

## Version: v2.2.14

Elpis2.2.14 is the integrity and authority-boundary successor to Elpis2.2.13. It consolidates qualified identity, immutability, language-policy, native ABI, writer-chain, ingress, plugin-trust, and release-tag controls without broadening learned-component authority or promoting verification-only evidence into runtime authority.

## Qualified changes

- **Canonical identity and digest accounting:** ratify the R2 canonical receipt identity path while preserving the legacy v1 receipt identity, and bind the complete direct SHA-256 sink census so new direct digest consumers cannot appear silently.
- **Authority temporality:** distinguish live runtime/release admission authority from historical release and scoped-evidence snapshots, preventing historical declarations from overriding active authority.
- **Repository immutability:** enforce permanent evidence, append-only release records, and current model/checkpoint identity pins through the release path; accidental protected rewrites fail qualification.
- **Static-language closure:** reject `Await`, `Yield`, `YieldFrom`, and `GeneratorExp` in the Python AST policy while preserving explicitly admitted `async def` structure.
- **FMS bridge cardinality:** replace duplicated native cardinality literals with `FMS_NTIERS` and `FMS_NDOMAINS` while retaining compile-time assertions that preserve the existing three-tier/three-domain Python ctypes ABI.
- **Grid81 writer-chain coverage:** bind every node in the five-node canonical writer flow while preserving the existing three successor components and the unchanged sixteen-component public registry.
- **Inference-plugin trust boundary:** state the installed-driver model explicitly as `TRUSTED_INSTALLED_ENVIRONMENT`; semi-untrusted plugins, pre-load cryptographic code identity, transactional import rollback, arbitrary model-port-path equivalence, and deep runtime-context immutability are not claimed.
- **Ingress-trio coverage:** bind the exact qualified authority objects for `StreamingRegexIngress_R1`, `RegexHACFQueryIngress_R0`, and `QueryLocalProposalIngress_R0` while keeping all three outside public-registry and runtime admission.
- **Annotated release-tag integrity:** strict tagged repository identity now requires the release ref itself to be a Git `tag` object, rejecting a lightweight ref even when it peels to the exact same release commit.

## Preserved boundaries

- The ratified primitive-closure commit and original distribution-baseline commit remain unchanged.
- `PUBLISHED_RELEASES.json` remains publication-fact authority; release-note prose does not substitute for that registry.
- Historical failed and published release records remain immutable evidence.
- The sixteen-component public registry remains distinct from qualified non-public writer and ingress coverage authorities.
- Furyan remains a verification component and is not promoted to semantic, execution, public-registry, or runtime authority.
- The plugin trust model does not claim isolation for semi-untrusted installed Python code.
- No learned proposal, confidence value, verification result, or coverage record acquires terminal execution authority through these changes.

## Release integrity

Elpis2.2.14 retains lifecycle-separated repository identity: candidate ancestry is checked before a release tag exists, while strict tagged identity additionally requires an annotated tag object at the checked-out release commit. Repository immutability, historical-release integrity, and publication-fact authority remain independently enforced.
