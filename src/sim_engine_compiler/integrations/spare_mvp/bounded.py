"""Canonical simulation_inputs import for the explicitly selected event profile.

This accepts authored canonical entities, never Project JSON, SIMLOX tables,
expected observations, native logs, or case names. Domain validation/lowering
is deliberately outside this integration.
"""
from sim_engine_compiler.ir.bounded import BUSINESS, PROFILE, Document, digest, require


def import_bounded_business(simulation_inputs):
    from sim_engine_compiler.domains.aircraft_support.bounded import validate_model
    require(simulation_inputs.get('schema_version') == 'aircraft-bounded-input/v1',
            'unsupported canonical schema')
    require(simulation_inputs.get('semantic_profile') == PROFILE, 'unsupported profile')
    require(set(simulation_inputs) == {'schema_version', 'semantic_profile', 'model'},
            'unknown canonical input fields')
    validate_model(simulation_inputs['model'])
    return Document.create(BUSINESS, {
        'semantic_profile': PROFILE,
        'canonical_sha256': digest(simulation_inputs),
        'model': simulation_inputs['model'],
        'source_map': {name: [{'id': row['id'], 'path': f'/model/{name}/{i}'}
                              for i, row in enumerate(simulation_inputs['model'][name])]
                       for name in ('aircraft', 'resources', 'processes', 'missions',
                                    'nodes', 'routes', 'external_events')},
    })
