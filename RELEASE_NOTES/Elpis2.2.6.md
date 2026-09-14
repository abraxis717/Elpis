# Elpis2.2.6

## Version: v2.2.6

Elpis2.2.6 is the hosted-completeness and repository-hygiene corrective
successor to Elpis2.2.5.

Elpis2.2.5 was sealed and fast-forwarded to public `main`, but it was never
tagged or published. Hosted CI failed only in `Repository completeness and
installed artifact`: the full `tests/` collection included three deliberately
source-only downstream Grid81 integration tests whose packages are outside both
normal pytest roots and package discovery.

The three tests exercise:
- application receipt -> promotion source identity;
- promotion authority -> canonical candidate construction;
- candidate construction -> canonical publication.

The repair does not package those downstream source-only packages and does not
restore ambient `PYTHONPATH` leakage. Repository-completeness now keeps the
ordinary installed/root suite isolated and runs exactly those three integration
tests in a separate explicit-root lane. Installed-artifact qualification
remains separate and strict.

This successor also adds a permanent current-release hygiene contract. A future
VERSION change must agree with package/citation metadata, README, release-note
index, CHANGELOG, and the ratified release-identity table. Manifest and
publication-registry entries are validated when they exist. The CI topology
that protects source-only integration boundaries is itself regression-tested.

`PUBLISHED_RELEASES.json` is intentionally not pre-populated. It records actual
publication, not intent. Release closeout is incomplete until the immutable
tag, GitHub latest Release, PyPI latest distribution, and published-release
registry all converge on 2.2.6.

### Integrated agent hardening and compact release authority

This release also integrates two independently isolated engineering tracks from the common qualified 2.2.6 seed.

Hermes contributed repository-hygiene and fresh-child-process hermeticity hardening, including deterministic audits and the TRMFractalSpine fresh-process digest replay repair.

Astra contributed a forward-looking compact release-authority implementation. The new `elpis.release-manifest.v3` path is explicitly opt-in for a future release and is not used to seal Elpis2.2.6. Historical v2 verification remains supported and Elpis2.2.6 remains a v2 release.

The existing mutation harness remains the historical/default-v2 mutation qualification path. Future activation of v3 should extend that harness before a release elects v3; this does not affect the 2.2.6 v2 publication boundary.
