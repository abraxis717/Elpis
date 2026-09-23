"""Self-contained R3 qualification fixtures.

Keeps the R3 branch mechanically separate from the top-level ``tests/`` tree.
The native FMS file-asset library is required explicitly; never an implicit PASS.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

R3_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = R3_ROOT.parents[2]

# Make both the inference package and the R3 package importable. R1 is a
# read-only dependency of the R3 r1_adapter boundary.
for p in (str(REPO_ROOT / "src"), str(R3_ROOT / "src"), str(REPO_ROOT / "runtime" / "R1" / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def fms_library():
    lib = os.environ.get("ELPIS_FMS_FILE_LIBRARY")
    if lib is None:
        pytest.skip("explicit native file-asset library required; never an implicit PASS")
    return lib


@pytest.fixture
def workspace_root():
    root = os.environ.get("ELPIS_INFERENCE_WORKSPACE")
    if root is None:
        pytest.skip("explicit inference workspace root required; never an implicit PASS")
    return Path(root)


@pytest.fixture
def provider(fms_library, workspace_root, tmp_path):
    from elpis.inference.file_assets import inspect_asset
    from elpis.inference.synthetic_file_assets import SyntheticFileAssets as FMSFileAssets

    f = FMSFileAssets(
        root=workspace_root,
        library=fms_library,
        scratch=tmp_path / "pal",
        warm_bytes=64,
        staging_bytes=128,
    )
    path = tmp_path / "asset.dat"
    path.write_bytes(bytes(range(128)))
    m = inspect_asset(workspace_root, path, 16)
    asset = f.register(path, m, expected_manifest=m.digest)
    yield f, path, m, asset
    f.close()


@pytest.fixture
def target(provider, tmp_path):
    from elpis.inference.fixtures import make_fixture

    f, *_ = provider
    t, resident, meta = make_fixture(f, tmp_path / "target")
    return t, resident, meta
