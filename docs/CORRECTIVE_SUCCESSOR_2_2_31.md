# Corrective successor engineering

This is an unsealed development successor. Elpis2.2.30 remains closed and
immutable. No 2.2.31 manifest, tag, assertion, ratification or publication receipt
is supplied by this work. Qualification results and remaining blockers are recorded
in the local engineering debrief; this document specifies the contracts.

## Physical snapshot versus development

`verify_public_release.py --development` runs package, runtime boundary, hygiene
and repository identity checks on current source. Its verdict explicitly makes
no release-snapshot or origin claim. Branch/PR CI uses this mode. It does not
substitute a historical checkout for the source being tested.

`--candidate` checks a sealed payload, with no publication/origin claim. Default
verification checks the release snapshot and, from 2.2.31, requires an external
SSH allowed-signers authority. Tag CI and PyPI build verification must pass the
separate protected release-integrity check.

After publication the sealed manifest is verified against a safe archive, then
the physical checkout is compared against that archive. Index flags, ignored and
untracked status never remove a physical file from this comparison. Membership,
bytes, symlink target/type and executable bits participate. Only the root `.git`
administrative entry is omitted. Nested `.git` content remains visible. Generated
build directories, bytecode and egg-info are rejected in a presented snapshot;
qualification scratch belongs outside it. Symlink parents and escapes are
rejected. Extraction uses an explicit, whole-archive validated file/directory/link
implementation compatible with Python 3.11.0, without `extractall`.

The only postpublication differences are the exact current assertion append and
the current release's optional, semantically exact ratification. Historical
registries, manifests and ratifications must match the seal. The assertion-only
stage is supported during closeout. A tag at HEAD must be physically exact.
Publication assertions still bind the peeled commit and annotated object to Git.

The threat model is a quiescent checkout inspected by trusted verifier code.
This is not an atomic filesystem snapshot against a concurrent writer, and a
verifier obtained only from an untrusted repository cannot establish its own
trustworthiness. External origin verification must be run with reviewed tooling.

## SSH origin authority and ceremony

The v2 intent records the **observed signed annotated-tag object ID** and SHA256
of externally supplied allowed-signers bytes. Signed bytes are never recreated
by `mktag` or predicted from unsigned annotation text. Legacy intent v1 remains
readable for historical fixtures; 2.2.31 and newer require v2. Resuming with a
different object or signer authority conflicts with the journal.

The trusted operator must provision an allowed-signers file outside the checkout
and outside repository control. The current profile accepts explicit principals
and Ed25519 public keys, one `principal ssh-ed25519 base64-public-key` per line.
It rejects empty data, wildcard principals, unsupported key types and options.
Git verifies the exact object, direct commit target and embedded tag name using
`git verify-tag`, the external file, and the SSH verifier explicitly selected by
the tool. No private key is generated, stored or required by verification.

After complete locked qualification and the explicitly authorized seal, an
operator signs the exact candidate on a trusted signing workstation, verifies it
there with the independent trust root, and transfers the public signed tag object
to the release object database without publishing a ref. Record its object ID as
`ELPIS_SIGNED_TAG_OBJECT` and set `ELPIS_ALLOWED_SIGNERS` to the external trust-root
path. Resume the same full-release state. The release machine verifies this
object before creating the local ref with a zero-old-OID compare-and-swap and
before publishing the exact object. Never regenerate a different signature to
recover a journaled object. Do not perform this ceremony until release approval.

GitHub integration uses a protected `release-verification` environment with
`RELEASE_ALLOWED_SIGNERS`, delivered into runner temporary space. Protect the
environment, workflow changes and tag creation independently of PR content; use
reviewers and prevent self-approval. The file is public-key authority, not a
private signing key. CI configuration alone does not establish those external
protections. Existing OIDC publishing and archive-export build controls remain.

