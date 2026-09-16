"""Reference POSIX/CPU implementation of ``fms.checkpoint.v1``.

The package owns its compiled FMS inference bridge.  Importing this module does
not discover plugins, probe hardware, load Torch, or open a checkpoint.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, Mapping

from elpis_fractal_spine.contracts import ResidencyAbsentPolicy
from elpis_reference.fms_inference_adapter import (
    FMSCheckpointInferenceAdapter,
)


def _bridge_resource():
    package_root = resources.files(__package__)
    matches = tuple(
        child
        for child in package_root.iterdir()
        if (
            child.name.startswith("_fms_inference_bridge")
            and (
                child.name.endswith(".so")
                or child.name.endswith(".dylib")
            )
        )
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one packaged FMS inference bridge, got {matches!r}"
        )
    return matches[0]


def factory(
    runtime_context: Mapping[str, Any],
) -> FMSCheckpointInferenceAdapter:
    """Construct the qualified FMS checkpoint provider from package resources."""
    try:
        checkpoint_path = Path(runtime_context["checkpoint_path"])
        cold_root = Path(runtime_context["cold_root"])
    except KeyError as exc:
        raise KeyError(
            "fms.checkpoint.v1 requires checkpoint_path and cold_root"
        ) from exc

    bridge_resource = _bridge_resource()
    with resources.as_file(bridge_resource) as bridge_path:
        return FMSCheckpointInferenceAdapter(
            checkpoint_path,
            bridge_library=Path(bridge_path),
            cold_root=cold_root,
            absent_policy=ResidencyAbsentPolicy.FOLD_DOWN,
        )
