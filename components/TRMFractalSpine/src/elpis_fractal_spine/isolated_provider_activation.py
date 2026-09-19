"""Explicit host/bootstrap activation for wheel-isolated inference drivers.

This is a sibling lane to provider_activation. It never registers installed
drivers, performs plugin discovery, or grants model admission. The caller
supplies exact registry bytes, wheel authority, bounded policy expectations,
runtime context, and lifecycle policy explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .isolated_driver import (
    CanonicalContext,
    IsolatedProvider,
    StartupReceipt,
    SupervisorPolicy,
    WheelAuthority,
    activate_isolated_provider,
    bind_model_port,
    canonicalize_context,
)
from .isolated_driver.errors import AuthorityError, LifecycleError


@dataclass(frozen=True)
class ActivatedIsolatedInferenceProvider:
    """Host receipt plus the already-started isolated provider."""

    model_id: str
    port_id: str
    driver_id: str
    adapter_id: str
    registry_sha256: str
    authority_digest: str
    startup_receipt: StartupReceipt
    provider: IsolatedProvider

    def close(self) -> None:
        self.provider.close()

    def __enter__(self) -> "ActivatedIsolatedInferenceProvider":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        self.close()


def activate_isolated_model_provider(
    *,
    model_id: str,
    model_ports_path: Path,
    expected_model_ports_sha256: str,
    authority: WheelAuthority,
    wheel_path: Path,
    runtime_context: object,
    policy: SupervisorPolicy,
    expected_adapter_id: str,
    expected_admission_status: str,
    expected_authority_class: str,
) -> ActivatedIsolatedInferenceProvider:
    """Bind one exact disabled ON_DEMAND port and start its isolated worker.

    No fallback to the trusted installed-driver lane exists here.
    """
    if type(authority) is not WheelAuthority:
        raise AuthorityError("typed wheel authority required")
    if type(policy) is not SupervisorPolicy:
        raise LifecycleError("typed supervisor policy required")

    context = (
        runtime_context
        if type(runtime_context) is CanonicalContext
        else canonicalize_context(runtime_context)
    )

    bound = bind_model_port(
        model_ports_path=Path(model_ports_path),
        expected_sha256=expected_model_ports_sha256,
        model_id=model_id,
        expected_driver_id=authority.driver_id,
        expected_adapter_id=expected_adapter_id,
        expected_admission_status=expected_admission_status,
        expected_load_policy="ON_DEMAND",
        expected_authority_class=expected_authority_class,
    )

    provider = activate_isolated_provider(
        bound_port=bound,
        authority=authority,
        wheel_path=Path(wheel_path),
        runtime_context=context,
        policy=policy,
    )

    receipt = provider.receipt

    if receipt is None:
        try:
            provider.close()
        finally:
            raise LifecycleError(
                "isolated provider started without startup receipt"
            )

    if (
        receipt.authority_digest != authority.digest
        or receipt.context_digest != context.digest
    ):
        try:
            provider.close()
        finally:
            raise LifecycleError(
                "isolated startup receipt does not bind caller authority/context"
            )

    return ActivatedIsolatedInferenceProvider(
        model_id=bound.model_id,
        port_id=bound.port_id,
        driver_id=bound.driver_id,
        adapter_id=bound.adapter_id,
        registry_sha256=bound.registry_sha256,
        authority_digest=authority.digest,
        startup_receipt=receipt,
        provider=provider,
    )
