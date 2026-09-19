# Isolated native inference driver host R0

Task identity: `ISOLATED_NATIVE_INFERENCE_DRIVER_HOST_R0`.

This is an **additive, explicit, content-addressed wheel lane**. No model is
admitted by this implementation. No registry row, release identity, installed
driver discovery behavior, FPRM provider, or existing provider contract changes.
There is no Needle3 integration, model asset, entry point, or model hash here.

## Public API and authority

The package is `elpis_fractal_spine.isolated_driver`. Its exports are:

- `WheelAuthority`, a frozen expected artifact identity;
- `bind_model_port()` and frozen `BoundModelPort`;
- `canonicalize_context()` and frozen `CanonicalContext`;
- `SandboxPolicy`, `SupervisorPolicy`, and frozen `StartupReceipt`;
- `IsolatedProvider` and `activate_isolated_provider()`.

The fixed error taxonomy lives in `isolated_driver.errors`: `IsolatedDriverError`,
`AuthorityError`, `WheelError`, `RegistryError`, `ContextError`,
`InfrastructureError`, `ProtocolError`, `WorkerTimeout`, `SandboxError`,
`LifecycleError`, and `ProviderError`. Import/factory/transport/confinement
failures are infrastructure failures, never ordinary inference results or
abstentions. Exceptions during acquire/execute/release become bounded
`ProviderError`s; the provider remains available to resolve its own lease
semantics. Invalid result schemas destroy the worker.

Typical explicit activation (all identities must come from caller qualification):

```python
from pathlib import Path
from elpis_fractal_spine.isolated_driver import (
    WheelAuthority, SupervisorPolicy, bind_model_port,
    canonicalize_context, activate_isolated_provider,
)

port = bind_model_port(
    model_ports_path=Path("qualified-ports.toml"),
    expected_sha256=qualified_registry_sha256,
    model_id=qualified_model_id,
    expected_driver_id=qualified_driver_id,
    expected_adapter_id=qualified_adapter_id,
    expected_admission_status=qualified_admission_status,
    expected_load_policy="ON_DEMAND",
    expected_authority_class="PROPOSAL_ONLY",
)
wheel = WheelAuthority(
    driver_id=qualified_driver_id,
    distribution_name=qualified_distribution_name,
    distribution_version=qualified_distribution_version,
    entry_point_group="elpis.inference_drivers.v1",
    entry_point_value=qualified_module_and_factory,
    wheel_sha256=qualified_wheel_sha256,
)
with activate_isolated_provider(
    bound_port=port, authority=wheel, wheel_path=Path("artifact.whl"),
    runtime_context=canonicalize_context({"model_path": qualified_readonly_path}),
    policy=SupervisorPolicy(scratch_root=host_owned_existing_scratch_directory),
) as provider:
    binding = provider.acquire(residency_request)
    result = provider.execute(execution_request, residency=binding)
    provider.release(binding)
```

The caller controls the scratch *parent*, but neither wheel metadata nor plugin
code chooses the generated private destination. The secure default requires
Linux libseccomp. R0 implements POSIX pipe supervision; unsupported platforms
fail closed by default. An explicit `SandboxPolicy(require_seccomp=False)` is
for trusted development when the capability is absent, not semi-untrusted
activation. Where libseccomp is available it is still applied, and setup errors
never silently downgrade security. No software is downloaded or installed.

Authority dataclasses are in-process caller receipts, not signatures or a
defense against an already-compromised parent. A hash does not establish who
published the artifact, nor that its behavior is trustworthy. Callers must
qualify the expected digest and policy. Supplying a digest of arbitrary bytes
does not make them equivalent to the repository's qualified registry.

## Wheel verification and snapshots

