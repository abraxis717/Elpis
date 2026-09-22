from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"

EXPECTED = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
    "pypa/gh-action-pypi-publish": "dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
}


def test_all_external_actions_are_commit_pinned():
    found = set()
    for path in sorted(WORKFLOWS.iterdir()):
        if path.suffix not in {".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"uses:\s*([^\s#]+)", text):
            value = match.group(1)
            if value.startswith("./"):
                continue
            name, sep, ref = value.rpartition("@")
            assert sep and re.fullmatch(r"[0-9a-f]{40}", ref), (path.name, value)
            if name in EXPECTED:
                assert ref == EXPECTED[name], (path.name, value)
                found.add(name)
    assert found == set(EXPECTED)


def test_runtime_r0_does_not_mix_pytorch_and_pypi_indexes():
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "--extra-index-url" not in text
    assert "numpy==1.26.4" in text
    assert "torch==2.14.0+cpu" in text


def test_native_numerical_stack_is_directly_pinned():
    text = (WORKFLOWS / "inference-native-r0.yml").read_text(encoding="utf-8")
    assert "pytest==9.0.2" in text
    assert "numpy==1.26.4" in text
    assert "scipy==1.17.1" in text
