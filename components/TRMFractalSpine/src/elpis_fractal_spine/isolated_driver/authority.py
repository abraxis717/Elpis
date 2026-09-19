"""Caller-supplied artifact identity, independent of installed distributions."""
from dataclasses import asdict, dataclass
import hashlib
import re

from .context import canonical_bytes
from .errors import AuthorityError


def identifier(value: str) -> None:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", value):
        raise AuthorityError("invalid authority identifier")


def sha256_identity(value: str) -> None:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AuthorityError("SHA-256 must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True)
class WheelAuthority:
    driver_id: str
    distribution_name: str
    distribution_version: str
    entry_point_group: str
    entry_point_value: str
    wheel_sha256: str

    def __post_init__(self) -> None:
        for value in (self.driver_id, self.entry_point_group):
            identifier(value)
        if type(self.distribution_version) is not str or len(self.distribution_version) > 100 or not re.fullmatch(
            r"[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?(?:\+[a-z0-9]+(?:\.[a-z0-9]+)*)?",
            self.distribution_version,
        ):
            raise AuthorityError("version must use R0's canonical numeric release/version subset")
        if type(self.distribution_name) is not str or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", self.distribution_name
        ):
            raise AuthorityError("distribution name must be canonical lowercase/hyphen form")
        if len(self.distribution_name) > 200:
            raise AuthorityError("distribution name too long")
        part = r"[A-Za-z_][A-Za-z0-9_]*"
        if type(self.entry_point_value) is not str or len(self.entry_point_value) > 400 or not re.fullmatch(
            rf"{part}(?:\.{part})*:{part}(?:\.{part})*", self.entry_point_value
        ):
            raise AuthorityError("entry point must be module:attribute without extras")
        sha256_identity(self.wheel_sha256)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_bytes(asdict(self))).hexdigest()