Reference: [Git SSH signing configuration](https://git-scm.com/docs/git-config#Documentation/git-config.txt-gpgsshallowedSignersFile).

## Recovery

New lower-journal intents record a dispatch protocol version. A durable intent
with no dispatch can resume safely. A dispatch records the last boundary before
the external call. An exact observed result is validated and completed without
repeating the operation. Conflicts and disappeared completed/acknowledged state
stop. Legacy intent-only journals remain ambiguous, preserving their original
semantics.

After a dispatched call with absent current state, reconciliation records remote
refs and, for tags, GitHub Release, PyPI and paginated tag Actions witnesses. A
prior witness produces `PREVIOUS_SIDE_EFFECT`; empty current APIs produce
`ABSENT_UNPROVEN`. Neither authorizes replay. HTTP 500 and transport failures are
not proof of non-execution. These APIs cannot distinguish never-executed from
executed-and-deleted. Automatic replay after such failure remains blocked until
an independently durable non-execution witness or service idempotency contract
exists. This intentionally does not pretend to solve the 2.2.30 HTTP-500 case by
retrying it. A future safe-replay extension must bind such evidence in the journal.

Outer resume derives HEAD from the exact candidate/assertion/ratification chain,
state and journal. Each descendant requires its operation intent, exact parent,
exact changed path and agreement with returned/completed IDs. The owning closeout
step retains its payload checks. Arbitrary descendants are rejected. Git raw
output preserves porcelain columns and NULs; the text helper removes only one
terminal newline.

## Qualification authority and outstanding lock work

The driver checks Python 3.11/3.12, an isolated venv, a platform-specific complete
release lock, exact installed distribution versions and hash-verified pip install
report before starting a release transaction. It records Python patch version,
interpreter binary digest, platform profile, lock digest, complete installed graph
and artifact hashes. Resume requires the same authority. The lower signed-intent
entry point independently checks this authority. This is environment provenance,
not protection against a malicious operator forging local evidence.

`qualification/locks/test-tools-py311-py312.lock` contains universal wheels and
all pytest dependencies, including colorama for Windows. Hashes were obtained
from the corresponding PyPI version JSON endpoints. Install with:

```
python -m pip install --require-hashes --only-binary=:all: -r qualification/locks/test-tools-py311-py312.lock
```

Full numerical/TRM/build locks are **not completed**. No placeholder hashes or
false qualification records are present. Required full-release filenames are
`release-<sys.platform>-<platform.machine().lower()>-py311.lock` and `...py312.lock`.
For example Linux x86_64 uses `release-linux-x86_64-py311.lock`. They must include
pip, pytest, numpy, scipy, torch, setuptools, wheel, build, twine and every
transitive dependency. Resolve and review each supported matrix separately:

* Base: Linux x86_64, macOS arm64 (and x86_64 if claimed), Windows AMD64,
  Python 3.11 and 3.12, with numpy 1.26.4 and compatible SciPy wheels.
* TRM/reference/full release: Linux x86_64, both Python lines, CPU Torch from
  its explicit upstream wheel index. GPU qualification needs its own profile;
  it cannot inherit a CPU result. Include Hugging Face, einops, pydantic and
  safetensors transitives and component dependencies.
* Build: preserve the declared setuptools 84.0.0 backend; lock build/twine and
  transitives. Install the project with `--no-deps --no-build-isolation` only
  after the locked graph is installed. Otherwise isolated builds still resolve.
* Native: pin runner/container identity and compiler/system-package authority;
  a Python lock alone does not reproduce apt or hosted runner images.

Use a clean venv, install the complete lock with `--require-hashes --only-binary=:all:
--ignore-installed --report <venv>/qualification-install.json`, and run pip check.
Bootstrap pip must also be pinned and included in this installation report.
Tests-only lock installation does not qualify the full release environment.
Remaining floating CI installs are a release blocker, not claimed fixed by the
test-tools lock.

## Census and checkpoint

The original census passed on both locally available supported interpreters.
`digest_ast_format_v1.json` now freezes field order and optional-None omission,
and `canonical_ast` owns serialization. Unknown node/field forms fail closed.
The full historical/current corpus produces unchanged v1 identities, so neither
immutable census registry is migrated or rewritten. Any future incompatible
format must have an explicit schema migration.

The FPRM checkpoint revision is pinned to
`6e871275e9b8f95036c6003fd6366f3811565ac6`, whose
[upstream commit](https://huggingface.co/fixed-point-reasoners/fprm/commit/6e871275e9b8f95036c6003fd6366f3811565ac6)
records `sudoku/step_78120` with the existing SHA256 and size 54637557.
The download receives that revision and still enforces the original digest;
deserialization, ABI and memory revalidation controls remain unchanged.
