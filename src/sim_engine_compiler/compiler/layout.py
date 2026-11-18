"""Resolve Core symbols and validate backend layout without domain dispatch."""
from __future__ import annotations

import copy
from dataclasses import fields
import math
from typing import get_type_hints, get_origin, get_args

from sim_engine_compiler.ir.layers import CoreIR, TABLE_IDS, ALL_TABLE_IDS, REFERENCES, reject
from sim_engine_compiler.ir import plan as schema
from sim_engine_compiler.ir.reliability import (
    ReliabilityComponentGroupSpec,
    ReliabilityComponentInstanceSpec,
)

TABLE_TYPES = dict(zip(TABLE_IDS, (schema.AircraftSpec, schema.MissionSpec, schema.ActivitySpec,
                                  schema.ResourceNodeSpec, schema.ComponentSpec,
                                  schema.PreventiveCycleSpec, schema.SupplyRouteSpec)))
TABLE_TYPES.update({
    'component_groups': ReliabilityComponentGroupSpec,
    'component_instances': ReliabilityComponentInstanceSpec,
})


def _typed(value, kind, path):
    origin = get_origin(kind)
    if origin is tuple:
        if not isinstance(value, (tuple, list)):
            reject(path, 'expected list')
        args = get_args(kind)
        if len(args) == 2 and args[1] is Ellipsis:
            for index, item in enumerate(value):
                _typed(item, args[0], f'{path}[{index}]')
        else:
            if len(value) != len(args):
                reject(path, 'invalid tuple length')
            for index, (item, item_type) in enumerate(zip(value, args)):
                _typed(item, item_type, f'{path}[{index}]')
    elif hasattr(kind, '__dataclass_fields__'):
        _record(value, kind, path)
    elif kind is float:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            reject(path, 'expected finite nonnegative number')
    elif kind is int:
        if type(value) is not int or not -1 <= value < 2**63:
            reject(path, 'expected signed integer')
    elif type(value) is not kind:
        reject(path, f'expected {kind.__name__}')


def _record(row, cls, path):
    if not isinstance(row, dict) or set(row) != {field.name for field in fields(cls)}:
        reject(path, 'unknown or missing layout attribute')
    for name, kind in get_type_hints(cls).items():
        _typed(row[name], kind, f'{path}.{name}')


def layout_core(core: CoreIR):
    """Produce a backend layout dictionary, usable also by the Core MLIR projection."""
    core.validate()
    tables = core.payload['tables']
    indexes = {name: {row['id']: i for i, row in enumerate(rows)} for name, rows in tables.items()}
    result = {'plan_version': schema.PLAN_VERSION,
              **copy.deepcopy(core.payload['contract']),
              'source_inputs_sha256': core.payload['source']['canonical_sha256']}
    for name, rows in tables.items():
        result[name] = []
        for index, row in enumerate(rows):
            attrs = {'index': index, **copy.deepcopy(row['attributes'])}
            for field, (target, optional) in REFERENCES.get(name, {}).items():
                value = row['references'][field]
                attrs[field] = [indexes[target][v] for v in value] if field == 'aircraft_indexes' else (-1 if optional and value is None else indexes[target][value])
            if name == 'activities':
                step_indexes = {step['id']: i for i, step in enumerate(row['steps'])}
                attrs['steps'] = [{'index': i, **copy.deepcopy(step['attributes']),
                                   'predecessors': [step_indexes[p] for p in step['predecessors']]}
                                  for i, step in enumerate(row['steps'])]
            _record(attrs, TABLE_TYPES[name], f'core.tables.{name}.{row["id"]}')
            result[name].append(attrs)
    _typed(result['duration_minutes'], int, 'core.contract.duration_minutes')
    _typed(result['natural_completion_enabled'], bool, 'core.contract.natural_completion_enabled')
    if result['duration_minutes'] <= 0:
        reject('core.contract.duration_minutes', 'duration must be positive')
    return result


def compile_core(core: CoreIR, *, backend='rust-runtime', resource_dispatch_index=None):
    if backend not in ('rust-runtime', 'python-reference') or any(backend not in op['backends'] for op in core.payload['operations']):
        reject('core.operations.backends', 'backend capability gap')
    value = layout_core(core)
    if resource_dispatch_index is not None:
        value['resource_dispatch_index'] = copy.deepcopy(resource_dispatch_index)
    return schema.ExecutionPlan.from_dict(value)


def lineage(business, core, plan):
    core.validate()
    return {'version': 'compiler-lineage/v2', 'business_fingerprint': business.fingerprint,
            'core_fingerprint': core.fingerprint, 'plan_fingerprint': plan.fingerprint,
            'canonical_sha256': core.payload['source']['canonical_sha256'],
            'symbols': {name: [{'id': row['id'], 'plan_path': f'{name}[{i}]',
                               'source_path': row['source_path']}
                              for i, row in enumerate(rows)] for name, rows in core.payload['tables'].items()}}


def revision_impact(before: CoreIR, after: CoreIR):
    """Report contract, content and layout changes as distinct revision effects."""
    before.validate()
    after.validate()
    changes = []
    for section, kind in (('contract', 'contract'), ('source', 'provenance')):
        old, new = before.payload[section], after.payload[section]
        for field in sorted(old.keys() | new.keys()):
            if old.get(field) != new.get(field):
                changes.append({'kind': kind, 'field': field, 'core_path': f'{section}.{field}',
                                'before': copy.deepcopy(old.get(field)), 'after': copy.deepcopy(new.get(field))})

    def compare(symbol, left, right, old_path, new_path, source):
        common = {'core_symbol': symbol, 'source_path': source,
                  'before_plan_path': old_path, 'after_plan_path': new_path}
        if left is None or right is None or left != right:
            changes.append({'kind': 'entity', **common})
        if left is not None and right is not None and old_path != new_path:
            changes.append({'kind': 'layout', **common})

    for table in [name for name in ALL_TABLE_IDS if name in before.payload['tables'] or name in after.payload['tables']]:
        old = {row['id']: (i, row) for i, row in enumerate(before.payload['tables'].get(table, []))}
        new = {row['id']: (i, row) for i, row in enumerate(after.payload['tables'].get(table, []))}
        for symbol in sorted(old.keys() | new.keys()):
            left, right = old.get(symbol), new.get(symbol)
            a, b = left[1] if left else None, right[1] if right else None
            old_path = f'{table}[{left[0]}]' if left else None
            new_path = f'{table}[{right[0]}]' if right else None
            compare(f'{table}/{symbol}', a, b, old_path, new_path, (b or a)['source_path'])
            if table == 'activities':
                old_steps = {s['id']: (i, s) for i, s in enumerate(a['steps'])} if a else {}
                new_steps = {s['id']: (i, s) for i, s in enumerate(b['steps'])} if b else {}
                for code in sorted(old_steps.keys() | new_steps.keys()):
                    x, y = old_steps.get(code), new_steps.get(code)
                    compare(f'{table}/{symbol}/steps/{code}', x[1] if x else None, y[1] if y else None,
                            f'{old_path}.steps[{x[0]}]' if x else None,
                            f'{new_path}.steps[{y[0]}]' if y else None,
                            (y or x)[1]['attributes']['source_path'])
    return {'version': 'compiler-impact/v2', 'before_core': before.fingerprint,
            'after_core': after.fingerprint, 'changes': changes}