`WheelAuthority` contains driver id, distribution name/version, entry-point
group/value, and lowercase 64-digit wheel SHA-256. Distribution names must use
canonical lowercase, single-hyphen-separated spelling. R0 versions use numeric
release components with optional `a`, `b`, `rc`, `.post`, `.dev`, and lowercase
`+local` components; epochs and alternate PEP 440 spellings are intentionally
not accepted. Entry points are exact `module:attribute` targets, with dotted
modules/attributes allowed and extras forbidden. Identity digest is SHA-256 of
the compact, sorted-key UTF-8 JSON representation of these fields, never repr.

The parent streams the wheel into a host-generated private byte copy, hashing
as it copies. Hash mismatch fails before ZIP parsing, extraction, or spawning.
The filename is not authority. Verification and extraction use the same open
private copy, not a reopened original artifact path.

The verifier rejects unsafe member paths, traversal, absolute/drive paths,
NUL/backslash/non-ASCII aliases, dot/empty components, case aliases, duplicate
paths, file/directory collisions, symlinks, special files, encrypted members,
unsupported compression, and resource-limit violations. Materialization writes
individual validated regular files using exclusive creation. It never uses
`extractall()`, archive executable bits, or installer hooks.

A bounded fixed-header preflight validates central-directory size and actual
entry count before Python's ZIP parser allocates member objects. ZIP64, split
archives, and central-directory layout extensions are outside this R0 profile.
Nonblocking artifact open plus a regular-file check rejects FIFOs/devices.

R0 supports flat purelib/platlib layouts and compiled extension packages.
It rejects `.data` relocation, `.pth`, and precompiled Python bytecode; the
selected top-level module must have an origin within the snapshot (namespace
entry-point roots are rejected). Empty directory entries carry no code and
are not materialized. Dependencies are not resolved or installed.

Exactly one expected `.dist-info` identity is required. METADATA Name/Version
must exactly match the authority, including canonical name spelling. Duplicate
identity headers, invalid metadata/WHEEL versions, malformed wheel tags,
duplicate entry-point declarations, and mismatched group/id/target fail.
Wheel tags undergo syntactic sanity checks; there is no platform-tag installer
or automatic compatibility selection. An incompatible extension fails import
in the child. Unrelated entry points are never loaded.

Every regular member except RECORD must have a canonical, unpadded base64url
SHA-256 and exact size in RECORD. Missing hashes, unsupported digest algorithms,
extra/missing/duplicate rows, malformed digest encoding, and content mismatch
fail. RECORD's own hash/size fields must be empty in this R0 profile. Its bytes
are still bound by the outer wheel hash and snapshot manifest. RECORD is an
internal-consistency check; the outer SHA-256 is the primary artifact identity.

All RECORD bytes are checked before package content is materialized. Extraction
also checks output hashes. A frozen snapshot receipt records ordered
`(relative_path, sha256, size)` tuples and the SHA-256 of their canonical JSON.
Files become mode 0400, directories 0500. Extensions need read access, not an
executable file permission bit. The private work directory stays 0700, with a
separate private cwd. The artifact copy is deleted after materialization.

Before the handshake, and again immediately before target import, the child
rehashes snapshot contents and checks inventory, permissions, symlinks and
resolved paths against the manifest. It imports from the private snapshot,
never from the original wheel. Cleanup restores directory/file owner write
permissions solely to delete the parent-owned snapshot. Normal close, failed
startup, factory failure, corruption, timeout, and active or idle crash remove
the snapshot and scratch. `retain_snapshot_for_debug=True` deliberately retains
them, is development-only, and must not be used for routine activation.

### Wheel/registry TOCTOU limits

Replacing the original wheel path after copying cannot switch the bytes used
for metadata verification/extraction. Concurrent writes while copying either
produce the expected complete digest or fail. Copy/extraction/child rehashing
minimize later changes. Nevertheless **same-UID adversaries outside the sandbox
can chmod, replace, or race files in the private snapshot between verification
and import**, including during extension dependency resolution. POSIX owner
read-only permissions do not defend against the owner. Trusted core/Python and
ambient dependency files also remain mutable to an external same-user actor.
There is no separate UID, immutable mount, sealed executable filesystem, or
cryptographic measurement of every trusted dependency. Use an OS/container
boundary with separate ownership for a stronger hostile-code deployment.

