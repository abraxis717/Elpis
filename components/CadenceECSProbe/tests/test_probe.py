from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from elpis_ecs.kernel import Kernel
from elpis_ecs_context.contracts import ProjectionRequest
from elpis_ecs_context.kernel_adapter import project_kernel_history
from elpis_cadence_ecs import RUNTIME_ADMISSION, ProbeError, evaluate_history
from elpis_cadence_ecs import probe


@pytest.fixture
def history(tmp_path):
    with Kernel(str(tmp_path / "ecs")) as kernel:
        entity = kernel.found_entity("observed")
        kernel.activate(entity)
        for _ in range(12):
            kernel.dormant(entity)
            kernel.reactivate(entity)
        yield kernel, project_kernel_history(kernel, ProjectionRequest())


@pytest.fixture
def cadence_root():
    raw = os.environ.get("ELPIS_CADENCE_DONOR_ROOT")
    if raw is None:
        pytest.skip("external Cadence donor not supplied to this conformance lane")
    root = Path(raw).resolve()
    assert (root / "src/cadence/__init__.py").is_file()
    return root


def _subprocess_env(root: Path, cadence_root: Path, hashseed: int) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONHASHSEED"] = str(hashseed)
    env["ELPIS_CADENCE_DONOR_ROOT"] = str(cadence_root)
    env["PYTHONPATH"] = os.pathsep.join(
        str(root / rel)
        for rel in (
            "src",
            "ECS/runtime",
            "components/ECSContextProjector/src",
            "components/CadenceECSProbe/src",
        )
    ) + os.pathsep + str(cadence_root / "src")
    return env


def _fresh_report_digest(cadence_root: Path, hashseed: int, *, contaminate: bool) -> str:
    root = Path(__file__).resolve().parents[3]
    code = r'''
import os
from pathlib import Path
import tempfile
from elpis_ecs.kernel import Kernel
from elpis_ecs_context.contracts import ProjectionRequest
from elpis_ecs_context.kernel_adapter import project_kernel_history
from elpis_cadence_ecs import evaluate_history

donor = Path(os.environ["ELPIS_CADENCE_DONOR_ROOT"])

def history_a(base):
    with Kernel(str(base / "a")) as kernel:
        entity = kernel.found_entity("a")
        kernel.activate(entity)
        for _ in range(5):
            kernel.dormant(entity)
            kernel.reactivate(entity)
        return project_kernel_history(kernel, ProjectionRequest())

def history_b(base):
    with Kernel(str(base / "b")) as kernel:
        for index in range(9):
            kernel.found_entity("b-" + str(index))
        return project_kernel_history(kernel, ProjectionRequest())

with tempfile.TemporaryDirectory() as raw:
    base = Path(raw)
    if os.environ.get("ELPIS_CONTAMINATE") == "1":
        evaluate_history(history_a(base), seed=717, donor_root=donor)
    report = evaluate_history(history_b(base), seed=717, donor_root=donor)
    print(report.digest)
'''
    env = _subprocess_env(root, cadence_root, hashseed)
    env["ELPIS_CONTAMINATE"] = "1" if contaminate else "0"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert len(lines[0]) == 64
    return lines[0]


def test_external_donor_authority_record_is_exact_and_path_free():
    component_root = Path(__file__).resolve().parents[1]
    authority = json.loads((component_root / "CADENCE_DONOR_AUTHORITY.json").read_text(encoding="utf-8"))
    manifest = json.loads((component_root / "COMPONENT_MANIFEST.json").read_text(encoding="utf-8"))
    assert authority["schema"] == probe.DONOR_AUTHORITY_SCHEMA
    assert authority["commit"] == probe.DONOR_COMMIT == manifest["donor_commit"]
    assert authority["source_digest"] == probe.DONOR_SOURCE_DIGEST == manifest["donor_source_digest"]
    assert authority["source_file_count"] == probe.DONOR_SOURCE_FILE_COUNT == 44
    assert authority["source_package_relative_path"] == "src/cadence"
    assert manifest["donor_authority"] == "CADENCE_DONOR_AUTHORITY.json"
    assert authority["runtime_admission"] is False
    assert authority["root_distribution_inclusion"] is False
    assert manifest["runtime_admission"] is False
    assert manifest["root_distribution_inclusion"] is False
    serialized = json.dumps(authority)
    assert "/mnt/" not in serialized
    assert "third_party/cadence" not in serialized


