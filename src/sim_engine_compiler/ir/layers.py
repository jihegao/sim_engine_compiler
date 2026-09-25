"""Versioned, independently reloadable Business and symbolic Core artifacts.

The compatibility operation registry is deliberately finite: editing an unknown
operation, phase, dependency or backend capability fails before Plan emission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import hashlib
import json
import math
from functools import lru_cache
from typing import Any

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.ir.plan import LEGACY_MINUTE_PHASES

BUSINESS_VERSION = 'aircraft-business-ir/v1'
CORE_VERSION = 'simulation-core-ir/v1'
PROFILES = ('legacy-minute-v1', 'event-time-v2')
# Stable symbolic references are resolved only by the layout pass. Ordered table
# membership preserves the compatibility RNG and source tie-breaking order.
TABLE_IDS = {
    'aircraft': 'tail_number', 'missions': 'mission_id', 'activities': 'activity_id',
    'resource_nodes': 'node_id', 'components': 'component_id',
    'preventive_cycles': 'source_path', 'supply_routes': 'route_id',
}
REFERENCES = {
    'activities': {'resource_node_index': ('resource_nodes', False),
                   'equipment_component_index': ('components', True)},
    'components': {'parent_index': ('components', True), 'aircraft_indexes': ('aircraft', False),
                   'repair_activity_index': ('activities', True)},
    'preventive_cycles': {'aircraft_index': ('aircraft', False), 'activity_index': ('activities', False)},
    'supply_routes': {'source_node_index': ('resource_nodes', False), 'destination_node_index': ('resource_nodes', False)},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def reject(path, reason, code='invalid_ir'):
    raise CompilationError(reason, code=code, source_path=path)


def require_keys(value, keys, path):
    if not isinstance(value, dict) or set(value) != set(keys):
        reject(path, f'expected fields {sorted(keys)}')


@lru_cache(maxsize=None)
def _schema_file(name):
    from importlib.resources import files
    return json.loads(files('sim_engine_compiler.ir').joinpath(name).read_text())


def operation_contracts():
    return copy.deepcopy(_schema_file('compatibility_operations.json'))


@dataclass(frozen=True)
class BusinessIR:
    payload: dict[str, Any]

    @classmethod
    def create(cls, payload):
        result = cls(copy.deepcopy(payload))
        result.validate()
        return result

    def validate(self):
        require_keys(self.payload, ('semantic_profile', 'source', 'sections'), 'business')
        if self.payload['semantic_profile'] not in PROFILES:
            reject('business.semantic_profile', 'unsupported time profile')
        require_keys(self.payload['source'], ('schema_version', 'canonical_sha256'), 'business.source')
        if self.payload['source']['schema_version'] != 'aircraft-support-v1-input-v1':
            reject('business.source.schema_version', 'unsupported canonical input schema')
        self.canonical_view()

    def canonical_view(self):
        sections = self.payload['sections']
        if not isinstance(sections, dict):
            reject('business.sections', 'expected section object')
        value = {}
        for section, content in sections.items():
            require_keys(content, ('properties', 'collections'), f'business.sections.{section}')
            properties = copy.deepcopy(content['properties'])
            if not isinstance(properties, dict) or not isinstance(content['collections'], dict):
                reject(f'business.sections.{section}', 'invalid section')
            for collection, entities in content['collections'].items():
                if collection in properties or not isinstance(entities, list):
                    reject(f'business.sections.{section}.{collection}', 'duplicate or invalid collection')
                seen = set()
                rows = []
                for index, entity in enumerate(entities):
                    path = f'business.sections.{section}.{collection}[{index}]'
                    require_keys(entity, ('business_id', 'source_path', 'definition'), path)
                    if not isinstance(entity['business_id'], str) or not entity['business_id'] or entity['business_id'] in seen:
                        reject(path, 'duplicate or missing stable business identity')
                    if not isinstance(entity['source_path'], str) or not isinstance(entity['definition'], dict):
                        reject(path, 'source path and entity definition required')
                    seen.add(entity['business_id'])
                    rows.append(copy.deepcopy(entity['definition']))
                properties[collection] = rows
            value[section] = properties
        # Scalar top-level canonical metadata/policies are a dedicated section,
        # not a hidden copy of the original input document.
        root = value.pop('$root', {})
        if set(root) & set(value):
            reject('business.sections.$root', 'duplicate canonical section')
        return {**root, **value}

    @property
    def fingerprint(self):
        return digest({'version': BUSINESS_VERSION, 'payload': self.payload})

    def to_dict(self):
        self.validate()
        return {'version': BUSINESS_VERSION, 'fingerprint': self.fingerprint, 'payload': copy.deepcopy(self.payload)}

    @classmethod
    def from_dict(cls, value):
        require_keys(value, ('version', 'fingerprint', 'payload'), 'business')
        if value['version'] != BUSINESS_VERSION:
            reject('business.version', 'unsupported Business IR version')
        result = cls.create(value['payload'])
        if result.fingerprint != value['fingerprint']:
            reject('business.fingerprint', 'Business IR checksum mismatch')
        return result


@dataclass(frozen=True)
class CoreIR:
    payload: dict[str, Any]

    @classmethod
    def create(cls, payload):
        result = cls(copy.deepcopy(payload))
        result.validate()
        return result

    def validate(self):
        require_keys(self.payload, ('source', 'contract', 'operations', 'tables'), 'core')
        source = self.payload['source']
        require_keys(source, ('business_fingerprint', 'canonical_sha256', 'origin_canonical_sha256'), 'core.source')
        for key, value in source.items():
            if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                reject(f'core.source.{key}', 'expected SHA-256')
        contract = self.payload['contract']
        require_keys(contract, ('domain', 'semantic_profile', 'work_policy', 'rng_profile', 'duration_minutes', 'natural_completion_enabled', 'phases', 'unsupported_features'), 'core.contract')
        if contract['domain'] != 'aircraft-support' or contract['semantic_profile'] not in PROFILES or contract['work_policy'] != 'stable-topological-serial' or contract['rng_profile'] != 'legacy-sequential-v1' or contract['phases'] != list(LEGACY_MINUTE_PHASES) or contract['unsupported_features']:
            reject('core.contract', 'unsupported compatibility contract')
        if type(contract['duration_minutes']) is not int or not 0 < contract['duration_minutes'] < 2**63 or type(contract['natural_completion_enabled']) is not bool:
            reject('core.contract', 'invalid duration or termination policy type')
        if self.payload['operations'] != operation_contracts():
            reject('core.operations', 'unknown operation or incomplete read/write/time/backend contract', 'unsupported_operation')
        tables = self.payload['tables']
        require_keys(tables, TABLE_IDS, 'core.tables')
        ids = {}
        for name, rows in tables.items():
            if not isinstance(rows, list):
                reject(f'core.tables.{name}', 'expected ordered table')
            ids[name] = set()
            for row in rows:
                require_keys(row, ('id', 'attributes', 'references', 'steps'), f'core.tables.{name}')
                if not isinstance(row['id'], str) or not row['id'] or row['id'] in ids[name]:
                    reject(f'core.tables.{name}', 'duplicate or missing symbol')
                ids[name].add(row['id'])
                validate_attributes(row['attributes'], name, f'core.tables.{name}.{row["id"]}.attributes')
                if not isinstance(row['attributes'], dict) or row['attributes'].get(TABLE_IDS[name]) != row['id']:
                    reject(f'core.tables.{name}', 'symbol and business identity disagree')
                require_keys(row['references'], REFERENCES.get(name, {}), f'core.tables.{name}.{row["id"]}.references')
                if name != 'activities' and row['steps']:
                    reject(f'core.tables.{name}', 'unexpected nested work steps')
        for name, rows in tables.items():
            for row in rows:
                for field, (target, optional) in REFERENCES.get(name, {}).items():
                    values = row['references'][field]
                    values = values if field == 'aircraft_indexes' else [values]
                    if not isinstance(values, list):
                        reject(f'core.tables.{name}.{row["id"]}.{field}', 'expected reference list')
                    for value in values:
                        if value is None and optional:
                            continue
                        if not isinstance(value, str) or value not in ids[target]:
                            reject(f'core.tables.{name}.{row["id"]}.{field}', f'unresolved {target} symbol {value!r}')
                if name == 'activities':
                    seen = set()
                    for step in row['steps']:
                        require_keys(step, ('id', 'attributes', 'predecessors', 'dependencies'), f'core.steps.{row["id"]}')
                        if not isinstance(step['id'], str) or step['id'] in seen or step['attributes'].get('code') != step['id']:
                            reject('core.steps', 'invalid step identity')
                        if not isinstance(step['predecessors'], list) or any(p not in seen for p in step['predecessors']):
                            reject('core.steps.predecessors', 'expected earlier step symbol; cycles and unknown predecessors are unsupported')
                        seen.add(step['id'])
                        validate_attributes(step['attributes'], 'steps', f'core.steps.{step["id"]}.attributes')
                        expected = step_dependencies(row, step, tables)
                        if step['dependencies'] != expected:
                            reject('core.steps.dependencies', 'incomplete resource/wakeup dependency contract')

    @property
    def fingerprint(self):
        return digest({'version': CORE_VERSION, 'payload': self.payload})

    def to_dict(self):
        self.validate()
        return {'version': CORE_VERSION, 'fingerprint': self.fingerprint, 'payload': copy.deepcopy(self.payload)}

    @classmethod
    def from_dict(cls, value):
        require_keys(value, ('version', 'fingerprint', 'payload'), 'core')
        if value['version'] != CORE_VERSION:
            reject('core.version', 'unsupported Core IR version')
        result = cls.create(value['payload'])
        if result.fingerprint != value['fingerprint']:
            reject('core.fingerprint', 'Core IR checksum mismatch')
        return result


def step_dependencies(activity, step, tables):
    node = activity['references']['resource_node_index']
    products = {p for p, _ in step['attributes']['spares']}
    if activity['attributes']['kind'] == 'repair':
        products.update(c['attributes']['product_id'] for c in tables['components']
                        if c['references']['repair_activity_index'] == activity['id'] and c['attributes']['product_type'] == 'LRU' and c['attributes']['product_id'])
    capacity_sources = {kind: sorted({node, *(r['references']['source_node_index'] for r in tables['supply_routes'] if r['references']['destination_node_index'] == node and r['attributes']['product_id'] in ('', '*', kind))}) for kind in ('personnel', 'equipment')}
    return {'capacity_node': node, 'capacity_sources': capacity_sources, 'inventory_products': sorted(products),
            'supply_routes': [r['id'] for r in tables['supply_routes']
                              if r['references']['destination_node_index'] == node and
                              (not r['attributes']['product_id'] or r['attributes']['product_id'] in products)],
            'dynamic_state': ['job_reservations', 'active_shipment', 'job_step', 'job_status'],
            'wakeups': ['resource_change', 'job_change', 'canonical_dispatch_phase']}


def core_from_records(*, business, **records):
    """Seal domain lowering's temporary records as symbol-based Core IR.

    No ExecutionPlan is created and no original-input object survives this pass.
    Mission templates and distributions have already been lowered into instances
    and compatibility rates; layout below can be run from this artifact alone.
    """
    tables = {}
    symbol_lists = {name: [getattr(row, field) for row in records[name]] for name, field in TABLE_IDS.items()}
    for name in TABLE_IDS:
        tables[name] = []
        for record in records.pop(name):
            attrs = asdict(record)
            attrs.pop('index')
            steps = attrs.pop('steps', [])
            refs = {}
            for field, (target, optional) in REFERENCES.get(name, {}).items():
                raw = attrs.pop(field)
                refs[field] = [symbol_lists[target][i] for i in raw] if field == 'aircraft_indexes' else (None if optional and raw < 0 else symbol_lists[target][raw])
            codes = [step['code'] for step in steps]
            core_steps = []
            for step in steps:
                step.pop('index')
                predecessors = [codes[i] for i in step.pop('predecessors')]
                core_steps.append({'id': step['code'], 'attributes': step, 'predecessors': predecessors, 'dependencies': {}})
            tables[name].append({'id': attrs[TABLE_IDS[name]], 'attributes': attrs, 'references': refs, 'steps': core_steps})
    # JSON normalization makes tuple/list transport identical in both backends.
    tables = json.loads(json.dumps(tables))
    for activity in tables['activities']:
        for step in activity['steps']:
            step['dependencies'] = step_dependencies(activity, step, tables)
    canonical = business.canonical_view()
    return CoreIR.create({'source': {'business_fingerprint': business.fingerprint,
                                    'canonical_sha256': digest(canonical),
                                    'origin_canonical_sha256': business.payload['source']['canonical_sha256']},
                          'contract': json.loads(json.dumps(records)),
                          'operations': operation_contracts(), 'tables': tables})


def validate_attributes(value, table, path):
    schemas = _schema_file('attribute_types.json')
    schema = schemas[table]
    require_keys(value, schema, path)
    def check(item, kind, location):
        if isinstance(kind, list):
            if not isinstance(item, list):
                reject(location, 'expected list')
            if kind[0] == 'tuple':
                if len(item) != len(kind)-1:
                    reject(location, 'wrong tuple size')
                for i, (entry, entry_type) in enumerate(zip(item, kind[1:])):
                    check(entry, entry_type, f'{location}[{i}]')
            else:
                for i, entry in enumerate(item):
                    check(entry, kind[1], f'{location}[{i}]')
        elif kind == 'int':
            if type(item) is not int or not 0 <= item < 2**63:
                reject(location, 'expected nonnegative integer')
        elif kind == 'float':
            if type(item) not in (float, int) or not math.isfinite(item) or item < 0:
                reject(location, 'expected finite nonnegative number')
        elif (kind == 'str' and not isinstance(item, str)) or (kind == 'bool' and type(item) is not bool):
            reject(location, f'expected {kind}')
    for key, kind in schema.items():
        check(value[key], kind, f'{path}.{key}')
