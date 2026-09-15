import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_direct_frozen_authority_import_fails_closed_under_python_O():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable,
            "-O",
            "-c",
            (
                "from elpis_reference.structural_guidance._authority."
                "c2r6p0.projector import project"
            ),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode != 0
    assert "FROZEN_AUTHORITY_REQUIRES_DEBUG" in proc.stderr