def test_real_ecs_to_cadence_learning_is_local_and_repeatable(history, cadence_root):
    kernel, projection = history
    before = kernel.snapshot(), kernel.events(), projection.canonical_bytes()
    first = evaluate_history(projection, seed=717, donor_root=cadence_root)
    second = evaluate_history(projection, seed=717, donor_root=cadence_root)
    assert first == second and first.digest == second.digest
    assert (kernel.snapshot(), kernel.events(), projection.canonical_bytes()) == before
    assert first.projection_digest == projection.projection_digest
    assert len(first.steps) == len(projection.records) - 1
    assert first.writes == len(first.steps)
    assert first.updates == sum(step.slow_updated for step in first.steps)
    assert 0 < first.updates <= len(first.steps)
    assert sum(step.replay_calls for step in first.steps) <= 16 * len(first.steps)
    assert all(abs(value) <= 1 for value in first.final_context)
    assert not first.runtime_admission and not RUNTIME_ADMISSION
    assert np.mean([step.mean_squared_error for step in first.steps[-6:]]) < np.mean(
        [step.mean_squared_error for step in first.steps[:6]]
    )


def test_predictions_precede_targets_and_later_history_does_not_change_prefix(tmp_path, cadence_root):
    with Kernel(str(tmp_path / "prefix")) as kernel:
        entity = kernel.found_entity("a")
        kernel.activate(entity)
        short = evaluate_history(
            project_kernel_history(kernel, ProjectionRequest()), donor_root=cadence_root
        )
        kernel.dormant(entity)
        longer = evaluate_history(
            project_kernel_history(kernel, ProjectionRequest()), donor_root=cadence_root
        )
    assert longer.steps[:1] == short.steps
    assert longer.projection_digest != short.projection_digest
    with Kernel(str(tmp_path / "other")) as kernel:
        kernel.found_entity("a")
        kernel.found_entity("b")
        other = evaluate_history(
            project_kernel_history(kernel, ProjectionRequest()), donor_root=cadence_root
        )
    assert other.steps[0].observed_kind != short.steps[0].observed_kind
    assert other.steps[0].scores == short.steps[0].scores


def test_repair_and_readback_follow_exact_donor_arithmetic(history, cadence_root):
    from cadence.record_patch import RecordPatchNet

    _, projection = history
    report = evaluate_history(projection, seed=4, donor_root=cadence_root)
    donor = RecordPatchNet(7, 8, 7, seed=4, cells=32, active=4, slowest=8.0)
    eye = np.eye(7)
    events = [json.loads(record.record_bytes) for record in projection.records]
    for step, current, observed in zip(report.steps, events, events[1:]):
        x = eye[report.kinds.index(current["event_kind"])][None, None, :]
        y = eye[report.kinds.index(observed["event_kind"])][None, None, :]
        snapshot = donor.snapshot()
        imagined = donor.imagine(x)
        for name, value in snapshot.items():
            np.testing.assert_array_equal(value, donor.snapshot()[name])
        np.testing.assert_array_equal(imagined.output[0, 0], step.scores)
        update = donor.observe(x, y, rate=0.5, backtrack=True)
        assert (
            step.slow_updated,
            step.update_reason,
            step.record_writes,
            step.replay_calls,
        ) == (update.updated, update.reason, update.writes, update.replay_calls)
    np.testing.assert_array_equal(report.final_context, donor.readback().state[0])


