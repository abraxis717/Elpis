from pathlib import Path
import importlib.util

def _load_policy():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "verify_no_production_asserts.py"
    spec = importlib.util.spec_from_file_location("verify_no_production_asserts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def test_no_plain_asserts_in_production_python():
    policy = _load_policy()
    assert policy.find_production_asserts() == []
