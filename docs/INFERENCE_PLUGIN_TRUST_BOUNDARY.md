# Inference plugin trust boundary — R0

## Scope

This document defines the trust model for installed inference-driver discovery
and activation in the bounded Elpis R2 provider path.

The fixed entry-point group is `elpis.inference_drivers.v1`.

The current model is:

**Installed inference-driver distributions are trusted host code.**

An operator or host that installs a provider wheel is extending the trusted
Python process. Elpis does not claim that an installed provider wheel is
sandboxed, transactional, provenance-verified before import, or safe to execute
when the wheel itself is semi-untrusted.

This boundary is narrower than arbitrary plugin execution:

- discovery is explicit rather than automatic;
- matching is exact by requested abstract `driver_id`;
- zero or duplicate exact matches fail before plugin loading;
- unrelated entry points are not loaded;
- registry TOML does not supply Python import targets;
- discovery performs no package installation, network operation, or hardware
  preference selection.

Those properties do not make the selected installed plugin untrusted code.

## N10 — pre-load identity is metadata-only

Before `EntryPoint.load()`, discovery records:

- requested driver id;
- distribution name;
- distribution version;
- entry-point group;
- entry-point value.

That is useful provenance metadata, but it is not a cryptographic identity for
the Python code that will execute. The current path does not bind the selected
distribution or importable module bytes to a pre-load content digest, signed
artifact identity, or equivalent code identity.

Therefore Elpis2.2.14 does **not** claim pre-load code identity for installed
inference-driver plugins.

A future semi-untrusted plugin design would need a separately qualified
artifact/provenance control before execution.

## N11 — plugin import is not transactional

`EntryPoint.load()` imports and executes Python module initialization inside the
host process. If that import raises, Elpis can refuse registry mutation, but it
cannot roll back arbitrary side effects already performed by imported code.

Examples of process side effects that are outside rollback authority include
module-global mutation, filesystem writes, thread creation, environment
mutation, native-library loading, or other actions performed by the plugin
during import.

Therefore Elpis2.2.14 does **not** claim transactional plugin import or
side-effect rollback.

Supporting semi-untrusted plugins would require a separately qualified
isolation boundary such as process isolation plus an explicit IPC contract;
that architecture is not admitted by this threat model.

## N12 — model-port registry path is caller supplied

`activate_model_provider()` accepts `model_ports_path` and parses that path at
activation time. The parser validates the registry schema and bounded port
policy, but activation does not independently prove that the supplied path is
the exact qualified repository `model_ports.toml` object by digest or canonical
authority identity.

The qualified repository file remains a release-bound data authority. That does
not turn every caller-supplied path with schema-valid content into equivalent
release authority.

Therefore Elpis2.2.14 does **not** claim arbitrary caller-supplied
`model_ports_path` identity equivalence.

A future stronger authority boundary would bind activation to an exact
qualified registry digest or canonical authority object before using the port.

## N13 — runtime context is only shallowly read-only

`InferenceDriverRegistry.resolve()` currently passes:

`MappingProxyType(dict(runtime_context))`

to the selected driver factory.

This prevents assignment to top-level mapping keys through that view, but it
does not recursively freeze nested lists, dictionaries, sets, custom objects,
or other mutable values.

Therefore Elpis2.2.14 claims only **top-level mapping immutability**, not deep
runtime-context immutability.

A future stronger boundary would use a separately qualified canonical
serialization/deserialization or recursive immutable typed representation.

## Release disposition

N10–N13 are documented trust-boundary findings, not silently reclassified as
technical fixes.

For Elpis2.2.14:

- trusted installed driver code: admitted only through the already-qualified
  explicit discovery/activation path;
- semi-untrusted installed driver code: **not admitted**;
- pre-load cryptographic code identity: not claimed;
- transactional import rollback: not claimed;
- arbitrary caller-supplied model-port registry identity equivalence: not
  claimed;
- deep runtime-context immutability: not claimed;
- process sandboxing/isolation: not claimed.

This threat model does not grant runtime, network, writer, public-registry,
hardware-selection, package-installation, or background-execution authority.
