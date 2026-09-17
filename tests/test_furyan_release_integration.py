"""Release-integration gate for frozen Furyan R0 scientific authority.

The historical production differential remains frozen inside the Furyan
component as evidence of the allocator defect qualified by Elpis2.1.5.

Current-production allocator behavior is intentionally qualified separately:
once that defect is repaired, successor releases must not require production
to continue returning the historical failure.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components/FuryanLocusOracle"
FURYAN_TESTS = COMPONENT / "tests"
SOLVER_PATH = COMPONENT / "FuryanLocusOracle.py"

sys.path.insert(0, str(FURYAN_TESTS))
sys.path.insert(0, str(COMPONENT))

import contract
import certificate_validator
import guards
import corpus
import reference
import baseline
import mutations

# Component qualification owns the inventory; the verifier independently pins
# its aggregate to the original eleven R0 hashes.
import json
import runpy

QUALIFICATION = runpy.run_path(str(ROOT / "tools/verify_furyan_locus_oracle.py"))
MANIFEST = json.loads((COMPONENT / "COMPONENT_MANIFEST.json").read_text())
EXPECTED_FILES = {
    str(Path("components/FuryanLocusOracle") / name): digest
    for name, digest in MANIFEST["frozen_r0_files"].items()
}


EXPECTED_COUNTS = {
    "1": {"canonical": 1, "labeled": 1, "SAT": 1, "UNSAT": 0},
    "2": {"canonical": 36, "labeled": 64, "SAT": 8, "UNSAT": 28},
    "3": {"canonical": 43968, "labeled": 262144, "SAT": 456, "UNSAT": 43512},
}

EXPECTED_INVENTORY_SHA256 = (
    "29645430e5cc6500f74e99091a233562ce116e6853df3bc0205f5cf12ef3488f"
)

EXPECTED_MINIMAL = [
    {
        "operations": ["A", "B", "C"],
        "edges": [["route", "A", "B"], ["route", "C", "B"]],
        "tails": [],
    },
    {
        "operations": ["A", "B", "C"],
        "edges": [
            ["state_feeds", "A", "B"],
            ["state_feeds", "A", "C"],
        ],
        "tails": [],
    },
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_solver():
    spec = importlib.util.spec_from_file_location(
        "furyan_release_under_test",
        SOLVER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_scientific_inventory_and_hashes():
    QUALIFICATION["verify"](ROOT)
    for rel, expected in EXPECTED_FILES.items():
        assert sha(ROOT / rel) == expected, rel
    assert contract.MODEL_DIGEST == MANIFEST["model_digest"]


def test_focused_certificates_and_mutations():
    solver = load_solver()

    assert guards.focused(solver)
    assert guards.certificates(solver)

    target = solver.solve(guards.TARGET)
    assert target["status"] == "SAT"
    assert target["certificate"]["operations"] == {
        "A": 0,
        "B": 0,
        "C": 3,
    }
    assert [x["rank"] for x in target["certificate"]["loci"]] == [1, 2]

    certificate_validator.validate_result(
        guards.TARGET,
        target,
    )

    assert baseline.earliest(guards.TARGET) == {
        "status": "FAIL",
        "reason": "auxiliary_capacity",
        "operations": {"A": 0, "B": 0, "C": 2},
    }

    records = mutations.run(solver, SOLVER_PATH)

    assert len(records) == 12
    assert [x["mutant"] for x in records] == [
        f"M{i}" for i in range(1, 13)
    ]
    assert all(x["result"] == "KILLED" for x in records)


def test_historical_production_differential_remains_frozen_evidence():
    """The old production-defect witness remains byte-identical evidence."""
    rel = "components/FuryanLocusOracle/tests/production_differential.py"

    assert sha(ROOT / rel) == EXPECTED_FILES[rel]



def test_exhaustive_44005_case_reference_equivalence_and_minimality():
    solver = load_solver()

    counts = {}
    stream = hashlib.sha256()

    minimal_key = None
    minimal = []

    for n in (1, 2, 3):
        cases = corpus.canonical_core(n)

        count = {
            "canonical": len(cases),
            "labeled": sum(size for _, size in cases),
            "SAT": 0,
            "UNSAT": 0,
        }

        for raw, orbit_size in cases:
            result = solver.solve(raw)
            expected_status = (
                "SAT" if reference.brute(raw) else "UNSAT"
            )

            assert result["status"] == expected_status, corpus.serial(raw)

            if expected_status == "SAT":
                certificate_validator.validate_result(raw, result)

            count[expected_status] += 1

            stream.update(
                contract.canonical(
                    {
                        "input": raw,
                        "status": result["status"],
                        "orbit_size": orbit_size,
                    }
                )
                + b"\n"
            )

            if (
                result["status"] == "SAT"
                and baseline.earliest(raw)["status"] == "FAIL"
            ):
                key = (n, len(raw["edges"]))

                if minimal_key is None:
                    minimal_key = key

                if key == minimal_key:
                    minimal.append(raw)

        counts[str(n)] = count

    assert sum(v["canonical"] for v in counts.values()) == 44005
    assert counts == EXPECTED_COUNTS
    assert stream.hexdigest() == EXPECTED_INVENTORY_SHA256

    assert minimal_key == (3, 2)
    assert minimal == EXPECTED_MINIMAL


def test_fresh_process_sat_and_unsat_byte_identity(tmp_path):
    cases = {
        "SAT": guards.TARGET,
        "UNSAT": corpus.instance(
            "AB",
            [
                ("precedes", "A", "B"),
                ("precedes", "B", "A"),
            ],
        ),
    }

    for status, raw in cases.items():
        outputs = []

        for seed, cwd in (
            ("1", ROOT),
            ("999", tmp_path),
            ("42", ROOT),
        ):
            env = dict(
                os.environ,
                PYTHONHASHSEED=seed,
                PYTHONDONTWRITEBYTECODE="1",
            )

            env.pop("PYTHONPATH", None)
            env["PYTHONNOUSERSITE"] = "1"

            outputs.append(
                subprocess.check_output(
                    [sys.executable, str(SOLVER_PATH)],
                    input=contract.canonical(raw),
                    cwd=cwd,
                    env=env,
                )
            )

        assert outputs[0] == outputs[1] == outputs[2]
        assert json.loads(outputs[0])["status"] == status
