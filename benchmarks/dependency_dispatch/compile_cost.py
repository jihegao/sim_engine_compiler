#!/usr/bin/env python3
"""Paired old/new compiler cost, independently reloaded IR and revision evidence."""
import argparse
import copy
import io
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

from sim_engine_compiler.compiler.layout import compile_core, lineage, revision_impact
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR

ROOT=Path(__file__).resolve().parents[2]
BASELINE='7b110db7f69e36048cfd95ac9d5182ffa9eea7cc'


def checked(command, **kwargs):
    return subprocess.run([str(v) for v in command], check=True, capture_output=True, **kwargs)


def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


PYTHON_PROBE='''import json,sys,time
sys.path.insert(0,sys.argv[1]+'/src')
from sim_engine_compiler.compiler.aircraft_support import compile_aircraft_support
inputs=json.load(open(sys.argv[2]));records=[]
for i in range(8):
 start=time.perf_counter_ns();plan=compile_aircraft_support(inputs,semantic_profile='event-time-v2');ns=time.perf_counter_ns()-start
 if i:records.append(ns)
json.dump(plan.to_dict(),open(sys.argv[3],'w'))
print(json.dumps(records))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if checked(['git','status','--porcelain','--untracked-files=no'],text=True,cwd=ROOT).stdout:
        raise RuntimeError('commit tracked source before measuring')
    report={'baseline_commit':BASELINE,'current_commit':checked(['git','rev-parse','HEAD'],text=True,cwd=ROOT).stdout.strip(),
            'warmups':1,'repeats':7,'profile':'event-time-v2','cases':[]}
    cases={'b1':ROOT/'tests/fixtures/synthetic/b1-daily-operations.json',
           'f35':ROOT/'tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json'}
    with tempfile.TemporaryDirectory(prefix='sim-compile-paired-') as tmp:
        tmp=Path(tmp);old=tmp/'old';old.mkdir()
        archive=checked(['git','archive',BASELINE],cwd=ROOT).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(old,filter='data')
        # Source-only baseline checkout; separate target avoids overwriting the current binary.
        for root in (old,ROOT):
            checked(['cargo','build','--locked','--release','--manifest-path',root/'rust/compiler/Cargo.toml','--bin','sim-engine-compiler-aot'],cwd=root)
        for name,source in cases.items():
            print('paired compile',name,flush=True)
            directory=out/name;directory.mkdir(exist_ok=True)
            row={'case':name,'python':{},'rust':{}}
            for label,root in (('old',old),('current',ROOT)):
                probe=checked([sys.executable,'-c',PYTHON_PROBE,root,source,directory/f'{label}-plan.json'],text=True,cwd=root)
                row['python'][label]=json.loads(probe.stdout)
            assert json.loads((directory/'old-plan.json').read_text())==json.loads((directory/'current-plan.json').read_text())
            for repeat in range(8):
                arms=[('old',old),('current',ROOT)]
                if repeat%2:arms.reverse()
                for label,root in arms:
                    start=time.perf_counter_ns()
                    result=checked([root/'rust/compiler/target/release/sim-engine-compiler-aot',source,tmp/'out.seplan',
                        '--json-output',tmp/'out.json','--semantic-profile','event-time-v2'],text=True,cwd=root)
                    wall=time.perf_counter_ns()-start
                    assert json.loads((tmp/'out.json').read_text())==json.loads((directory/'current-plan.json').read_text())
                    if repeat:row['rust'].setdefault(label,[]).append({'process_wall_ns':wall,'segments':json.loads(result.stdout)})
            inputs=json.loads(source.read_text());business=import_business_ir(inputs,semantic_profile='event-time-v2')
            core=lower_business(business);plan=compile_core(core)
            save(directory/'business.json',business.to_dict());save(directory/'core.json',core.to_dict())
            save(directory/'lineage.json',lineage(business,core,plan))
            steps={'canonical_to_business':lambda:import_business_ir(inputs,semantic_profile='event-time-v2'),
                   'business_to_core':lambda:lower_business(business), 'core_to_plan':lambda:compile_core(core),
                   'business_read_parse_validate':lambda:BusinessIR.from_dict(json.loads((directory/'business.json').read_text())),
                   'core_read_parse_validate':lambda:CoreIR.from_dict(json.loads((directory/'core.json').read_text()))}
            row['layer_timings_ns']={}
            for label,operation in steps.items():
                operation();records=[]
                for _ in range(7):
                    start=time.perf_counter_ns();operation();records.append(time.perf_counter_ns()-start)
                row['layer_timings_ns'][label]=records
            edited=copy.deepcopy(business.payload)
            activity=next(a for a in edited['sections']['support_activities']['collections']['activities'] if a['definition'].get('jobs'))
            job=activity['definition']['jobs'][0]
            job['durationMinutes']=int(job.get('durationMinutes') or job.get('duration_minutes') or 1)+3
            changed_business=BusinessIR.create(edited);changed_core=lower_business(changed_business)
            changed_plan=compile_core(changed_core)
            assert changed_plan.fingerprint!=plan.fingerprint
            save(directory/'edited-business.json',changed_business.to_dict())
            save(directory/'edited-core.json',changed_core.to_dict())
            save(directory/'edited-plan.json',changed_plan.to_dict())
            save(directory/'revision-impact.json',revision_impact(core,changed_core))
            row['python_median_ns']={k:statistics.median(v) for k,v in row['python'].items()}
            row['rust_median_process_ns']={k:statistics.median(r['process_wall_ns'] for r in v) for k,v in row['rust'].items()}
            report['cases'].append(row);save(out/'compile-cost.json',report)


if __name__=='__main__':main()
