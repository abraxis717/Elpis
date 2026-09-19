"""Fixed error taxonomy; child exception names never select parent classes."""


class IsolatedDriverError(RuntimeError):
    """Base for the additive isolated-driver API."""


class AuthorityError(IsolatedDriverError):
    pass


class WheelError(AuthorityError):
    pass


class RegistryError(AuthorityError):
    pass


class ContextError(IsolatedDriverError):
    pass


class InfrastructureError(IsolatedDriverError):
    pass


class ProtocolError(InfrastructureError):
    pass


class WorkerTimeout(InfrastructureError):
    pass


class SandboxError(InfrastructureError):
    pass


class LifecycleError(IsolatedDriverError):
    pass


class ProviderError(IsolatedDriverError):
    """A provider operation raised; never an ordinary inference result."""
