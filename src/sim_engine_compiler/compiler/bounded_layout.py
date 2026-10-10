"""Symbol resolution for the opt-in versioned event IR (no case dispatch)."""
import copy
from sim_engine_compiler.ir.bounded import CORE, PLAN, Document, require


def compile_bounded(core, *, operations, backend='python-bounded-reference'):
    require(core.version == CORE, 'unsupported Core IR')
    p = core.payload
    require(p['operations'] == operations, 'unknown operation or incomplete contract')
    require(all(backend in op['backends'] for op in operations), 'backend capability gap')
    indexes = {}
    for table, rows in p['tables'].items():
        indexes[table] = {r['id']: i for i, r in enumerate(rows)}
        require(len(indexes[table]) == len(rows), 'duplicate Core symbol')
    def resolve(table, value):
        if isinstance(value, list):
            return [resolve(table, v) for v in value]
        if value is None:
            return None
        require(table in indexes and value in indexes[table], f'unresolved symbol: {table}/{value}')
        return indexes[table][value]
    tables, source_map = {}, []
    for table, rows in p['tables'].items():
        tables[table] = []
        for i, row in enumerate(rows):
            attrs = copy.deepcopy(row['attributes'])
            for field, ref in row['references'].items():
                attrs[field] = resolve(ref['table'], ref['value'])
            # Resource demands are a nested, typed symbolic operand list.
            for step in attrs.get('steps', []):
                step['demands'] = [[resolve('resources', d['resource']), d['quantity']] for d in step['demands']]
            tables[table].append({'id': row['id'], 'source_path': row['source_path'], **attrs})
            source_map.append({'symbol': f'{table}/{row["id"]}', 'source_path': row['source_path'],
                               'plan_path': f'/tables/{table}/{i}'})
    return Document.create(PLAN, {k: copy.deepcopy(v) for k, v in p.items() if k != 'tables'} |
                           {'tables': tables, 'core_fingerprint': core.fingerprint,
                            'source_map': source_map, 'backend': backend})
