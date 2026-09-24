import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGETS = (
    "tools/digest_sink_census.py",
    "tools/runtime_admission_temporality.py",
    "tools/refresh_published_releases.py",
    "tools/verify_grid81_writer_successor_assembly.py",
)


def _is_literal_git_list(node):
    return (
        isinstance(node, (ast.List, ast.Tuple))
        and bool(node.elts)
        and isinstance(node.elts[0], ast.Constant)
        and node.elts[0].value == "git"
    )


def test_r3_authority_readers_have_no_direct_subprocess_git():
    findings = []

    for rel in TARGETS:
        source = (ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
                and func.attr in {
                    "run",
                    "check_output",
                    "check_call",
                    "call",
                    "Popen",
                }
            ):
                continue

            if node.args and _is_literal_git_list(node.args[0]):
                findings.append(
                    f"{rel}:{node.lineno}"
                )

    assert findings == []


def test_r3_authority_readers_use_shared_release_git_boundary():
    for rel in TARGETS:
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "release_git" in source
        assert "_release_git.run(" in source
