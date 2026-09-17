"""Small local conformance layer around immutable R0 scientific authority."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
API = runpy.run_path(str(ROOT / "tools/verify_furyan_locus_oracle.py"))
COMPONENT = API["COMPONENT_REL"]


def test_furyan_manifest_frozen_identity_and_independence():
    result = API["verify"](ROOT)
    assert result["frozen_files"] == 11
    assert result["status"] == "IDENTITY_AND_INDEPENDENCE_PASS"
    assert result["imports"]["certificate_validator.py"] == ["contract"]
    assert result["imports"]["tests/reference.py"] == ["functools", "itertools"]


def test_furyan_existing_guards_and_mutation_diagnostics():
    science = runpy.run_path(str(ROOT / API["ROOT_GATE"]))
    science["test_focused_certificates_and_mutations"]()


def test_furyan_tail_and_larger_reference_conformance():
    science = runpy.run_path(str(ROOT / API["ROOT_GATE"]))
    solver = science["load_solver"]()
    corpus = science["corpus"]
    groups = [list(corpus.single_tails()), list(corpus.small_tail_minimality()), list(corpus.stress())]
    assert len(groups[0]) == 55
    assert len(groups[2]) == 75
    for group in groups:
        for raw in group:
            result = solver.solve(raw)
            assert result["status"] == ("SAT" if science["reference"].brute(raw) else "UNSAT"), raw
            if result["status"] == "SAT":
                science["certificate_validator"].validate_result(raw, result)


def test_furyan_runs_without_production_or_site_packages():
    script = '''
import importlib.abc, pathlib, sys
component = pathlib.Path(sys.argv[1])
sys.path[:0] = [str(component), str(component / 'tests')]
class NoProduction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0].startswith(('elpis', 'DarwinianMatrix')):
            raise AssertionError('oracle tried to load production: ' + fullname)
sys.meta_path.insert(0, NoProduction())
import FuryanLocusOracle as solver
import certificate_validator, contract, reference, corpus, baseline
for module in (solver, certificate_validator, contract, reference, corpus, baseline):
    assert pathlib.Path(module.__file__).is_relative_to(component)
raw = corpus.instance('ABC', [('route', 'A', 'C'), ('route', 'B', 'C')])
result = solver.solve(raw)
assert result['status'] == 'SAT' and reference.brute(raw)
assert certificate_validator.validate_result(raw, result)
assert baseline.earliest(raw)['status'] == 'FAIL'
raw = corpus.instance('AB', [('precedes', 'A', 'B'), ('precedes', 'B', 'A')])
assert solver.solve(raw)['status'] == 'UNSAT' and not reference.brute(raw)
assert not any(name.startswith('elpis') for name in sys.modules)
'''
    subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, str(ROOT / COMPONENT)],
                   cwd=ROOT / COMPONENT, check=True)


@pytest.mark.parametrize(("name", "addition"), [
    ("FuryanLocusOracle.py", "import elpis_reference as allocator"),
    ("certificate_validator.py", "from FuryanLocusOracle import solve as check"),
    ("contract.py", "from elpis_reference.structural_guidance import _authority"),
    ("tests/reference.py", "import contract"),
    ("tests/baseline.py", "import FuryanLocusOracle"),
    ("tests/corpus.py", "import importlib"),
    ("FuryanLocusOracle.py", "from .contract import normalize"),
    ("FuryanLocusOracle.py", "from contract import *"),
    ("FuryanLocusOracle.py", "loader = __import__; loader('elpis_reference')"),
    ("FuryanLocusOracle.py", "loader = eval; loader('1')"),
    ("FuryanLocusOracle.py", "sys.modules['allocator']"),
    ("FuryanLocusOracle.py", "alias = sys"),
    ("FuryanLocusOracle.py", "getattr(sys, 'modules')"),
    ("FuryanLocusOracle.py", "object.__subclasses__()"),
])
def test_furyan_source_boundary_rejects_forbidden_dependencies(name, addition):
    source = (ROOT / COMPONENT / name).read_text(encoding="utf-8")
    with pytest.raises(API["QualificationError"], match="IMPORT_BOUNDARY|DYNAMIC_ACCESS"):
        API["audit_source"](name, source + "\n" + addition + "\n")


@pytest.fixture
def qualification_copy(tmp_path):
    manifest = json.loads((ROOT / API["MANIFEST_REL"]).read_text())
    names = [str(API["MANIFEST_REL"])]
    names += [str(COMPONENT / item["path"]) for item in manifest["source_inventory"]]
    names += list(manifest["evidence_references"])
    names += ["manifests/PUBLIC_COMPONENT_REGISTRY.json", "COMPONENT_REGISTRY.json"]
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def write_manifest(root, manifest):
    manifest["manifest_self_hash"] = API["sha"](API["canonical"]({
        k: v for k, v in manifest.items() if k != "manifest_self_hash"
    }))
    (root / API["MANIFEST_REL"]).write_text(json.dumps(manifest))


@pytest.mark.parametrize("field", API["DENIED_AUTHORITIES"])
def test_furyan_authority_escalation_fails_even_with_new_self_hash(qualification_copy, field):
    root = qualification_copy
    manifest = json.loads((root / API["MANIFEST_REL"]).read_text())
    manifest[field] = True
    write_manifest(root, manifest)
    with pytest.raises(API["QualificationError"], match=f"AUTHORITY:{field}"):
        API["verify"](root)


@pytest.mark.parametrize("kind", ["frozen_bytes", "rehash_r0", "remove_frozen", "remove_local",
                                  "shadow_module", "symlink", "evidence", "provenance", "self_hash"])
def test_furyan_tampering_fails_closed(qualification_copy, kind):
    root = qualification_copy
    manifest = json.loads((root / API["MANIFEST_REL"]).read_text())
    solver = root / COMPONENT / "FuryanLocusOracle.py"
    if kind in {"frozen_bytes", "rehash_r0"}:
        solver.write_bytes(solver.read_bytes() + b"\n# changed\n")
        if kind == "rehash_r0":
            manifest["frozen_r0_files"][solver.name] = API["sha"](solver.read_bytes())
            write_manifest(root, manifest)
        reason = "FROZEN_R0_AUTHORITY_CHANGED" if kind == "rehash_r0" else "FROZEN_R0_BYTES"
    elif kind == "remove_frozen":
        solver.unlink()
        reason = "MISSING"
    elif kind == "remove_local":
        (root / API["LOCAL_GATE"]).unlink()
        reason = "SOURCE_INVENTORY"
    elif kind == "shadow_module":
        (root / COMPONENT / "json.py").write_text("raise RuntimeError('shadow')\n")
        reason = "SOURCE_INVENTORY"
    elif kind == "symlink":
        solver.unlink()
        solver.symlink_to(root / COMPONENT / "contract.py")
        reason = "SYMLINK"
    elif kind == "evidence":
        (root / API["ROOT_GATE"]).write_text("# disabled science\n")
        reason = "EVIDENCE_BYTES"
    elif kind == "provenance":
        manifest["provenance"]["source_commit"] = "0" * 40
        write_manifest(root, manifest)
        reason = "MANIFEST_FIELD:provenance"
    else:
        manifest["manifest_self_hash"] = "0" * 64
        (root / API["MANIFEST_REL"]).write_text(json.dumps(manifest))
        reason = "MANIFEST_SELF_HASH"
    with pytest.raises(API["QualificationError"], match=reason):
        API["verify"](root)
