#!/usr/bin/env python3
"""Three dispatch arms, exact results first, unprofiled timing separately.

Run required conformance first. Synthetic contention is explicitly synthetic;
F35 is the pinned canonical upstream snapshot. This never changes defaults.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.differential.test_dependency_dispatch import DependencyDispatchTests


def checked(command):
    return subprocess.run([str(v) for v in command], cwd=ROOT, check=True,
                          text=True, capture_output=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plugin-dir', type=Path, required=True)
    parser.add_argument('--mlir-opt', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error('at least three repeats required')
    if checked(['git', 'status', '--porcelain', '--untracked-files=no']).stdout:
        raise RuntimeError('commit tracked source before measuring')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    runtime = ROOT/'rust/runtime/target/release/sim-engine-runtime'
    batch = runtime.with_name('stage-c-benchmark')
    checked(['cargo', 'build', '--locked', '--release', '--manifest-path', ROOT/'rust/runtime/Cargo.toml'])
    identity = {
        'source_commit': checked(['git','rev-parse','HEAD']).stdout.strip(),
        'source_tree': checked(['git','rev-parse','HEAD^{tree}']).stdout.strip(),
        'platform': platform.platform(), 'python': sys.version,
        'rustc': checked(['rustc','--version']).stdout.strip(),
        'runtime_sha256': sha(runtime), 'batch_binary_sha256': sha(batch),
        'plugin_sha256': sha(args.plugin_dir/'SimResourceDispatchPass.so'),
        'cpu_count': os.cpu_count(), 'load_before': os.getloadavg(),
        'affinity': 'OS scheduled; no affinity or frequency control',
        'memory_measurement': 'not measured',
        'warmups_per_arm': 1, 'repeats': args.repeats,
        'timing': 'unprofiled CLI process wall includes load/init/run/pretty JSON write; profiles are separate runs',
        'queue_ns_scope': 'queue construction/sort and in-phase invalidation merge only; all maintenance is included in wall time',
        'queue_updates_scope': 'waiting-job invalidation notifications; not all set inserts/removes',
    }
    helper = DependencyDispatchTests()
    f35 = ROOT/'tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json'
    cases = {'f35': json.loads(f35.read_text()), 'synthetic-capacity-16': helper.contention(),
             'synthetic-shortage-16': helper.contention(stock=True),
             'synthetic-remote-16': helper.remote_contention()}
    identity['upstream_manifest'] = json.loads(f35.with_name('manifest.json').read_text())
    save(out/'identity.json', identity)
    rows=[]; batch_rows=[]
    for name, inputs in cases.items():
        case = out/name; case.mkdir(exist_ok=True)
        source=case/'inputs.json'; save(source,inputs)
        for semantic in ('legacy-minute-v1','event-time-v2'):
            directory=case/semantic; directory.mkdir(exist_ok=True)
            indexed=directory/'indexed-plan.json'; baseline=directory/'scan-plan.json'
            start=time.perf_counter_ns()
            compiled=checked([sys.executable,ROOT/'scripts/compile_mlir_execution_plan.py',source,indexed,
                '--semantic-profile',semantic,'--plugin-dir',args.plugin_dir.resolve(),'--mlir-opt',args.mlir_opt.resolve()])
            compile_wall=time.perf_counter_ns()-start
            compile_report=json.loads(compiled.stdout);compile_report['compile_process_wall_ns']=compile_wall
            save(directory/'compile.json',compile_report)
            raw=json.loads(indexed.read_text());raw.pop('resource_dispatch_index');save(baseline,raw)
            for level in ('full','summary'):
                print(name,semantic,level,flush=True)
                expected={}; records={arm:[] for arm in ('scan','cache','candidates')}
                def command(arm,seed,profile=False):
                    cmd=[runtime,baseline if arm=='scan' else indexed,directory/'result.tmp.json',
                         '--seed',seed,'--observation-level',level]
                    if arm=='candidates':cmd+=['--dependency-dispatch']
                    if profile:cmd+=['--profile-output',directory/f'{level}-{arm}-{seed}-profile.json']
                    return cmd
                profiles={}
                for arm in records:
                    profiles[arm]=[]
                    for seed in (0,1,7):
                        checked(command(arm,seed,True))
                        result=json.loads((directory/'result.tmp.json').read_text())
                        if arm=='scan':expected[seed]=result
                        else:assert result==expected[seed],(name,semantic,level,arm,seed)
                        profiles[arm].append(json.loads((directory/f'{level}-{arm}-{seed}-profile.json').read_text()))
                    checked(command(arm,0))  # unprofiled warmup
                for repeat in range(args.repeats):
                    arms=list(records);arms=arms[repeat%3:]+arms[:repeat%3]
                    for arm in arms:
                        for seed in (0,1,7):
                            start=time.perf_counter_ns();checked(command(arm,seed))
                            wall=time.perf_counter_ns()-start
                            result=json.loads((directory/'result.tmp.json').read_text())
                            assert result==expected[seed]
                            records[arm].append({'repeat':repeat,'seed':seed,'wall_ns':wall})
                hashes={str(seed):hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                        for seed,result in expected.items()}
                row={'case':name,'semantic_profile':semantic,'observation_level':level,
                     'input_sha256':sha(source),'plan_fingerprint':compile_report['plan_fingerprint'],
                     'result_sha256':hashes,'records':records,'profiles':profiles,
                     'median_wall_ns':{arm:statistics.median(r['wall_ns'] for r in data) for arm,data in records.items()}}
                rows.append(row);save(out/'runs.json',rows)
                if name=='f35' and semantic=='event-time-v2':
                    sample_hash=None
                    for arm in records:
                        for threads in (1,4):
                            report=directory/f'{level}-{arm}-batch-{threads}.json'
                            cmd=[batch,baseline if arm=='scan' else indexed,report,'--seeds','0,1,7,7,0,1,7,7',
                                 '--worker-threads',threads,'--observation-level',level,'--repeats',args.repeats]
                            if arm=='candidates':cmd+=['--dependency-dispatch']
                            checked(cmd);data=json.loads(report.read_text())
                            for record in data['records']:
                                if sample_hash is None:sample_hash=record['samples_sha256']
                                assert sample_hash==record['samples_sha256']
                            batch_rows.append({'observation_level':level,'arm':arm,'threads':threads,
                                'median_end_to_end_ns':statistics.median(r['phases']['end_to_end_batch_ns'] for r in data['records']),
                                'samples_sha256':sample_hash})
                    save(out/'batch-summary.json',batch_rows)
            (directory/'result.tmp.json').unlink()
    identity['load_after']=os.getloadavg();save(out/'identity.json',identity)


if __name__=='__main__':main()