The registry helper opens the file once, reads bounded bytes once, computes
SHA-256, then passes those same bytes (UTF-8 decoded) to TOML. It never hashes
and reopens. Subsequent path replacement cannot change a bound receipt. The
helper requires schema `elpis.model-ports.v1`, top-level network/remote-code
false, exactly one matching model row, row enabled/network/remote-code false,
and exact caller-requested driver, adapter, admission, load policy and authority
class. The receipt contains the raw-byte registry hash and selected model/port/
driver/adapter/policy identities. Activation also requires ON_DEMAND and equal
wheel/port driver ids, and the proxy rejects operations for another model.

## Runtime context and provider contracts

The context must be a JSON object. The accepted Python values are exact builtin
`None`, bool, signed 64-bit int, finite float, valid UTF-8 str, list, tuple,
dict, and `MappingProxyType`. Custom classes/container subclasses, bytes-like
values, Path, sets, non-string keys, cycles and non-finite floats are rejected.
Dict/mappingproxy is the deliberate narrow accepted mapping subset. Tuples
normalize to arrays. JSON uses UTF-8, sorted keys, compact separators and
`allow_nan=False`. The frozen context stores immutable canonical bytes and
exposes their SHA-256. Every decode yields a new graph. No nested identity is
shared with either the caller or another worker. The child's copy may mutate.

Only the existing `ModelResidencyRequest`, `ModelResidencyBinding`,
`InferenceExecutionRequest`, and `InferenceExecutionResult` cross the provider
interface. Their exact fields and primitive types are checked; their existing
validators still execute. Enums use explicit strings; outer payload tuples use
JSON arrays and are reconstructed as tuples. Unknown fields, wrong types,
invalid dataclass values, and non-JSON nested payloads fail closed. Parent
results are newly constructed trusted Elpis dataclasses. There is no pickle.

## Worker, protocol and lifecycle

The parent uses `sys.executable -I -B`, `shell=False`, three pipes,
`close_fds=True`, a scrubbed environment, private cwd, and a new POSIX session.
The environment sets `PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1`, a fixed
system PATH, deterministic locale and one-thread BLAS defaults; no caller
PYTHONPATH, credentials, preload variables or arbitrary environment survive.
Python's isolated mode ignores Python environment overrides; `-B` separately
enforces no bytecode writes. A trusted core source path is explicitly supplied
by the bootstrap. The ambient Python/site environment is trusted, including
system site initialization; no wheel code is on sys.path during that bootstrap.

The worker applies confinement, rechecks the snapshot, and replies to `start`
with the exact authority fields/digest, snapshot path/digest, child PID, and
effective sandbox receipt. The protocol version binds the outer frame. The
parent compares all identity fields and resource/security requirements. Only
then does it request `factory` with canonical context and context digest. The
worker rechecks snapshot bytes, rejects an already-imported top-level target,
resolves the top-level target within the snapshot before import, imports the
exact selected module/attribute, and checks top-level and target origins again.
Trusted Elpis/Python dependencies may remain ambient; the selected package
must resolve inside the snapshot. Origin checks are not protection against
malicious code changing its own interpreter after import.

One worker owns one factory-created instance. Factory gets only the decoded
context. Acquire/release/execute must be callable; optional close is called
at shutdown. Python module globals and C extension globals are process-local.
The parent never imports any wheel module, uses no legacy driver registry,
and does not implement tools, shell execution, arbitrary method lookup or
remote-object capabilities on behalf of the child.

Each frame is a 4-byte unsigned big-endian byte length followed by exactly that
many canonical UTF-8 JSON bytes. Version 1 messages have exactly:

```json
{"id":1,"op":"start","payload":{},"v":1}
```

