from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_all_github_workflows_parse_as_yaml():
    workflows = ROOT / ".github" / "workflows"
    paths = sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")])
    assert paths
    for path in paths:
        yaml.compose(path.read_text(encoding="utf-8"))


def test_hash_locked_pip_workflow_commands_are_yaml_block_scalars():
    for rel, expected in (
        (".github/workflows/ci.yml", 4),
        (".github/workflows/platform-matrix.yml", 1),
    ):
        lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
        hits = [
            index
            for index, line in enumerate(lines)
            if "--only-binary=:all:" in line
        ]
        assert len(hits) == expected
        for index in hits:
            command = lines[index].strip()
            assert command.startswith("- run: 'python -m pip install ")
            assert command.endswith("'")


def test_reference_runtime_verifier_disables_bytecode_generation():
    text = (
        ROOT / ".github/workflows/reference-runtime.yml"
    ).read_text(encoding="utf-8")
    assert "PYTHONDONTWRITEBYTECODE: '1'" in text
    assert "PYTHONNOUSERSITE: '1'" in text
    assert (
        "run: python tools/verify_public_release.py --development"
        in text
    )


def test_full_release_uses_package_module_orchestrator_entry():
    text = (ROOT / "tools/full_release.py").read_text(
        encoding="utf-8"
    )
    assert (
        'sys.executable, "-m", "tools.release_orchestrator",'
        in text
    )
    assert (
        'sys.executable, "tools/release_orchestrator.py",'
        not in text
    )


def test_hardened_pushes_delegate_only_credentials_to_external_gh():
    full = (ROOT / "tools/full_release.py").read_text(
        encoding="utf-8"
    )
    boundary = (
        ROOT / "tools/release_orchestrator_io.py"
    ).read_text(encoding="utf-8")
    helper = "credential.helper=!gh auth git-credential"
    assert full.count(helper) >= 2
    assert boundary.count(helper) == 1
    assert 'GIT_CONFIG_GLOBAL' in boundary
    assert 'GIT_CONFIG_SYSTEM' in boundary
    assert "verify_git_transport_policy" in boundary


def test_successor_metadata_is_2232_and_failed_2231_is_preserved():
    assert (ROOT / "VERSION").read_text().strip() == "2.2.32"
    pyproject = (ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'version = "2.2.32"' in pyproject
    assert 'version: "2.2.32"' in (
        ROOT / "CITATION.cff"
    ).read_text(encoding="utf-8")
    assert (
        ROOT / "manifests/Elpis2.2.31.RELEASE_MANIFEST.json"
    ).is_file()
    assert not (
        ROOT / "manifests/Elpis2.2.32.RELEASE_MANIFEST.json"
    ).exists()
