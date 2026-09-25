"""Import canonical Adapter data into Business IR; never interpret Project JSON."""
import copy
from sim_engine_compiler.ir.layers import BusinessIR, digest, reject
from sim_engine_compiler.domains.aircraft_support.validation import validate_canonical_work

COLLECTIONS = {'aircraft': ('assets',), 'equipment_tree': ('components',),
               'support_activities': ('activities',), 'support_network': ('nodes',),
               'mission_profile': ('basic_missions', 'composite_tasks', 'mission_calendar', 'mission_phases', 'airports')}


def import_business_ir(inputs, *, semantic_profile='legacy-minute-v1'):
    if not isinstance(inputs, dict) or inputs.get('schema_version') != 'aircraft-support-v1-input-v1':
        reject('schema_version', 'unsupported canonical input schema')
    validate_canonical_work(inputs)
    sections = {}
    root = {}
    for key, value in inputs.items():
        if not isinstance(value, dict):
            root[key] = copy.deepcopy(value)
            continue
        properties = copy.deepcopy(value)
        collections = {}
        for field in COLLECTIONS.get(key, ()):
            if field not in properties or not isinstance(properties[field], list):
                continue
            entities = []
            for index, definition in enumerate(properties.pop(field)):
                if not isinstance(definition, dict):
                    reject(f'{key}.{field}[{index}]', 'canonical entity must be an object')
                path = f'{key}.{field}[{index}]'
                identity = str(definition.get('id') or definition.get('tail_number') or definition.get('missionId') or path)
                entities.append({'business_id': identity, 'source_path': path, 'definition': definition})
            collections[field] = entities
        sections[key] = {'properties': properties, 'collections': collections}
    sections['$root'] = {'properties': root, 'collections': {}}
    return BusinessIR.create({'semantic_profile': semantic_profile,
                              'source': {'schema_version': inputs['schema_version'], 'canonical_sha256': digest(inputs)},
                              'sections': sections})
