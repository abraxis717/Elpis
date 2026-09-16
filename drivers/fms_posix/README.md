# Elpis reference FMS POSIX driver

This subproject is the reference POSIX/CPU implementation of the abstract
Elpis inference driver id `fms.checkpoint.v1`.

It is deliberately separate from core Elpis. Core registry data names only the
abstract driver id; an explicit host discovery step resolves an installed
provider wheel through the fixed entry-point group
`elpis.inference_drivers.v1`.

## Version authority

The wheel does not own a release version. `setup.py` reads the repository root
`pyproject.toml` at build time and uses the same `[project].version` for both:

- the driver wheel version; and
- the exact `elpisai==<version>` dependency.

Release preparation therefore has one version authority.

## Native payload

The wheel builds the canonical repository `native/hacf` and
`native/hacf_bridge/fms_inference_bridge` sources in an external build tree and
packages the resulting bridge inside `elpis_fms_posix_driver`.

At runtime the factory resolves that package resource internally. Callers
provide `checkpoint_path` and `cold_root`; they do not provide a bridge path and
do not need `ELPIS_FMS_INFERENCE_BRIDGE`.

This is a host-qualified POSIX/CPU reference wheel. It is not a manylinux
certification, accelerator provider, or claim that live PyTorch tensors are
FMS-owned.