@pytest.mark.parametrize(
    "case", ["truncated", "filtered", "reordered", "root", "payload", "bytes", "count"]
)
def test_invalid_history_fails_before_cadence(history, monkeypatch, case):
    kernel, projection = history
    if case == "truncated":
        projection = project_kernel_history(kernel, ProjectionRequest(max_records=2))
    elif case == "filtered":
        projection = replace(projection, request=ProjectionRequest(kind_pattern="ENTITY*"))
    elif case == "reordered":
        projection = replace(projection, records=projection.records[::-1])
    elif case == "root":
        projection = replace(
            projection,
            source=replace(projection.source, final_state_root="0" * 64),
        )
    elif case == "payload":
        record = projection.records[0]
        event = json.loads(record.record_bytes)
        event["payload"] = {}
        projection = replace(
            projection,
            records=(
                replace(record, record_bytes=json.dumps(event).encode()),
                *projection.records[1:],
            ),
        )
    elif case == "bytes":
        projection = replace(
            projection,
            records=(
                replace(
                    projection.records[0],
                    record_bytes=b" " * (probe.MAX_RECORD_BYTES + 1),
                ),
                *projection.records[1:],
            ),
        )
    else:
        projection = replace(projection, records=projection.records * 3)

    def forbidden(*args, **kwargs):
        del args, kwargs
        pytest.fail("invalid input reached Cadence")

    monkeypatch.setattr(probe, "_load_donor", forbidden)
    with pytest.raises((ProbeError, ValueError)):
        evaluate_history(projection)


@pytest.mark.parametrize("seed", [True, -1, 2**32, 0.5, "0"])
def test_seed_bounds(history, seed):
    with pytest.raises(ProbeError, match="INVALID_SEED"):
        evaluate_history(history[1], seed=seed)


def test_exact_event_budget_and_small_histories(tmp_path, cadence_root):
    with Kernel(str(tmp_path / "budget")) as kernel:
        for _ in range(2):
            with pytest.raises(ProbeError, match="EVENT_BUDGET"):
                evaluate_history(project_kernel_history(kernel, ProjectionRequest()))
            kernel.found_entity("small")
        for index in range(62):
            kernel.found_entity(str(index))
        assert len(
            evaluate_history(
                project_kernel_history(kernel, ProjectionRequest()),
                donor_root=cadence_root,
            ).steps
        ) == 63
        kernel.found_entity("overflow")
        with pytest.raises(ProbeError):
            evaluate_history(
                project_kernel_history(kernel, ProjectionRequest(max_records=65)),
                donor_root=cadence_root,
            )


def test_missing_donor_fails_closed(history, tmp_path):
    with pytest.raises(ProbeError, match="DONOR_SOURCE_MISSING"):
        evaluate_history(history[1], donor_root=tmp_path)


def test_substituted_import_origin_fails_closed(history, cadence_root, tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_module_origin", lambda name: tmp_path / (name + ".py"))
    with pytest.raises(ProbeError, match="PINNED_DONOR_NOT_ON_SOURCE_PATH"):
        evaluate_history(history[1], donor_root=cadence_root)


def test_valid_history_requires_explicit_donor_root(history):
    with pytest.raises(ProbeError, match="DONOR_ROOT_REQUIRED"):
        evaluate_history(history[1])


def test_donor_source_drift_fails_closed(history, cadence_root, monkeypatch):
    original = probe.content_digest
    monkeypatch.setattr(
        probe,
        "content_digest",
        lambda domain, value: "0" * 64
        if domain == probe.DONOR_DIGEST_DOMAIN
        else original(domain, value),
    )
    with pytest.raises(ProbeError, match="DONOR_SOURCE_MISMATCH"):
        evaluate_history(history[1], donor_root=cadence_root)


def test_fresh_process_report_is_hashseed_independent(cadence_root):
    digests = {
        _fresh_report_digest(cadence_root, seed, contaminate=False)
        for seed in (0, 717, 845813583)
    }
    assert len(digests) == 1


def test_prior_unrelated_probe_cannot_contaminate_fresh_history(cadence_root):
    contaminated = _fresh_report_digest(cadence_root, 717, contaminate=True)
    fresh = _fresh_report_digest(cadence_root, 717, contaminate=False)
    assert contaminated == fresh


def test_import_alone_has_no_donor_or_runtime_side_effects():
    code = """
import sys
import elpis_cadence_ecs
assert not elpis_cadence_ecs.RUNTIME_ADMISSION
for prefix in ('cadence', 'torch', 'elpis_sot', 'elpis_runtime_r3', 'elpis_runtime_r4', 'DarwinianMatrix'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
"""
    root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    env.pop("ELPIS_CADENCE_DONOR_ROOT", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        str(root / rel)
        for rel in (
            "src",
            "ECS/runtime",
            "components/ECSContextProjector/src",
            "components/CadenceECSProbe/src",
        )
    )
    subprocess.run([sys.executable, "-c", code], cwd=root, env=env, check=True)
