"""Bounded Cadence experiment over a complete committed ECS prefix.

Cadence is an external exact donor supplied explicitly by the caller for
research/conformance only. No learned state, kernel handle, proposal, selection
result or execution capability escapes the call.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

from elpis.canonical_identity import content_digest
from elpis_ecs.errors import EcsError
from elpis_ecs_context.contracts import ContextProjection, EVENT_KINDS, ProjectionRequest
from elpis_ecs_context.projector import project_history

DONOR_COMMIT = "f12f1bb30286f5bc0b339853cabe94fc9fbb3ffe"
DONOR_SOURCE_DIGEST = "a408b7db453ccef348f6bc31d2f55f081d8e132a2b0907534343ffe202bf917f"
DONOR_SOURCE_FILE_COUNT = 44
DONOR_DIGEST_DOMAIN = "elpis.cadence-python-source.v1"
DONOR_AUTHORITY_SCHEMA = "elpis.cadence-external-donor-authority.v1"
PROFILE = "ECS_COMMITTED_EVENT_KIND_PREQUENTIAL_R0"
KINDS = (
    "ENTITY_ACTIVATED", "ENTITY_DORMANT", "ENTITY_FOUNDED",
    "ENTITY_REACTIVATED", "ENTITY_TERMINATED", "MESSAGE_ENQUEUED",
    "MESSAGE_PROCESSED",
)
MAX_EVENTS = 64
MAX_RECORD_BYTES = 1024 * 1024
HIDDEN = 8
CELLS = 32
ACTIVE = 4


class ProbeError(ValueError):
    """Rejected experiment; no partial report or persistent state."""


@dataclass(frozen=True)
class ProbeStep:
    input_event_index: int
    observed_event_index: int
    observed_kind: str
    scores: tuple[float, ...]
    mean_squared_error: float
    slow_updated: bool
    update_reason: str
    record_writes: int
    replay_calls: int


@dataclass(frozen=True)
class ProbeReport:
    profile: str
    donor_commit: str
    donor_source_digest: str
    projection_digest: str
    history_head: str
    history_root: str
    seed: int
    kinds: tuple[str, ...]
    steps: tuple[ProbeStep, ...]
    updates: int
    writes: int
    final_context: tuple[float, ...]
    runtime_admission: bool = False

    @property
    def digest(self) -> str:
        return content_digest("elpis.cadence-ecs-probe.report.v1", self)


def _component_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_authority() -> dict:
    authority_path = _component_root() / "CADENCE_DONOR_AUTHORITY.json"
    try:
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError("DONOR_AUTHORITY_UNREADABLE") from exc
    expected = {
        "schema": DONOR_AUTHORITY_SCHEMA,
        "donor_id": "cadence-net-0.16.0-f12f1bb",
        "fork_repository": "https://github.com/abraxis717/cadence.git",
        "upstream_repository": "https://github.com/muellerberndt/cadence",
        "commit": DONOR_COMMIT,
        "distribution": "cadence-net",
        "version": "0.16.0",
        "license": "MIT",
        "copyright": "Copyright (c) 2026 Bernhard Mueller",
        "source_package_relative_path": "src/cadence",
        "source_file_count": DONOR_SOURCE_FILE_COUNT,
        "source_digest": DONOR_SOURCE_DIGEST,
        "digest_domain": DONOR_DIGEST_DOMAIN,
        "usage_class": "EXTERNAL_QUALIFICATION_DONOR",
        "runtime_admission": False,
        "root_distribution_inclusion": False,
    }
    if authority != expected:
        raise ProbeError("DONOR_AUTHORITY_MISMATCH")
    return authority


def _resolve_donor_root(donor_root: str | os.PathLike[str] | None) -> Path:
    if donor_root is None or isinstance(donor_root, bool):
        raise ProbeError("DONOR_ROOT_REQUIRED")
    try:
        root = Path(donor_root).expanduser().resolve(strict=True)
    except (TypeError, ValueError, OSError) as exc:
        raise ProbeError("DONOR_ROOT_INVALID") from exc
    if not root.is_dir():
        raise ProbeError("DONOR_ROOT_INVALID")
    return root


def _module_origin(name: str) -> Path | None:
    module = sys.modules.get(name)
    if module is not None:
        filename = getattr(module, "__file__", None)
        if filename:
            try:
                return Path(filename).resolve()
            except OSError:
                return None
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    try:
        return Path(spec.origin).resolve()
    except OSError:
        return None


def _load_donor(donor_root: str | os.PathLike[str] | None):
    """Verify caller-supplied donor without Git, downloads or sys.path edits."""
    authority = _load_authority()
    root = _resolve_donor_root(donor_root)
    package = root / authority["source_package_relative_path"]
    if not package.is_dir() or not (package / "__init__.py").is_file():
        raise ProbeError("DONOR_SOURCE_MISSING")

    sources = {
        source.relative_to(package).as_posix(): source.read_bytes()
        for source in sorted(package.rglob("*.py"))
        if source.is_file()
    }
    if len(sources) != authority["source_file_count"]:
        raise ProbeError("DONOR_SOURCE_FILE_COUNT_MISMATCH")
    digest = content_digest(authority["digest_domain"], sources)
    if digest != authority["source_digest"] or digest != DONOR_SOURCE_DIGEST:
        raise ProbeError("DONOR_SOURCE_MISMATCH")

    expected_init = (package / "__init__.py").resolve()
    if _module_origin("cadence") != expected_init:
        raise ProbeError("PINNED_DONOR_NOT_ON_SOURCE_PATH")
    try:
        from cadence.record_patch import RecordPatchNet
    except (ImportError, ModuleNotFoundError) as exc:
        raise ProbeError("DONOR_IMPORT_FAILED") from exc
    expected_record_patch = (package / "record_patch.py").resolve()
    if _module_origin("cadence.record_patch") != expected_record_patch:
        raise ProbeError("DONOR_MODULE_MISMATCH")
    return RecordPatchNet, digest


def _events(projection: ContextProjection) -> list[dict]:
    if type(projection) is not ContextProjection:
        raise ProbeError("CONTEXT_PROJECTION_REQUIRED")
    if type(projection.records) is not tuple or not 2 <= len(projection.records) <= MAX_EVENTS:
        raise ProbeError("EVENT_BUDGET_OR_EMPTY_HISTORY")
    if sum(len(record.record_bytes) for record in projection.records) > MAX_RECORD_BYTES:
        raise ProbeError("RECORD_BYTE_BUDGET")
    if projection.truncated or projection.source.event_count != len(projection.records):
        raise ProbeError("COMPLETE_PREFIX_REQUIRED")
    request = projection.request
    if request != ProjectionRequest(
        max_records=request.max_records,
        max_record_bytes=request.max_record_bytes,
    ):
        raise ProbeError("UNFILTERED_PREFIX_REQUIRED")
    if frozenset(KINDS) != EVENT_KINDS:
        raise ProbeError("EVENT_KIND_CONTRACT_CHANGED")
    try:
        events = [json.loads(record.record_bytes) for record in projection.records]
        verified = project_history(
            projection.source.genesis_digest,
            events,
            request,
            mailbox_capacity=projection.source.mailbox_capacity,
            scheduler_protocol=projection.source.scheduler_protocol,
        )
        if verified.canonical_bytes() != projection.canonical_bytes():
            raise ProbeError("PROJECTION_BINDING_MISMATCH")
    except (EcsError, ValueError, TypeError, KeyError) as exc:
        raise ProbeError("INVALID_HISTORY") from exc
    return events


def evaluate_history(
    projection: ContextProjection,
    *,
    seed: int = 0,
    donor_root: str | os.PathLike[str] | None = None,
) -> ProbeReport:
    """Run one offline, fresh-model experiment; this grants no runtime admission."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ProbeError("INVALID_SEED")
    # Replay and reject invalid input before resolving/importing donor code.
    events = _events(projection)
    patch_type, donor_digest = _load_donor(donor_root)
    import numpy as np

    patch = patch_type(
        len(KINDS), HIDDEN, len(KINDS), seed=seed,
        cells=CELLS, active=ACTIVE, slowest=8.0,
    )
    one_hot = np.eye(len(KINDS), dtype=np.float64)
    steps = []
    for current, observed in zip(events, events[1:]):
        inputs = one_hot[KINDS.index(current["event_kind"])][None, None, :]
        prediction = patch.imagine(inputs)
        scores = tuple(float(value) for value in prediction.output[0, 0])
        if not all(math.isfinite(value) for value in scores):
            raise ProbeError("NONFINITE_PREDICTION")
        target = one_hot[KINDS.index(observed["event_kind"])][None, None, :]
        error = float(np.mean((prediction.output - target) ** 2))
        update = patch.observe(inputs, target, rate=0.5, backtrack=True)
        if not np.array_equal(update.prediction.output, prediction.output):
            raise ProbeError("PREQUENTIAL_PREDICTION_MISMATCH")
        if not math.isfinite(error) or not 0 <= update.replay_calls <= 16 or update.writes != 1:
            raise ProbeError("DONOR_RESULT_OUTSIDE_CONTRACT")
        steps.append(ProbeStep(
            current["event_index"], observed["event_index"], observed["event_kind"],
            scores, error, bool(update.updated), update.reason,
            update.writes, update.replay_calls,
        ))
    readback = patch.readback()
    context = tuple(float(value) for value in readback.state[0])
    if not all(math.isfinite(value) and abs(value) <= 1.0 for value in context):
        raise ProbeError("INVALID_BOUNDED_CONTEXT")
    return ProbeReport(
        PROFILE, DONOR_COMMIT, donor_digest, projection.projection_digest,
        projection.source.head_event_digest, projection.source.final_state_root,
        seed, KINDS, tuple(steps), readback.updates, readback.writes, context,
    )
