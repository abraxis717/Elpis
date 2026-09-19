"""Byte-bound model-port selection; does not admit or change any model."""
from dataclasses import dataclass
from pathlib import Path

from ..structural_refinement import _sha256_hex
import tomllib

from .authority import identifier, sha256_identity
from .errors import AuthorityError, RegistryError

MAX_REGISTRY_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class BoundModelPort:
    registry_sha256: str
    model_id: str
    port_id: str
    driver_id: str
    adapter_id: str
    admission_status: str
    load_policy: str
    authority_class: str

    def __post_init__(self) -> None:
        try:
            sha256_identity(self.registry_sha256)
            for value in (self.model_id, self.port_id, self.driver_id, self.adapter_id,
                          self.admission_status, self.load_policy, self.authority_class):
                identifier(value)
        except AuthorityError as exc:
            raise RegistryError("invalid bound port identity") from exc


def bind_model_port(*, model_ports_path: Path, expected_sha256: str,
                    model_id: str, expected_driver_id: str, expected_adapter_id: str,
                    expected_admission_status: str, expected_load_policy: str,
                    expected_authority_class: str) -> BoundModelPort:
    """Read once, hash and parse those exact bytes; expected policy is mandatory."""
    try:
        sha256_identity(expected_sha256)
        for value in (model_id, expected_driver_id, expected_adapter_id,
                      expected_admission_status, expected_load_policy, expected_authority_class):
            identifier(value)
        with Path(model_ports_path).open("rb") as source:
            raw = source.read(MAX_REGISTRY_BYTES + 1)
        if len(raw) > MAX_REGISTRY_BYTES or _sha256_hex(raw) != expected_sha256:
            raise RegistryError("registry byte identity/size mismatch")
        data = tomllib.loads(raw.decode("utf-8"))
        if data.get("schema_version") != "elpis.model-ports.v1":
            raise RegistryError("unsupported registry schema")
        if any(data.get(key) is not False for key in ("network_allowed", "remote_code_allowed")):
            raise RegistryError("registry must deny network/remote code")
        rows = data.get("port")
        if type(rows) is not list or any(type(row) is not dict for row in rows):
            raise RegistryError("invalid model port rows")
        matches = [row for row in rows if row.get("model_id") == model_id]
        if len(matches) != 1:
            raise RegistryError("expected exactly one matching model port")
        row = matches[0]
        if any(row.get(key) is not False for key in ("enabled", "network_allowed", "remote_code_allowed")):
            raise RegistryError("model port must remain disabled and deny network/remote code")
        expected = {"driver_id": expected_driver_id, "adapter_id": expected_adapter_id,
                    "admission_status": expected_admission_status, "load_policy": expected_load_policy,
                    "authority_class": expected_authority_class}
        if any(row.get(key) != value for key, value in expected.items()):
            raise RegistryError("model port identity/policy mismatch")
        return BoundModelPort(expected_sha256, model_id, row.get("port_id"), **expected)
    except (OSError, ValueError, UnicodeError, AuthorityError) as exc:
        if isinstance(exc, RegistryError):
            raise
        raise RegistryError("cannot bind model-port registry") from exc
