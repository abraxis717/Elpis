# File-backed inference trust boundary (successor)

`FMSFileAssets` requires a `PinnedAuthority` plus a `library_id`. Registration
requires an `asset_id` from that authority. The optional legacy
`expected_manifest` is only a consistency assertion: it grants no authority.
`inspect_asset` returns an untrusted observation. Existing manifest/page identity
encodings remain unchanged, preserving inference identities and numerical behavior.

The deployment supplies catalog **bytes** and an independently configured
SHA-256 pin. The pin must come from the operator's trusted configuration channel
(e.g. a reviewed deployment record or verified publisher metadata), never by
hashing the candidate catalog at runtime and trusting that result. Pinning bytes
is the root here; no signing service, key distribution, freshness/rollback policy,
or public release asset catalog is supplied by this change. Published release
manifests and receipts are untouched.

Catalog shape:

```json
{
  "schema": "elpis.inference-authority.v1",
  "source": "operator-approved-model-bundle/version",
  "provenance": "deployment",
  "assets": [{
    "asset_id": "weights",
    "size": 1234,
    "page_size": 4096,
    "sha256": "<ordinary SHA-256 of raw asset bytes>",
    "manifest_digest": "<existing AssetManifest.digest binding geometry and page map>"
  }],
  "libraries": [{
    "library_id": "fms-provider",
    "size": 1234,
    "sha256": "<ordinary SHA-256 of approved shared object bytes>"
  }]
}
```

Example admission (deployment-owned variables deliberately have no auto-discovery):

```python
from elpis.inference.asset_authority import PinnedAuthority
from elpis.inference.file_assets import FMSFileAssets, inspect_asset

authority = PinnedAuthority(catalog_bytes, expected_sha256=deployment_catalog_pin)
with FMSFileAssets(root=trusted_root, library="native/provider.so",
                   authority=authority, library_id="fms-provider") as provider:
    observation = inspect_asset(trusted_root, "model/weights.dat", 4096)
    asset = provider.register("model/weights.dat", observation, asset_id="weights")
    # provider.acquire(...) retains the established page verification semantics.
```

`SyntheticFileAssets` in `synthetic_file_assets.py` explicitly self-authorizes
synthetic test assets and locally built test libraries. It shares descriptor,
sealing, and read verification code; it **does not** establish independent
provenance. Its catalog says `synthetic-test`, and the production constructor
rejects that provenance. Arbitrary Python code can construct a new deployment
catalog and choose its pin; hostile in-process callers are outside this boundary.
This API enforces the distinction at production admission, not the honesty of a
trusted operator's configuration channel.

## Threat model and invariants

An adversary may control candidate bytes, symlinks, directory entries, concurrent
renames and concurrent file writes inside the selected asset root. The configured
root selection, catalog pin, Python process, kernel, mount administration, dynamic
linker, startup environment and native dependency closure are trusted. This is an
integrity boundary, not a sandbox for a malicious but authorized provider or a
protection against resource exhaustion, hostile kernel/filesystem behavior,
ptrace, writable process memory, or a compromised deployment configuration.

* The root is opened once with Linux `openat2`. Every ancestor of the configured
  absolute root and every asset/library component is resolved with
  `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS`. All later opens use the retained root FD.
  No stat-then-open security decision or component-walk fallback is used.
* Files must be regular. Nonblocking opens prevent a FIFO from hanging admission.
  `..` and absolute paths outside the configured lexical root are rejected.
  Hard links and mounted filesystems are not prohibited: content authentication
  still applies. Renaming the root retains authority over the originally opened
  directory; it does not redirect the capability to the replacement pathname.
* Registration streams the entire opened asset, verifies approved length, raw
  SHA-256 and complete page map, and retains that very descriptor. Subsequent
  pages are hashed before native registration/exposure. Metadata stamps are
  supplementary mutation detection, not the provenance root. Mutations and
  renames may conservatively deny service; replacement bytes cannot be exposed.
  Admission now incurs a complete initial read. Demand-read telemetry excludes
  admission reads and OS page cache remains outside native RAM accounting.
* Native loading securely opens the candidate, copies bounded chunks to a private
  `memfd`, applies WRITE/GROW/SHRINK/SEAL seals, hashes that sealed object and
  compares with the catalog's expected length/SHA-256 before `CDLL`. The loader
  receives `/proc/self/fd/<sealed-fd>`, never the candidate pathname. This
  preserves the exact verified bytes even under in-place writes after hashing.
  Loading a descriptor to the original unsealed inode would **not** do so.
* The top-level shared object is covered. ELF dependencies, loader configuration,
  symbol interposition, constructors of authorized code and `$ORIGIN` behavior
  are not independently authenticated. Libraries that require relative `$ORIGIN`
  dependencies may fail under the memfd load location; there is no path fallback.
* The native inference page cache uses a RAM-only PAL and has no filesystem
  callbacks or scratch directory. `scratch=` is accepted for call compatibility
  but is never traversed or created. Legacy native PAL/bridge APIs remain
  available for other consumers; they do not acquire this successor's guarantee.
  The reference checkpoint adapter and isolated plugin loaders are separate
  surfaces and have not been redefined by this change.

## Platform and lifetime

Strong mode is implemented for Linux x86_64, aarch64 and riscv64 LP64, subject to
kernel support for openat2, memfd seals and executable memfd loading through a
trusted `/proc`. Only x86_64 was exercised locally. Unknown ABIs, non-Linux,
missing openat2, or seccomp refusal fail closed. There is no claim of equivalent
fallback race resistance. The rest of the Python inference package remains
importable; unavailable file-provider functionality reports a typed failure.

Validated library descriptors must outlive providers: ctypes does not automatically
unload the library, and reusing a `/proc/self/fd/N` path can make dlopen return an
old cached object. Successful native snapshots therefore remain owned for process
lifetime, with one snapshot per distinct approved size/SHA-256. Each snapshot
occupies a full memory-backed library copy outside the FMS page RAM budget. Repeated contexts
revalidate candidates before reusing that executable snapshot. Asset and root descriptors close with the provider; failed admission
closes its descriptors. Active leases still prevent provider close.

Reference semantics checked against the Linux man-pages:
[openat2](https://www.man7.org/linux/man-pages/man2/openat2.2.html),
[memfd_create](https://www.man7.org/linux/man-pages/man2/memfd_create.2.html),
[file seals](https://www.man7.org/linux/man-pages/man2/F_GET_SEALS.2const.html).
