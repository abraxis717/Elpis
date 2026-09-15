from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN_AUTHORITY_ROOT = Path("src/elpis_reference/structural_guidance/_authority")

def is_test_path(rel: Path) -> bool:
    return "tests" in rel.parts or rel.name.startswith("test_") or rel.name.endswith("_test.py")

def is_frozen_authority(rel: Path) -> bool:
    try:
        rel.relative_to(FROZEN_AUTHORITY_ROOT)
        return True
    except ValueError:
        return False

def find_production_asserts():
    findings = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if (
            ".git" in rel.parts
            or "__pycache__" in rel.parts
            or is_test_path(rel)
            or is_frozen_authority(rel)
        ):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                findings.append((str(rel), node.lineno))
    return findings

def main() -> int:
    findings = find_production_asserts()
    if findings:
        for path, line in findings:
            print(f"PRODUCTION_ASSERT:{path}:{line}")
        return 1
    print("PASS_NO_PRODUCTION_ASSERTS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
