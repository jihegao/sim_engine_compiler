"""Versioned, immutable documents for the opt-in bounded event profile.

These are a separate contract from the minute-compatible aircraft Plan. Loading
one never silently selects a different backend or time/RNG policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math


PROFILE = 'aircraft-bounded-events/v1'
TICKS_PER_HOUR = 3_600_000_000  # integer microseconds; no minute rounding


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def ticks(hours):
    require(type(hours) in (int, float) and math.isfinite(hours) and hours >= 0,
            'time must be finite, nonnegative hours')
    value = round(hours * TICKS_PER_HOUR)
    require(value < 2**63, 'time outside signed 64-bit range')
    return value


@dataclass(frozen=True)
class Document:
    version: str
    data: bytes

    @classmethod
    def create(cls, version, payload):
        return cls(version, encoded(payload))

    @property
    def payload(self):
        return json.loads(self.data)

    @property
    def fingerprint(self):
        return digest({'version': self.version, 'payload': self.payload})

    def to_dict(self):
        return {'version': self.version, 'fingerprint': self.fingerprint,
                'payload': self.payload}

    @classmethod
    def from_dict(cls, value, version):
        require(set(value) == {'version', 'fingerprint', 'payload'}, 'invalid IR envelope')
        require(value['version'] == version, 'unsupported IR version')
        result = cls.create(version, value['payload'])
        require(value['fingerprint'] == result.fingerprint, 'IR checksum mismatch')
        return result


BUSINESS = 'aircraft-bounded-business/v1'
CORE = 'aircraft-bounded-core/v1'
PLAN = 'aircraft-bounded-plan/v1'
