"""Explicit inference-driver activation for qualified model ports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping
import tomllib


class DriverActivationError(RuntimeError):
    pass


class DriverNotRegisteredError(DriverActivationError):
    pass


class DuplicateDriverRegistrationError(DriverActivationError):
    pass


class InvalidInferenceProviderError(DriverActivationError):
    pass


DriverFactory = Callable[[Mapping[str, Any]], object]


@dataclass(frozen=True)
class ActivatedInferenceProvider:
    model_id: str
    port_id: str
    driver_id: str
    adapter_id: str
    provider: object


class InferenceDriverRegistry:
    """Caller-owned driver-id -> provider-factory mapping."""

    def __init__(self) -> None:
        self._factories: dict[str, DriverFactory] = {}

    def register(self, driver_id: str, factory: DriverFactory) -> None:
        if not isinstance(driver_id, str) or not driver_id.strip():
            raise ValueError("driver_id must be a non-empty string")
        if not callable(factory):
            raise TypeError("driver factory must be callable")
        if driver_id in self._factories:
            raise DuplicateDriverRegistrationError(
                f"driver already registered: {driver_id}"
            )
        self._factories[driver_id] = factory

    def registered_driver_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def resolve(
        self,
        driver_id: str,
        runtime_context: Mapping[str, Any],
    ) -> object:
        try:
            factory = self._factories[driver_id]
        except KeyError as exc:
            raise DriverNotRegisteredError(
                f"no local driver registered for {driver_id}"
            ) from exc

        context = MappingProxyType(dict(runtime_context))
        provider = factory(context)
        missing = tuple(
            name
            for name in ("acquire", "release", "execute")
            if not callable(getattr(provider, name, None))
        )
        if missing:
            raise InvalidInferenceProviderError(
                f"driver {driver_id} returned provider missing {missing!r}"
            )
        return provider


def _load_model_ports(
    path: Path,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "elpis.model-ports.v1":
        raise DriverActivationError("unsupported model-port registry schema")
    if data.get("network_allowed") is not False:
        raise DriverActivationError("model-port registry must deny network")
    if data.get("remote_code_allowed") is not False:
        raise DriverActivationError("model-port registry must deny remote code")
    return data, tuple(data.get("port") or ())


def activate_model_provider(
    *,
    model_id: str,
    model_ports_path: Path,
    driver_registry: InferenceDriverRegistry,
    runtime_context: Mapping[str, Any],
) -> ActivatedInferenceProvider:
    _, rows = _load_model_ports(Path(model_ports_path))
    matches = tuple(row for row in rows if row.get("model_id") == model_id)
    if len(matches) != 1:
        raise DriverActivationError(
            f"expected exactly one model port for {model_id!r}, got {len(matches)}"
        )

    row = matches[0]
    if row.get("enabled") is not False:
        raise DriverActivationError(
            "bounded explicit port must remain globally disabled"
        )
    if row.get("load_policy") != "ON_DEMAND":
        raise DriverActivationError("bounded explicit port must use ON_DEMAND")
    if row.get("network_allowed") is not False:
        raise DriverActivationError("bounded explicit port must deny network")
    if row.get("remote_code_allowed") is not False:
        raise DriverActivationError(
            "bounded explicit port must deny remote code"
        )
    if row.get("admission_status") != "BOUNDED_R2_SUDOKU_FEEDBACK_V1":
        raise DriverActivationError(
            "model port is outside the qualified bounded profile"
        )

    driver_id = row.get("driver_id")
    adapter_id = row.get("adapter_id")
    port_id = row.get("port_id")
    if not all(
        isinstance(value, str) and value
        for value in (driver_id, adapter_id, port_id)
    ):
        raise DriverActivationError(
            "model port has incomplete activation identity"
        )

    provider = driver_registry.resolve(driver_id, runtime_context)
    return ActivatedInferenceProvider(
        model_id=model_id,
        port_id=port_id,
        driver_id=driver_id,
        adapter_id=adapter_id,
        provider=provider,
    )
