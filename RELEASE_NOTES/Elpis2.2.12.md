# Elpis2.2.12

## Version: v2.2.12

Elpis2.2.12 is the bounded-feedback and portability successor to Elpis2.2.11.

The release integrates the qualified R2 Sudoku feedback successor with explicit runtime ports, FMS/PAL checkpoint-artifact residency, explicit installed-provider activation, and a separately packaged POSIX/CPU reference FMS inference driver. Deterministic authority remains outside the learned model path.

## Qualified changes

- **Bounded R2 feedback:** task-level Sudoku residuals may drive at most one state-bound Projector release cell per traversal before a pinned Samsung FPRM re-proposal. Structural rejection is never reinterpreted as task residual, immutable givens cannot be released, surviving clamps remain authoritative, and learned output remains proposal-only.
- **Portable execution and residency ports:** R2 consumes injected `ModelResidencyPort` and `InferenceExecutionPort` capability surfaces rather than choosing CUDA, CPU, MPS, or another physical backend in semantic core. The CPU lane is the universal baseline; CUDA is not a core requirement.
- **FMS/PAL checkpoint residency:** the exact checkpoint artifact is verified, registered, leased, and accounted through FMS. On the reference POSIX/CPU provider a logical HOT request truthfully folds to actual WARM residency, with RAM/WARM byte accounting and no device emulation.
- **Ownership boundary:** checkpoint-artifact bytes are FMS-owned during the qualified inference path. Decoded model state and live PyTorch tensors remain outside FMS ownership; this release does not claim VRAM or live-tensor residency management.
- **Explicit provider activation:** model registry data names abstract driver and adapter identities. Hosts explicitly register/resolve provider factories; missing or duplicate exact drivers fail closed, and core does not infer a physical backend from the abstract driver id.
- **Installed driver discovery:** the fixed entry-point group `elpis.inference_drivers.v1` supports explicit exact-name discovery without loading unrelated plugin code, probing hardware, installing packages, or performing network access.
- **Reference POSIX FMS driver wheel:** `fms.checkpoint.v1` has a separate POSIX/CPU reference distribution that packages its compiled FMS inference bridge and resolves that bridge internally. Hosts provide checkpoint/cold-root runtime data rather than a repository-local bridge path.
- **No-Torch baseline qualification:** core/discovery behavior is qualified with the optional Torch dependency observably absent. The base package does not require Torch for the CPU/no-Torch lane.
- **Supported Python/dependency boundary:** the release carries `requires-python = ">=3.11,<3.13"`, `numpy>=1.26,<2`, and `scipy>=1.11,<2`. NumPy 2.x and Python 3.13 are not claimed by this release.

## Preserved boundaries

- The complete structural-guidance `_authority` subtree remains frozen.
- Historical R0/R1 runtime authority remains unchanged.
- Existing provider/discovery/FMS policy authority is not broadened by release metadata.
- The reference driver derives its version and exact `elpisai` dependency from root release metadata; the driver source does not contain an independent release-version authority.
- Elpis2.2.11 publication records, release notes, and sealed manifest remain immutable historical evidence.

## Explicitly not claimed

- The reference driver wheel is not claimed to be universal across operating systems.
- No manylinux compatibility/certification claim is made for the host-qualified POSIX wheel at this stage.
- The reference POSIX wheel does not claim CUDA, ROCm, MPS/Metal, Vulkan, or other accelerator support.
- FMS does not claim ownership of decoded/live PyTorch tensors or VRAM residency in this release.
- Elpis core does not perform automatic hardware selection.
- This release-preparation state does not claim that Elpis2.2.12 has already been tagged, published on GitHub, or published to PyPI.

## Publication record

`PUBLISHED_RELEASES.json` is the repository publication registry. This document describes the Elpis2.2.12 release content and does not itself establish a Git tag, GitHub Release, PyPI publication, or publication-registry entry.
