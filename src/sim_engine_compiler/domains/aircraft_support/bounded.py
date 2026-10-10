"""Restricted aircraft event profile: domain validation and symbolic lowering.

No native RNG is implemented here. External fault/damaged-arrival drivers are
explicit inputs, with a distinct acceptance scope from a stochastic model.
"""
from __future__ import annotations
import copy
import math
from sim_engine_compiler.ir.bounded import (BUSINESS, CORE, PLAN, PROFILE,
    Document, digest, require, ticks)


TABLES = ('aircraft', 'resources', 'processes', 'missions', 'nodes', 'routes', 'external_events')
OPS = {
    'notify': (10, ['aircraft', 'missions'], ['aircraft', 'missions', 'jobs']),
    'dispatch': (20, ['aircraft', 'missions', 'jobs', 'resources'], ['aircraft', 'missions', 'jobs', 'resources']),
    'work_done': (0, ['jobs'], ['jobs', 'aircraft', 'resources']),
    'early_deadline': (30, ['missions', 'resources', 'aircraft'], ['missions', 'aircraft', 'jobs', 'resources']),
    'deadline': (40, ['missions'], ['missions', 'aircraft', 'jobs', 'resources']),
    'mission_return': (0, ['missions'], ['missions', 'aircraft', 'jobs']),
    'turnround_done': (0, ['aircraft'], ['aircraft']),
    'fault': (5, ['aircraft'], ['aircraft', 'missions']),
    'damaged_arrival': (5, ['aircraft', 'missions'], ['aircraft', 'missions', 'jobs']),
    'repair_done': (0, ['aircraft'], ['aircraft']),
    'pm_due': (5, ['aircraft'], ['aircraft']),
    'pm_done': (0, ['aircraft'], ['aircraft']),
    'remove_done': (0, ['aircraft'], ['aircraft', 'items']),
    'item_repair_start': (0, ['items'], ['items']),
    'item_repair_done': (0, ['items'], ['items', 'stock', 'backorders']),
    'supply_arrival': (0, ['items', 'backorders'], ['items', 'backorders', 'aircraft']),
    'fit_done': (0, ['items', 'aircraft'], ['items', 'aircraft']),
    'in_transfer': (0, ['stock'], ['items', 'stock']),
    'set_repair_duration': (0, ['aircraft'], ['parameters']),
}


def operation_contracts():
    return [{'name': name, 'version': 1, 'classification': 'restricted-aircraft-profile',
             'phase': phase, 'reads': reads, 'writes': writes,
             'inputs': 'validated dense entity index or runtime owner token',
             'outputs': 'trace records, updated RunState and bounded calendar events',
             'preconditions': 'see docs/aircraft-bounded-events.md operation table',
             'time': 'integer-microsecond calendar; completion before dispatch before deadline',
             'random_requests': [], 'backends': ['python-bounded-reference'],
             'limits': {'event_budget': 100000, 'entities_per_table': 1000}}
            for name, (phase, reads, writes) in OPS.items()]


def keys(value, expected, context):
    require(isinstance(value, dict) and set(value) == set(expected.split()),
            f'{context}: missing/unknown fields')


def number(value, context, positive=False, integer=False):
    require(type(value) in ((int,) if integer else (int, float)) and math.isfinite(value)
            and (value > 0 if positive else value >= 0), f'{context}: invalid number')


