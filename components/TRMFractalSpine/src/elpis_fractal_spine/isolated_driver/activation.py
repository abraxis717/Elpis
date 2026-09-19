"""Additive activation lane; never uses InferenceDriverRegistry."""
from pathlib import Path

from .authority import WheelAuthority
from .context import CanonicalContext
from .errors import AuthorityError
from .registry import BoundModelPort
from .supervisor import IsolatedProvider, SupervisorPolicy


def activate_isolated_provider(*, bound_port: BoundModelPort, authority: WheelAuthority,
                               wheel_path: Path, runtime_context: CanonicalContext,
                               policy: SupervisorPolicy) -> IsolatedProvider:
    if type(bound_port) is not BoundModelPort or type(authority) is not WheelAuthority:
        raise AuthorityError("typed bound port/wheel authority required")
    if bound_port.driver_id != authority.driver_id:
        raise AuthorityError("bound port and wheel driver identities differ")
    if bound_port.load_policy != "ON_DEMAND":
        raise AuthorityError("isolated activation requires explicit ON_DEMAND policy")
    return IsolatedProvider(authority=authority, wheel_path=wheel_path,
                            runtime_context=runtime_context, policy=policy,
                            model_id=bound_port.model_id).start()