Operations are only `start`, `factory`, `acquire`, `execute`, `release`, `close`.
Ids begin at 1 and increase by one. Replies must repeat the request id and
operation, with exactly `{"ok":true,"value":...}` or
`{"ok":false,"error":{"category":"provider","message":"..."}}` as payload.
Error categories are fixed `provider`, `infrastructure`, `sandbox`; messages
are at most 2048 characters. No child-provided exception class is imported.
Responses for release/close/factory have null values. The startup response
contains the handshake. Contract operations carry only their specific request,
binding and optional residency fields.

Duplicate keys, noncanonical JSON, invalid UTF-8/JSON, non-object messages,
unknown versions/operations, extra fields, unexpected response ids, unsolicited
or duplicate output, invalid payload schemas, zero/oversized lengths, and
truncated frames fail. Trailing output after close also fails. There is no
stream resynchronization. The parent reads/validates the length before payload
allocation. All parent pipe reads and writes use nonblocking descriptors and
selectors against monotonic deadlines, including a child that stops reading.
One RPC is in flight under a lock. Normal Python and native stdout is redirected
to stderr in the worker; the saved protocol FD carries frames. A malicious
plugin can still write that FD, which is tested as corruption, not trusted data.

The explicit states are NEW, STARTING, READY, CLOSING, CLOSED and FAILED.
Acquire/execute/release require READY; lease semantics remain provider-owned.
Invalid caller-side requests do not destroy a healthy provider. Provider
exceptions preserve READY. Infrastructure failures transition to FAILED and
clean up. Close is idempotent, including from NEW/FAILED. A context manager is
available; explicit close is required and no destructor is correctness authority.

The parent owns the actual Popen handle, not a remembered PID after exit.
While the process is live, cleanup signals its owned process group, waits a
bounded terminate grace, then kills and reaps if needed. Strict seccomp prevents
fork/process clones and process-group escape while allowing thread clones.
An idle worker death is also observed by the stderr helper, which attempts
cleanup without waiting for an RPC. Cleanup closes all three pipes, stops/joins
the bounded stderr helper and removes the snapshot. No persistent daemon,
socket, port, worker pool, or background service is created. A truly
uninterruptible kernel task could outlive SIGKILL grace; this reports an
infrastructure error instead of claiming successful reaping.

## Explicit limits

| Boundary | Default / hard ceiling |
|---|---|
| Wheel compressed bytes | 512 MiB fixed |
| ZIP regular/directory members | 4096 fixed |
| ZIP central-directory bytes | 4 MiB fixed, checked before ZipInfo allocation |
| Individual expanded member | 128 MiB fixed |
| Aggregate expanded members | 512 MiB fixed |
| Expanded/compressed ratio | 200:1 per member fixed |
| Each metadata/RECORD file | 2 MiB fixed |
| Registry bytes | 2 MiB fixed |
| JSON container depth | 32 fixed |
| JSON values plus keys | 100,000 fixed |
| Context UTF-8 bytes | 1 MiB fixed |
| Frame UTF-8 bytes | 1 MiB default, 4 MiB hard ceiling, 256-byte minimum |
| Startup (child launch through factory) | 20 s / 120 s |
| RPC, including pipe write/read | 30 s / 300 s |
| Shutdown | 3 s / 30 s |
| Terminate grace | 1 s / 10 s |
| Kill/reap grace | 2 s / 10 s |
| Stderr tail bytes | 16 KiB / 64 KiB, 256-byte minimum |
| Address space | 2 GiB / 64 GiB, 64 MiB minimum |
| File descriptors | 64 / 256, minimum 16 |
| CPU time (entire worker lifetime) | 300 s / 3600 s, minimum 1 s |
| Core dumps | 0 |

These limits allow native wheel code and several-hundred-kilobyte inference
results without unbounded parent allocations. Encoded bytes, not only element
count, are checked. Linux address-space limits are virtual-memory limits, not
an RSS budget, and may require qualified adjustment for a particular native
engine. Existing stricter OS hard limits are preserved. Wheel I/O/verification
precedes the child-startup timer and is size-bounded, not a hard real-time disk
deadline. Idle child reads have a one-hour deadline; caller-owned provider
lifetimes should be explicitly closed.

