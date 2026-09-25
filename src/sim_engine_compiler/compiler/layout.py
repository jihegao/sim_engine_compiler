"""Resolve Core symbols and validate backend layout without domain dispatch."""
from __future__ import annotations

import copy
from dataclasses import fields
import math
from typing import get_type_hints, get_origin, get_args

from sim_engine_compiler.ir.layers import CoreIR, TABLE_IDS, REFERENCES, reject
from sim_engine_compiler.ir import plan as schema

TABLE_TYPES = dict(zip(TABLE_IDS, (schema.AircraftSpec, schema.MissionSpec, schema.ActivitySpec,
                                  schema.ResourceNodeSpec, schema.ComponentSpec,
                                  schema.PreventiveCycleSpec, schema.SupplyRouteSpec)))


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
    return {'version': 'compiler-lineage/v1', 'business_fingerprint': business.fingerprint,
            'core_fingerprint': core.fingerprint, 'plan_fingerprint': plan.fingerprint,
            'canonical_sha256': core.payload['source']['canonical_sha256'],
            'symbols': {name: [{'id': row['id'], 'plan_path': f'{name}[{i}]',
                               'source_path': row['attributes'].get('source_path', f'aircraft.assets[{i}]')}
                              for i, row in enumerate(rows)] for name, rows in core.payload['tables'].items()}}


def revision_impact(before: CoreIR, after: CoreIR):
    """Trace changed stable Core symbols to source fields and both Plan layouts."""
    before.validate()
    after.validate()
    changes = []
    for table in TABLE_IDS:
        old = {row['id']: (i,row) for i,row in enumerate(before.payload['tables'][table])}
        new = {row['id']: (i,row) for i,row in enumerate(after.payload['tables'][table])}
        for symbol in sorted(old.keys() | new.keys()):
            left = old.get(symbol)
            right = new.get(symbol)
            if left and right and left[1] == right[1]:
                continue
            row = (right or left)[1]
            changes.append({'core_symbol': f'{table}/{symbol}',
                            'source_path': row['attributes'].get('source_path'),
                            'before_plan_path': f'{table}[{left[0]}]' if left else None,
                            'after_plan_path': f'{table}[{right[0]}]' if right else None})
            if table == 'activities':
                old_steps = {s['id']:(i,s) for i,s in enumerate(left[1]['steps'])} if left else {}
                new_steps = {s['id']:(i,s) for i,s in enumerate(right[1]['steps'])} if right else {}
                for code in sorted(old_steps.keys() | new_steps.keys()):
                    a,b = old_steps.get(code),new_steps.get(code)
                    if a and b and a[1] == b[1]:
                        continue
                    changes.append({'core_symbol':f'{table}/{symbol}/steps/{code}',
                                    'source_path':(b or a)[1]['attributes']['source_path'],
                                    'before_plan_path':f'{table}[{left[0]}].steps[{a[0]}]' if a else None,
                                    'after_plan_path':f'{table}[{right[0]}].steps[{b[0]}]' if b else None})
    return {'version':'compiler-impact/v1','before_core':before.fingerprint,'after_core':after.fingerprint,'changes':changes}
