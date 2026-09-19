# Needle3 isolated native driver

This directory is a standalone platform-wheel source tree. It is intentionally
not part of the `elpisai` distribution.

The driver is loaded only through the Astra isolated-wheel host.

## Runtime shape

The final Linux x86-64 wheel must contain:

- `elpis_needle3_driver/provider.py`
- `elpis_needle3_driver/native/libelpis_needle3.so`
- the exact LLVM libc++ runtime needed by that shared object
- wheel metadata and the `elpis.inference_drivers.v1` entry point

`needle3.cact` is **not** carried in the wheel. The caller supplies its path and
expected SHA-256 through the canonical Astra runtime context.

The provider performs no networking, process creation, plugin discovery, model
download, filesystem mutation, or fallback into the trusted installed-driver
lane.

The existing Cactus `needle --serve` runtime is intentionally not used because
Astra R0 seccomp denies networking plus fork/exec before the wheel factory is
loaded.

## Authority

This source tree is a driver/build contract only. It does not grant model-port
admission. A model-port row and production wheel authority must be qualified
separately after the real platform wheel exists.