## Linux confinement and residual authority

Baseline controls disable core dumps, bound descriptors/address-space/CPU,
set and verify `prctl(PR_SET_NO_NEW_PRIVS, 1)`, scrub environment and own cwd/FDs.
Libseccomp is loaded directly with ctypes from `libseccomp.so.2`; it is never
installed automatically. Required capability failure precedes plugin import.
The syscall argument policy supports Linux x86_64 and aarch64; other
architectures fail closed. The current qualification machine is x86_64.

The filter defaults to ALLOW, kills the process for network-family calls, returns
EPERM for the other denied classes, and is applied with
thread synchronization (TSYNC). Unsupported ABI architectures retain libseccomp's
kill default. Denied syscall classes are:

- Socket/socketpair/socketcall, connect, bind, listen, accept/accept4, and
  send/receive message/datagram families use KILL_PROCESS; no inherited network
  FDs exist. Network attempts are infrastructure failures, not provider results.
- execve/execveat, fork/vfork, setsid/setpgid. `clone` requires CLONE_THREAD.
  `clone3` returns ENOSYS to allow libc's filtered-clone thread fallback.
- ptrace, cross-process VM access, pidfd access/signaling, kill/tkill and queued
  process signals. tgkill can target only the worker's own thread group.
- Mount/unmount and new mount APIs, setns/unshare/chroot, BPF, perf events,
  keyring calls, reboot/kexec, module loading/unloading, swap, userfaultfd,
  accounting, filesystem quota control, and ioctl.
- open/openat with any write, read-write, create, truncate, append, or O_TMPFILE
  flag. openat2 and creat are denied altogether, because their argument-pointer
  forms should not bypass flag checks.
- truncate/ftruncate variants, unlink, rename, mkdir/rmdir, hard/symbolic links,
  chmod/chown variants, mknod, timestamps, xattrs and fallocate.
- io_uring and file-handle opens, which could bypass ordinary open checks;
  setrlimit and prlimit64 setter calls after bootstrap.

`sandbox.DENIED_SYSCALLS` is the exact unconditional deny list; `_filter()` adds
the documented argument-filtered rules. Rules for syscalls absent on the native
architecture are omitted; libseccomp setup/load errors are fatal. None of the
network, filesystem or exec tests uses Python monkeypatching for enforcement.
Network tests require SIGSYS death, so an outer sandbox that already returns
EPERM cannot falsely qualify a missing worker socket rule.

Read-only open, read, private/read-only mmap, dynamic loading, computation,
memory allocation within RLIMIT_AS, synchronization, thread creation and IPC
pipe writes deliberately remain possible. Model archives may be mmap'ed read
only. The policy does not grant accelerator device I/O; ioctl is denied and
future GPU policies require separate qualification.

**This is process isolation plus an R0 syscall deny policy, not a complete
hostile-native-code sandbox.** There is no read-path allowlist, separate UID,
namespace, cgroup, seccomp notifier, CPU scheduling quota, or filesystem
virtualization. A driver can read files available to its UID (including model
paths), return those bytes over authorized inference IPC, consume bounded
address space/CPU but other kernel resources, and crash or corrupt its own
interpreter. Model artifacts referenced in the context are not automatically
hash-bound by this subsystem. Kernel bugs, side channels, new/unlisted syscalls,
ambient trusted dependency compromise, same-user snapshot races, and Python
or native serialization bugs remain residual risks. The child can forge valid
inference results: protocol validation is not semantic correctness proof.

Explicit no-seccomp development operation loses syscall-side-effect guarantees;
process isolation alone does not stop file writes, external process creation,
networking, or descendants that outlive the worker. Only the required-seccomp
lane is qualified for the R0 semi-untrusted use described here.

