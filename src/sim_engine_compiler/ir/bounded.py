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

# Operand types belong to this fixed, opt-in IR contract. They are checked
# before layout so a reference cannot alias an equal dense index in another
# table. Domain behavior and policy validation remain in the domain lowering.
CORE_ATTRIBUTES = {
    'aircraft': 'type turnround_ticks repair_mode repair_ticks remove_ticks fit_ticks item_repair_ticks installed_item pm',
    'resources': 'capacity',
    'processes': 'scalar_ticks steps',
    'missions': 'start_ticks notice_ticks duration_ticks delay_ticks priority requirements',
    'nodes': 'items',
    'routes': 'duration_ticks',
    'external_events': 'time_ticks operation item value_ticks',
}
CORE_REFERENCES = {
    'aircraft': {'stock_node': ('nodes', 'optional'), 'repair_node': ('nodes', 'optional')},
    'missions': {'process': ('processes', 'single'), 'depends_on': ('missions', 'list')},
    'routes': {'source': ('nodes', 'single'), 'destination': ('nodes', 'single')},
    'external_events': {'aircraft': ('aircraft', 'optional'), 'node': ('nodes', 'optional')},
}


def validate_core(core):
    """Validate bounded Core structure and typed operands before resolution."""
    require(core.version == CORE, 'unsupported Core IR')
    p = core.payload

    def fields(value, expected, context):
        require(type(value) is dict and set(value) == set(expected),
                f'{context}: missing/unknown fields')

    def symbol(value, context, optional=False):
        require((optional and value is None) or (type(value) is str and bool(value)),
                f'{context}: invalid symbol')

    def integer(value, context, positive=False):
        require(type(value) is int and (value > 0 if positive else value >= 0),
                f'{context}: invalid integer operand')

    def time(value, context, positive=False):
        integer(value, context, positive)
        require(value < 2**63, f'{context}: time outside signed 64-bit range')

    fields(p, ('semantic_profile', 'business_fingerprint', 'canonical_sha256', 'rng_profile',
               'horizon_ticks', 'report_interval_ticks', 'operations', 'tables'), 'Core')
    require(p['semantic_profile'] == PROFILE, 'unsupported Core profile')
    for key in ('business_fingerprint', 'canonical_sha256'):
        value = p[key]
        require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
                'invalid Core lineage fingerprint')
    require(p['rng_profile'] in ('none', 'external-events/v1'), 'unsupported Core RNG profile')
    for key in ('horizon_ticks', 'report_interval_ticks'):
        time(p[key], key, positive=True)
    require(type(p['operations']) is list, 'invalid Core operations')
    fields(p['tables'], CORE_ATTRIBUTES, 'Core tables')
    symbols = {}
    for table, rows in p['tables'].items():
        require(type(rows) is list and len(rows) <= 1000, f'{table}: invalid Core table size')
        symbols[table] = set()
        for index, row in enumerate(rows):
            fields(row, ('id', 'attributes', 'references', 'source_path'), f'{table} Core row')
            symbol(row['id'], table)
            require(row['id'] not in symbols[table], 'duplicate Core symbol')
            symbols[table].add(row['id'])
            require(row['source_path'] == f'/model/{table}/{index}', 'Core source path mismatch')
            fields(row['attributes'], CORE_ATTRIBUTES[table].split(), f'{table} Core attributes')
            fields(row['references'], CORE_REFERENCES.get(table, {}), f'{table} Core references')

    def reference(table, value, context):
        symbol(value, context)
        require(value in symbols[table], f'unresolved symbol: {table}/{value}')

    for table, rows in p['tables'].items():
        for row in rows:
            for key, (target, shape) in CORE_REFERENCES.get(table, {}).items():
                operand = row['references'][key]
                fields(operand, ('table', 'value'), f'{table}.{key} reference')
                require(operand['table'] == target, f'{table}.{key}: invalid reference table; expected {target}')
                value = operand['value']
                if shape == 'list':
                    require(type(value) is list, f'{table}.{key}: reference list required')
                    for item in value:
                        reference(target, item, key)
                elif value is not None or shape != 'optional':
                    reference(target, value, key)
            attrs = row['attributes']
            for key, value in attrs.items():
                if key.endswith('_ticks'):
                    time(value, key, positive=table == 'missions' and key == 'duration_ticks')
            if table == 'aircraft':
                symbol(attrs['type'], 'aircraft type')
                symbol(attrs['repair_mode'], 'repair mode')
                symbol(attrs['installed_item'], 'installed item', optional=True)
                pm = attrs['pm']
                if pm is not None:
                    fields(pm, ('id', 'clock', 'interval_ticks', 'duration_ticks'), 'Core PM')
                    symbol(pm['id'], 'PM id'); symbol(pm['clock'], 'PM clock')
                    time(pm['interval_ticks'], 'PM interval', positive=True)
                    time(pm['duration_ticks'], 'PM duration', positive=True)
            elif table == 'resources':
                integer(attrs['capacity'], 'resource capacity')
            elif table == 'processes':
                steps = attrs['steps']
                require(type(steps) is list and 0 < len(steps) <= 1000, 'invalid Core steps')
                step_ids = set()
                for step in steps:
                    fields(step, ('id', 'duration_ticks', 'demands'), 'Core step')
                    symbol(step['id'], 'step id')
                    require(step['id'] not in step_ids, 'duplicate Core step id')
                    step_ids.add(step['id'])
                    time(step['duration_ticks'], 'step duration')
                    require(type(step['demands']) is list, 'invalid Core demands')
                    demanded = set()
                    for demand in step['demands']:
                        fields(demand, ('resource', 'quantity'), 'Core demand')
                        reference('resources', demand['resource'], 'demand resource')
                        require(demand['resource'] not in demanded, 'duplicate demand resource')
                        demanded.add(demand['resource'])
                        integer(demand['quantity'], 'resource quantity', positive=True)
            elif table == 'missions':
                integer(attrs['priority'], 'mission priority')
                require(type(attrs['requirements']) is dict and attrs['requirements'], 'invalid formation operands')
                for kind, quantity in attrs['requirements'].items():
                    symbol(kind, 'formation type'); integer(quantity, 'formation quantity', positive=True)
            elif table == 'nodes':
                require(type(attrs['items']) is list, 'invalid Core stock items')
                for item in attrs['items']:
                    symbol(item, 'stock item')
            elif table == 'external_events':
                symbol(attrs['operation'], 'external operation')
                symbol(attrs['item'], 'external item', optional=True)
    return p
