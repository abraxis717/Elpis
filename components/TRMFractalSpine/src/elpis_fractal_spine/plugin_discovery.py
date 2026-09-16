"""Explicit discovery of already-installed inference-driver plugins.

Discovery is local, metadata-driven, exact by abstract driver id, and never
runs automatically on import.  Registry TOML is not an import mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Iterable

from .provider_activation import InferenceDriverRegistry


ENTRY_POINT_GROUP = "elpis.inference_drivers.v1"


class InferenceDriverPluginError(RuntimeError):
    pass


class InstalledInferenceDriverNotFoundError(InferenceDriverPluginError):
    pass


class InstalledInferenceDriverConflictError(InferenceDriverPluginError):
    pass


class InferenceDriverAlreadyRegisteredError(InferenceDriverPluginError):
    pass


class InvalidInstalledInferenceDriverError(InferenceDriverPluginError):
    pass


class InstalledInferenceDriverLoadError(InferenceDriverPluginError):
    pass


@dataclass(frozen=True, order=True)
class InstalledInferenceDriverCandidate:
    driver_id: str
    distribution_name: str
    distribution_version: str
    entry_point_group: str
    entry_point_value: str


@dataclass(frozen=True)
class InferenceDriverPluginReceipt:
    driver_id: str
    distribution_name: str
    distribution_version: str
    entry_point_group: str
    entry_point_value: str


@dataclass(frozen=True)
class _CandidateRecord:
    candidate: InstalledInferenceDriverCandidate
    entry_point: metadata.EntryPoint


def _validate_driver_id(driver_id: str) -> str:
    if not isinstance(driver_id, str) or not driver_id:
        raise ValueError("driver_id must be a non-empty string")
    return driver_id


def _distribution_identity(
    distribution: metadata.Distribution,
) -> tuple[str, str]:
    name = distribution.metadata.get("Name")
    version = distribution.version
    if not isinstance(name, str) or not name:
        raise InferenceDriverPluginError(
            "installed driver distribution is missing Name metadata"
        )
    if not isinstance(version, str) or not version:
        raise InferenceDriverPluginError(
            f"installed driver distribution {name!r} is missing version metadata"
        )
    return name, version


def _candidate_records(driver_id: str) -> tuple[_CandidateRecord, ...]:
    requested = _validate_driver_id(driver_id)
    records: list[_CandidateRecord] = []

    for distribution in metadata.distributions():
        matching = tuple(
            entry_point
            for entry_point in distribution.entry_points
            if (
                entry_point.group == ENTRY_POINT_GROUP
                and entry_point.name == requested
            )
        )
        if not matching:
            continue

        distribution_name, distribution_version = _distribution_identity(
            distribution
        )
        for entry_point in matching:
            records.append(
                _CandidateRecord(
                    candidate=InstalledInferenceDriverCandidate(
                        driver_id=requested,
                        distribution_name=distribution_name,
                        distribution_version=distribution_version,
                        entry_point_group=ENTRY_POINT_GROUP,
                        entry_point_value=entry_point.value,
                    ),
                    entry_point=entry_point,
                )
            )

    records.sort(
        key=lambda record: (
            record.candidate.distribution_name,
            record.candidate.distribution_version,
            record.candidate.entry_point_value,
        )
    )
    return tuple(records)


def installed_inference_driver_candidates(
    driver_id: str,
) -> tuple[InstalledInferenceDriverCandidate, ...]:
    """Return metadata for exact-name installed candidates without loading code."""
    return tuple(
        record.candidate for record in _candidate_records(driver_id)
    )


def register_installed_inference_driver(
    driver_registry: InferenceDriverRegistry,
    driver_id: str,
) -> InferenceDriverPluginReceipt:
    """Load and register exactly one explicitly requested installed driver."""
    requested = _validate_driver_id(driver_id)

    if requested in driver_registry.registered_driver_ids():
        raise InferenceDriverAlreadyRegisteredError(
            f"driver already registered before discovery: {requested}"
        )

    records = _candidate_records(requested)
    if not records:
        raise InstalledInferenceDriverNotFoundError(
            f"no installed inference-driver plugin for {requested}"
        )
    if len(records) != 1:
        candidates = tuple(record.candidate for record in records)
        raise InstalledInferenceDriverConflictError(
            f"multiple installed inference-driver plugins for "
            f"{requested}: {candidates!r}"
        )

    record = records[0]
    try:
        factory = record.entry_point.load()
    except Exception as exc:
        raise InstalledInferenceDriverLoadError(
            f"failed to load installed inference-driver plugin for {requested}"
        ) from exc

    if not callable(factory):
        raise InvalidInstalledInferenceDriverError(
            f"installed inference-driver plugin for {requested} is not callable"
        )

    driver_registry.register(requested, factory)
    candidate = record.candidate
    return InferenceDriverPluginReceipt(
        driver_id=candidate.driver_id,
        distribution_name=candidate.distribution_name,
        distribution_version=candidate.distribution_version,
        entry_point_group=candidate.entry_point_group,
        entry_point_value=candidate.entry_point_value,
    )