## Relationship to N10–N13

- **N10:** materially strengthened here by outer wheel SHA-256 binding and
  metadata/RECORD verification before any wheel code executes. This is artifact
  identity, not a publisher signature or proof of harmless behavior.
- **N11:** import/factory Python and native process-global state is isolated from
  the parent in a fresh child. Active syscall restrictions constrain additional
  effects. There is no universal transactional rollback of arbitrary external
  kernel effects and no change to the trusted installed lane.
- **N12:** the helper hashes and parses one registry byte snapshot, removing
  simple hash-then-reopen TOCTOU. Qualified digest selection remains caller
  authority.
- **N13:** canonical encoding/decoding removes shared nested Python identity.
  The child's mutable decoded copy is not a recursively frozen object graph.

Process isolation is claimed for this new lane. The original installed lane
still discovers metadata and calls EntryPoint.load in the host; its documented
trust model and N10–N13 findings remain unchanged.

## Behavioral qualification

Six new test modules generate synthetic wheel artifacts entirely in pytest
temporary directories. They cover outer hashes, metadata, RECORD, malicious
ZIP paths/types/limits, snapshot tampering and original-path replacement;
framing/schema/deadline and crossed/duplicate/unsolicited response failures;
state transitions, import/factory exceptions, stderr floods, hangs, SIGKILL,
idle crash detection and snapshot/FD/thread cleanup; registry same-byte binding,
policy mismatches and context graph isolation; and kernel-enforced network,
file, exec/process denials with read-only mmap/thread success.

The native fixture compiles a small extension in pytest temp storage using the
existing C compiler. That extension is never imported in the parent: it is
packaged into a RECORD-verified wheel and uses exactly the same materialization,
sandbox, child import and IPC path. Two processes start native counters at one,
retain their own successive values, and survive the other's close. Real C
pthread computation also runs under the filter. Missing compiler/libseccomp
are explicit environmental skips, not successful qualification of those claims.

Existing plugin/provider/FMS tests are run unchanged. Full-root test outcomes
must be reported separately from the focused subsystem results; no existing
tests are weakened, deselected, or modified to hide environment limitations.

## Repository-bound qualification record

The starting identities were verified and remain unchanged:

- HEAD and peeled `Elpis2.2.19`: `5c88cebda17afc719ddb037265b36dc0b73a3e30`.
- Annotated tag object: `980b43f379eb3e9da46b6954436ef6ab8b8fca06`.
- Branch: `astra/isolated-native-driver-host-r0`.
- Initial status contained only untracked `.astra_tmp/`. The user confirmed it
  was supplied by them and expressly authorized continuing from that state.

No existing tracked file was changed. The implementation comprises the twelve
isolated_driver modules (`__init__`, `_contracts`, `_worker`, `activation`,
`authority`, `context`, `errors`, `protocol`, `registry`, `sandbox`, `supervisor`,
`wheel`), this document, and the six new test files below. No commit, push, tag,
release, model admission, or registry modification was performed.

Tests used the available system Python 3.14.7, with user-site imports/bytecode
disabled, no network/package installation, and temporary material confined to
`.astra_tmp`. This interpreter is **outside** the project's declared Python
3.11–3.12 range. Libseccomp was present on Linux x86_64; the native C compiler
fixture ran, without a skip.

Each focused module used this command form, with its listed suffix substituted
for `MODULE` and a distinct temporary directory:

```sh
PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
TMPDIR="$PWD/.astra_tmp/build/tmp" \
python -B -m pytest -o addopts='' -o tmp_path_retention_policy=failed \
  -q -p no:cacheprovider --basetemp=.astra_tmp/tests/final-MODULE \
  tests/test_isolated_driver_MODULE.py
```

