"""Shared, explicitly non-authoritative inference contracts."""
from dataclasses import dataclass
from enum import Enum
from elpis.canonical_identity import content_digest


class Code(str, Enum):
    INVALID = 'INVALID'
    IDENTITY = 'IDENTITY'
    STALE = 'STALE'
    MISSING = 'MISSING'
    IO = 'IO'
    INTEGRITY = 'INTEGRITY'
    ENCODING = 'ENCODING'
    LIMIT = 'LIMIT'
    BUSY = 'BUSY'
    UNSUPPORTED = 'UNSUPPORTED'
    DEVICE = 'DEVICE'
    CLOSED = 'CLOSED'


class InferenceError(ValueError):
    def __init__(self, code: Code, detail: str):
        self.code = code
        super().__init__(f'{code.value}:{detail}')


def require(condition, code=Code.INVALID, detail='contract'):
    if not condition:
        raise InferenceError(code, detail)


def identity(kind, value):
    return content_digest('elpis.inference.' + kind + '.r0', value)


def integer(value, low=0, high=(1 << 63) - 1):
    require(type(value) is int and low <= value <= high, detail='integer range')
    return value


def digest_value(value):
    require(type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), detail='digest encoding')
    return value


class ProposalOnly:
    """Fixed properties, never caller-controlled admission flags."""
    __slots__ = ()
    semantic_authority = property(lambda self: False)
    admission_authority = property(lambda self: False)
    execution_authority = property(lambda self: False)
    mutation_authority = property(lambda self: False)
    runtime_admission = property(lambda self: False)


@dataclass(frozen=True)
class Bank:
    name: str
    model: str
    tokenizer: str
    scheme: str
    parameters: str
    layer: int
    rows: int
    dimension: int
    content: str
    representation: str

    def __post_init__(self):
        require(bool(self.name) and bool(self.model) and bool(self.tokenizer))
        integer(self.layer)
        integer(self.rows, 1)
        integer(self.dimension, 1)
        for d in (self.parameters, self.content, self.representation):
            digest_value(d)

    @property
    def digest(self):
        return identity('bank', self)


@dataclass(frozen=True)
class RowIdentity:
    bank: str
    row: int

    def __post_init__(self):
        digest_value(self.bank)
        integer(self.row)
