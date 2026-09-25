#!/usr/bin/env python3
"""Compile/reload independently persisted canonical, Business, Core and Plan stages."""
import argparse
import json
from pathlib import Path
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR, BUSINESS_VERSION, CORE_VERSION
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.compiler.layout import compile_core, lineage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--output-kind', choices=('business','core','plan'), default='plan')
    parser.add_argument('--semantic-profile', choices=('legacy-minute-v1','event-time-v2'), default='legacy-minute-v1')
    parser.add_argument('--artifacts-dir', type=Path)
    args = parser.parse_args()
    raw = json.loads(args.input.read_text())
    business = None
    if raw.get('version') == CORE_VERSION:
        if args.output_kind == 'business':
            parser.error('Core cannot reconstruct Business templates')
        core = CoreIR.from_dict(raw)
    else:
        business = BusinessIR.from_dict(raw) if raw.get('version') == BUSINESS_VERSION else import_business_ir(raw, semantic_profile=args.semantic_profile)
        core = lower_business(business)
    plan = compile_core(core)
    result = {'business': business.to_dict() if business else None, 'core': core.to_dict(), 'plan': plan.to_dict()}[args.output_kind]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    if args.artifacts_dir:
        args.artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {'core.json': core.to_dict(), 'plan.json': plan.to_dict()}
        if business:
            artifacts['business.json'] = business.to_dict()
            artifacts['lineage.json'] = lineage(business,core,plan)
        for name,value in artifacts.items():
            (args.artifacts_dir/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'business_fingerprint':core.payload['source']['business_fingerprint'], 'core_fingerprint':core.fingerprint,'plan_fingerprint':plan.fingerprint}))


if __name__=='__main__': main()