def validate_model(m):
    keys(m, 'horizon_hours report_interval_hours rng_profile aircraft resources processes missions nodes routes external_events', 'model')
    require(m['rng_profile'] in ('none', 'external-events/v1'), 'unsupported RNG profile')
    for name in ('horizon_hours', 'report_interval_hours'):
        number(m[name], name, positive=True)
        require(ticks(m[name]) > 0, 'time below microsecond precision')
    require(ticks(m['horizon_hours']) % ticks(m['report_interval_hours']) == 0,
            'horizon must contain whole report intervals')
    require(ticks(m['horizon_hours']) // ticks(m['report_interval_hours']) <= 10000, 'report budget exceeded')
    ids = {}
    for table in TABLES:
        rows = m[table]
        require(isinstance(rows, list) and len(rows) <= 1000, f'{table}: invalid table size')
        require(all(isinstance(r, dict) and isinstance(r.get('id'), str) and r['id'] for r in rows),
                f'{table}: nonempty stable id required')
        ids[table] = {r['id'] for r in rows}
        require(len(ids[table]) == len(rows), f'{table}: duplicate id')
    require(m['aircraft'] and m['missions'], 'at least one aircraft and mission required')
    def ref(table, value, optional=False):
        require((value is None and optional) or (type(value) is str and value in ids[table]), f'unresolved {table} reference: {value}')
    all_items = []
    for r in m['resources']:
        keys(r, 'id capacity', 'resource')
        number(r['capacity'], 'resource capacity', integer=True)
    for n in m['nodes']:
        keys(n, 'id items', 'stock node')
        require(isinstance(n['items'], list) and all(type(i) is str and i for i in n['items']), 'invalid stock items')
        all_items.extend(n['items'])
    for p in m['processes']:
        keys(p, 'id scalar_hours steps', 'process')
        number(p['scalar_hours'], 'process scalar duration')
        require(isinstance(p['steps'], list) and len(p['steps']) <= 1000, 'invalid process steps')
        seen = set()
        for s in p['steps']:
            keys(s, 'id duration_hours demands', 'work step')
            require(type(s['id']) is str and s['id'] and s['id'] not in seen, 'duplicate/missing step id')
            seen.add(s['id'])
            number(s['duration_hours'], 'work duration')
            require(isinstance(s['demands'], dict), 'invalid work demand')
            for rid, q in s['demands'].items():
                ref('resources', rid)
                number(q, 'resource quantity', positive=True, integer=True)
    for a in m['aircraft']:
        keys(a, 'id type turnround_hours repair_mode repair_hours remove_hours fit_hours item_repair_hours stock_node repair_node installed_item pm', 'aircraft')
        require(type(a['type']) is str and a['type'], 'aircraft type required')
        require(a['repair_mode'] in ('none', 'direct', 'replacement'), 'unsupported repair mode')
        for k in ('turnround_hours', 'repair_hours', 'remove_hours', 'fit_hours', 'item_repair_hours'):
            number(a[k], k)
        ref('nodes', a['stock_node'], optional=True)
        ref('nodes', a['repair_node'], optional=True)
        if a['repair_mode'] == 'replacement':
            require(a['stock_node'] is not None and a['repair_node'] is not None and
                    type(a['installed_item']) is str and a['installed_item'], 'replacement needs installed item and stock/repair nodes')
        else:
            require(a['installed_item'] is None, 'installed item requires replacement mode')
        if a['installed_item'] is not None:
            all_items.append(a['installed_item'])
        if a['pm'] is not None:
            keys(a['pm'], 'id clock interval_hours duration_hours', 'PM')
            require(type(a['pm']['id']) is str and a['pm']['id'], 'PM identity required')
            require(a['pm']['clock'] in ('calendar', 'flight'), 'unsupported PM clock')
            for key in ('interval_hours', 'duration_hours'):
                number(a['pm'][key], key, positive=True)
                require(ticks(a['pm'][key]) > 0, f'PM {key}: time below microsecond precision')
    types = {a['type'] for a in m['aircraft']}
    for miss in m['missions']:
        keys(miss, 'id start_hours notice_hours duration_hours delay_hours priority requirements process depends_on', 'mission')
        for k in ('start_hours', 'notice_hours', 'duration_hours', 'delay_hours'):
            number(miss[k], k, positive=k == 'duration_hours')
        require(ticks(miss['duration_hours']) > 0, 'mission duration: time below microsecond precision')
        require(miss['notice_hours'] <= miss['start_hours'] < m['horizon_hours'], 'invalid mission notice/start')
        require(ticks(miss['start_hours']) < ticks(m['horizon_hours']), 'mission start must precede horizon after time quantization')
        number(miss['priority'], 'mission priority', integer=True)
        require(isinstance(miss['requirements'], dict) and miss['requirements'], 'empty formation')
        for t, q in miss['requirements'].items():
            require(t in types, f'unknown aircraft type: {t}')
            number(q, 'formation quantity', positive=True, integer=True)
        ref('processes', miss['process'])
        require(isinstance(miss['depends_on'], list), 'invalid dependencies')
        for other in miss['depends_on']:
            ref('missions', other)
    # The declared 1,000-row bound must not depend on Python recursion depth
    # or input row order. Count each listed dependency, including repeated ones.
    remaining = {v['id']: len(v['depends_on']) for v in m['missions']}
    dependents = {mid: [] for mid in remaining}
    for mission in m['missions']:
        for other in mission['depends_on']:
            dependents[other].append(mission['id'])
    ready = [mid for mid, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        mid = ready.pop()
        visited += 1
        for successor in dependents[mid]:
            remaining[successor] -= 1
            if remaining[successor] == 0:
                ready.append(successor)
    require(visited == len(remaining), 'cyclic mission dependencies')
    route_pairs = set()
    for route in m['routes']:
        keys(route, 'id source destination duration_hours', 'route')
        ref('nodes', route['source']); ref('nodes', route['destination'])
        pair = (route['source'], route['destination'])
        require(pair[0] != pair[1] and pair not in route_pairs, 'duplicate/self route')
        route_pairs.add(pair)
        number(route['duration_hours'], 'transport duration')
    for a in m['aircraft']:
        if a['repair_mode'] == 'replacement' and a['stock_node'] != a['repair_node']:
            require((a['stock_node'], a['repair_node']) in route_pairs and
                    (a['repair_node'], a['stock_node']) in route_pairs, 'replacement requires both transport routes')
    for e in m['external_events']:
        keys(e, 'id time_hours operation aircraft node item value_hours', 'external driver')
        number(e['time_hours'], 'driver time')
        require(e['time_hours'] <= m['horizon_hours'], 'driver beyond horizon')
        require(e['operation'] in ('fault', 'damaged_arrival', 'in_transfer', 'set_repair_duration'), 'unsupported external operation')
        if e['operation'] == 'in_transfer':
            ref('nodes', e['node'])
            require(e['aircraft'] is None and type(e['item']) is str and e['item'], 'invalid IN transfer')
            all_items.append(e['item'])
        else:
            ref('aircraft', e['aircraft'])
            require(e['node'] is None and e['item'] is None, 'unexpected driver fields')
            a = next(a for a in m['aircraft'] if a['id'] == e['aircraft'])
            require(a['repair_mode'] != 'none', 'fault/parameter driver requires repair policy')
            if e['operation'] in ('set_repair_duration', 'damaged_arrival'):
                require(a['repair_mode'] == 'direct', 'driver requires direct system repair')
            if e['operation'] in ('fault', 'damaged_arrival'):
                require(m['rng_profile'] == 'external-events/v1', 'faults require explicit external-event scope')
        number(e['value_hours'], 'driver parameter')
        require(e['operation'] == 'set_repair_duration' or e['value_hours'] == 0, 'unused driver value must be zero')
    require(len(set(all_items)) == len(all_items), 'physical item identity reused')
    return m


def lower_bounded(business):
    require(business.version == BUSINESS, 'unsupported Business IR')
    payload = business.payload
    require(set(payload) == {'semantic_profile', 'canonical_sha256', 'model', 'source_map'}, 'invalid Business IR fields')
    require(payload['semantic_profile'] == PROFILE, 'unsupported profile')
    model = validate_model(payload['model'])
    canonical = {'schema_version': 'aircraft-bounded-input/v1', 'semantic_profile': PROFILE, 'model': model}
    require(payload['canonical_sha256'] == digest(canonical), 'canonical identity mismatch')
    expected_map = {name: [{'id': row['id'], 'path': f'/model/{name}/{i}'}
                           for i, row in enumerate(model[name])] for name in TABLES}
    require(payload['source_map'] == expected_map, 'Business source mapping mismatch')
    def convert(value):
        if isinstance(value, list):
            return [convert(v) for v in value]
        if isinstance(value, dict):
            return {(k[:-6] + '_ticks' if k.endswith('_hours') else k):
                    ticks(v) if k.endswith('_hours') else convert(v) for k, v in value.items()}
        return value
    tables = {}
    for name in TABLES:
        tables[name] = []
        for i, record in enumerate(model[name]):
            attrs = convert(copy.deepcopy(record))
            sid = attrs.pop('id')
            refs = {}
            fields = {'aircraft': {'stock_node': 'nodes', 'repair_node': 'nodes'},
                      'missions': {'process': 'processes', 'depends_on': 'missions'},
                      'routes': {'source': 'nodes', 'destination': 'nodes'},
                      'external_events': {'aircraft': 'aircraft', 'node': 'nodes'}}.get(name, {})
            for field, target in fields.items():
                refs[field] = {'table': target, 'value': attrs.pop(field)}
            if name == 'processes':
                if not attrs['steps']:
                    attrs['steps'] = [{'id': sid + ':scalar', 'duration_ticks': attrs['scalar_ticks'], 'demands': {}}]
                for step in attrs['steps']:
                    step['demands'] = [{'resource': r, 'quantity': q} for r, q in sorted(step['demands'].items())]
            tables[name].append({'id': sid, 'attributes': attrs, 'references': refs,
                                 'source_path': f'/model/{name}/{i}'})
    return Document.create(CORE, {'semantic_profile': PROFILE, 'business_fingerprint': business.fingerprint,
        'canonical_sha256': payload['canonical_sha256'], 'rng_profile': model['rng_profile'],
        'horizon_ticks': ticks(model['horizon_hours']), 'report_interval_ticks': ticks(model['report_interval_hours']),
        'operations': operation_contracts(), 'tables': tables})


def validate_plan(plan):
    require(plan.version == PLAN, 'unsupported Plan version')
    p = plan.payload
    require(set(p) == {'semantic_profile', 'business_fingerprint', 'canonical_sha256', 'rng_profile',
                       'horizon_ticks', 'report_interval_ticks', 'operations', 'tables',
                       'core_fingerprint', 'source_map', 'backend'}, 'invalid Plan fields')
    for field in ('business_fingerprint', 'canonical_sha256', 'core_fingerprint'):
        require(type(p[field]) is str and len(p[field]) == 64 and all(c in '0123456789abcdef' for c in p[field]),
                'invalid Plan lineage fingerprint')
    for field in ('horizon_ticks', 'report_interval_ticks'):
        require(type(p[field]) is int and 0 < p[field] < 2**63, 'invalid Plan clock')
    require(p.get('semantic_profile') == PROFILE and p.get('backend') == 'python-bounded-reference',
            'unsupported profile/backend')
    require(p.get('operations') == operation_contracts(), 'unknown/incomplete operation contract')
    require(set(p.get('tables', {})) == set(TABLES), 'missing plan tables')
    expected_map = [{'symbol': f'{name}/{row["id"]}', 'source_path': f'/model/{name}/{i}',
                     'plan_path': f'/tables/{name}/{i}'}
                    for name in sorted(TABLES) for i, row in enumerate(p['tables'][name])]
    require(p['source_map'] == expected_map, 'Plan source mapping mismatch')
    # Reconstruct only the canonical domain entities to reuse strict type/unit and
    # reference validation on independently deserialized plans. No source model
    # or expected output is needed by a loaded Plan.
    from sim_engine_compiler.ir.bounded import TICKS_PER_HOUR
    def reverse(value):
        if isinstance(value, list):
            return [reverse(v) for v in value]
        if isinstance(value, dict):
            result = {}
            for k, v in value.items():
                if k.endswith('_ticks'):
                    require(type(v) is int and 0 <= v < 2**63, 'invalid integer tick value')
                    result[k[:-6] + '_hours'] = v / TICKS_PER_HOUR
                else:
                    result[k] = reverse(v)
            return result
        return value
    m = {name: [] for name in TABLES}
    def symbol(table, i):
        if i is None:
            return None
        require(type(i) is int and 0 <= i < len(p['tables'][table]), 'invalid dense reference')
        return p['tables'][table][i]['id']
    for table in TABLES:
        for row in p['tables'][table]:
            attrs = reverse(row)
            source_path = attrs.pop('source_path')
            require(source_path == f'/model/{table}/{len(m[table])}', 'table source path mismatch')
            refs = {'aircraft': {'stock_node': 'nodes', 'repair_node': 'nodes'},
                    'missions': {'process': 'processes', 'depends_on': 'missions'},
                    'routes': {'source': 'nodes', 'destination': 'nodes'},
                    'external_events': {'aircraft': 'aircraft', 'node': 'nodes'}}.get(table, {})
            for field, target in refs.items():
                v = attrs[field]
                attrs[field] = [symbol(target, i) for i in v] if isinstance(v, list) else symbol(target, v)
            if table == 'processes':
                for step in attrs['steps']:
                    demands = step['demands']
                    require(len({r for r, q in demands}) == len(demands), 'duplicate demand resource')
                    step['demands'] = {symbol('resources', r): q for r, q in demands}
            m[table].append(attrs)
    m.update(horizon_hours=p['horizon_ticks'] / TICKS_PER_HOUR,
             report_interval_hours=p['report_interval_ticks'] / TICKS_PER_HOUR, rng_profile=p['rng_profile'])
    validate_model(m)
    return p
