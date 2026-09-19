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

The Linux x86-64 platform runtime is qualified through the Astra isolated host.
The model-port row remains globally disabled and can execute only through exact
registry bytes, exact wheel authority, and caller-supplied model bytes matching
the frozen SHA-256 in `QUALIFIED_RUNTIME.json`.  Native timing/RAM/reasoning
diagnostics are deliberately excluded from the portable tool-proposal payload.