| Module suffix | Passed | Failed | Skipped |
|---|---:|---:|---:|
| authority | 39 | 0 | 0 |
| protocol | 33 | 0 | 0 |
| supervisor | 30 | 0 | 0 |
| activation | 31 | 0 | 0 |
| linux_sandbox | 20 | 0 | 0 |
| native_fixture | 1 | 0 | 0 |
| Total | 154 | 0 | 0 |

The authority/activation adversarial tests were also rerun together after
strengthening the traversal fixtures to carry valid RECORD hashes and replacing
the registry pathname immediately after its first read: **70 passed**. The
registry test asserts exactly one read-open, making hash-then-reopen mutation
observable. An observed idle-crash/helper-thread race was corrected and covered
by a deterministic delayed-observer-exit test; reaping and signaling also share
the lifecycle lock.

Unchanged legacy regression command (same Python/environment controls):

```sh
python -B -m pytest -o addopts='' -q -p no:cacheprovider \
  tests/test_model_provider_activation.py \
  tests/test_inference_driver_plugin_discovery.py \
  tests/test_reference_fms_driver_wheel.py
```

Result: **24 passed, 0 failed, 0 skipped**.

The complete root run used:

```sh
PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
TMPDIR="$PWD/.astra_tmp/build/tmp" \
XDG_CACHE_HOME="$PWD/.astra_tmp/build/cache" \
MPLCONFIGDIR="$PWD/.astra_tmp/build/matplotlib" \
python -B -m pytest -o addopts='' -o tmp_path_retention_policy=failed \
  -q -p no:cacheprovider --basetemp=.astra_tmp/tests/full
```

Result: **1592 passed, 6 failed, 24 skipped** in 201.49 seconds. Nothing was
deselected. Two preliminary attempts were stopped when existing repository-copy
fixtures recursively included workspace-local temporary storage, and when the
secret scanner's ignored `build` path affected its positive fixtures. Separating
ordinary tempfile storage from pytest's fixture root allowed the complete run.

Four complete-run failures were temporary-material census failures, not source
regressions: current release manifest truthfulness, no-production-asserts
(the temporary immutable-base copy's vendored code), canonical assembly, and
repository hygiene. After removing the test material, these exact four checks
were rerun unchanged together: **4 passed, 0 failed, 0 skipped**.

The remaining two failures are the existing digest-sink census tests. They were
reproduced on a `git archive HEAD` copy without this subsystem: **2 failed,
1 passed**, including a passing current-release-manifest check. Python 3.14's
default `ast.dump` omits empty fields and therefore changes the existing census
fingerprints. For unchanged `elpis.canonical_identity.content_digest`, the
registered fingerprint is
`d26712c2a07195b2de03a7bc74fa5adac44a839febfe20ee1d81d9e0376e2032`;
Python 3.14's default produces
`2da1a50fd365a4a842f99ffa712643b6d543ab156723a08a649152f23ef4b1c4`.
Using `ast.dump(show_empty=True)` reproduces the registered fingerprint exactly.
No census, manifest, supported-Python requirement, or existing test was changed
to conceal this environment mismatch.

This dirty additive worktree is not a newly sealed release. Existing publication
inventories and the direct-digest census are deliberately unchanged; a later
release must separately qualify/classify the new hash call sites. Passing the
legacy provider tests does not assert publication authority for new files.

All worker snapshots, wheels, compiled fixtures, temporary source/build output,
and test caches created by this implementation were removed. A final cleanup
blocker remains: `.astra_tmp/codex-bwrap-synthetic-mount-targets-1000` is a
Codex-managed **read-only bind mount**, as verified in `/proc/self/mountinfo`.
Ordinary chmod/rmtree return `EROFS`. Its platform-maintained lock/mount-target
files were present before implementation and are not retained plugin material.
The current sandbox cannot remove that mount or its parent `.astra_tmp`.
Therefore the task's mandatory complete-scratch-removal condition is **not
satisfied**, despite successful subsystem, native, legacy and post-cleanup
hygiene qualification. The final disposition must remain NONPASS until this
external cleanup condition is resolved.
