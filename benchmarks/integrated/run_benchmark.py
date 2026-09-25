#!/usr/bin/env python3
"""Freeze the integrated F35 baseline; builds and correctness gates precede timing.

Requires current-checkout MLIR plugins. Run the conformance suite first. Does not
change engine defaults or interpret Project JSON. Binding measurements are a
separate optional boundary, and an unavailable binding is explicitly reported.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json'


def checked(command):
    return subprocess.run([str(v) for v in command], cwd=ROOT, check=True,
                          text=True, capture_output=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plugin-dir', type=Path, required=True)
    parser.add_argument('--mlir-opt', type=Path, required=True)
    parser.add_argument('--threads', default='1,2,4,8')
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1 or args.samples < 1:
        parser.error('positive samples and repeats required')
    threads = [int(v) for v in args.threads.split(',')]
    if any(v < 1 for v in threads) or args.samples < max(threads):
        parser.error('positive threads and samples >= max threads required')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source_status = checked(['git', 'status', '--porcelain', '--untracked-files=no']).stdout
    if source_status:
        raise RuntimeError('commit tracked source changes before freezing a baseline')
    identity = {
        'source_commit': checked(['git', 'rev-parse', 'HEAD']).stdout.strip(),
        'source_tree': checked(['git', 'rev-parse', 'HEAD^{tree}']).stdout.strip(),
        'platform': platform.platform(), 'machine': platform.machine(),
        'logical_cpus': os.cpu_count(), 'python': sys.version,
        'rustc': checked(['rustc', '--version']).stdout.strip(),
        'input_sha256': digest(INPUT),
        'upstream_manifest': json.loads(INPUT.with_name('manifest.json').read_text()),
        'binding_boundary': 'unmeasured',
        'cpu_affinity': 'OS scheduled; no affinity or frequency control',
        'background_load_before': os.getloadavg(),
    }
    if sys.platform == 'darwin':
        identity['cpu_topology'] = checked(['sysctl', 'hw.physicalcpu', 'hw.perflevel0.physicalcpu', 'hw.perflevel1.physicalcpu']).stdout.strip()
    if max(threads) > (int(checked(['sysctl', '-n', 'hw.physicalcpu']).stdout) if sys.platform == 'darwin' else os.cpu_count()):
        raise RuntimeError('requested threads exceed host CPU cap')
    save(out / 'identity.json', identity)
    for profile in ('legacy-minute-v1', 'event-time-v2'):
        print(f'MLIR three-arm correctness and cost: {profile}', flush=True)
        checked([sys.executable, ROOT / 'scripts/benchmark_mlir_resource_dispatch.py', out / profile,
                 '--plugin-dir', args.plugin_dir.resolve(), '--mlir-opt', args.mlir_opt.resolve(),
                 '--semantic-profile', profile, '--repeats', args.repeats, '--compile-repeats', args.repeats])
    checked(['cargo', 'build', '--locked', '--release', '--manifest-path', ROOT / 'rust/compiler/Cargo.toml'])
    checked(['cargo', 'build', '--locked', '--release', '--manifest-path', ROOT / 'rust/runtime/Cargo.toml', '--bin', 'stage-c-benchmark'])
    binary = ROOT / 'rust/runtime/target/release/stage-c-benchmark'
    compiler = ROOT / 'rust/compiler/target/release/sim-engine-compiler-aot'
    identity['binary_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in (binary, compiler)}
    identity['mlir_artifact_sha256'] = {p.name: digest(p) for p in (
        args.mlir_opt, args.plugin_dir / 'SimDialect.so', args.plugin_dir / 'SimResourceDispatchPass.so')}
    save(out / 'identity.json', identity)
    print('AOT v3 cold/miss/hit phases', flush=True)
    checked([sys.executable, ROOT / 'benchmarks/cold_start/run_benchmark.py', '--compiler', compiler,
             '--output', out / 'cache-v3.json', '--warmups', 1, '--repeats', max(3, args.repeats)])
    seeds = [v for _, v in zip(range(args.samples), itertools.cycle([0, 1, 7, 7]))]
    records = []
    hashes = {}
    with tempfile.TemporaryDirectory(prefix='sim-integrated-batch-') as tmp:
        for repeat in range(args.repeats):
            configurations = list(itertools.product(('full', 'summary'), ('baseline', 'mlir-pass-on'), threads))
            if repeat % 2:
                configurations.reverse()
            for observation, arm, count in configurations:
                print(f'batch repeat={repeat} {observation} {arm} threads={count}', flush=True)
                plan = out / 'event-time-v2' / f'{arm}-plan.json'
                report_path = Path(tmp) / 'batch.json'
                command = [binary, plan, report_path, '--seeds', ','.join(map(str, seeds)),
                           '--worker-threads', count, '--warmups', 1, '--repeats', 1,
                           '--observation-level', observation]
                if sys.platform == 'darwin':
                    command = ['/usr/bin/time', '-l', *command]
                started = time.perf_counter_ns()
                process = checked(command)
                wall = time.perf_counter_ns() - started
                report = json.loads(report_path.read_text())
                row = report['records'][0]
                if row['sample_indexes'] != list(range(len(seeds))) or row['seeds'] != seeds:
                    raise AssertionError('unstable sample identity/order')
                # Derived indexes are excluded from semantic Plan identity;
                # samples must match across index modes as well as threads.
                key = observation
                previous = hashes.setdefault(key, row['samples_sha256'])
                if previous != row['samples_sha256']:
                    raise AssertionError('sample result changed across thread counts/repeats')
                rss = next((int(line.strip().split()[0]) for line in process.stderr.splitlines()
                            if line.strip().endswith('maximum resident set size')), None)
                records.append({'repeat': repeat, 'arm': arm, 'observation': observation,
                                'threads': count, 'process_wall_including_warmup_ns': wall,
                                'peak_rss_bytes': rss, 'report': report})
                save(out / 'batch.json', {'seeds': seeds, 'warmups_per_invocation': 1,
                     'run_order': 'forward/reverse configurations on alternating repeats', 'records': records})
    summary = []
    for observation, arm, count in itertools.product(('full', 'summary'), ('baseline', 'mlir-pass-on'), threads):
        rows = [r['report']['records'][0]['phases'] for r in records if
                (r['observation'], r['arm'], r['threads']) == (observation, arm, count)]
        timings = {key: statistics.median(row[key] for row in rows) for key in rows[0]}
        summary.append({'observation': observation, 'arm': arm, 'threads': count,
                        'median_ns': timings, 'samples_per_second': len(seeds) * 1e9 / timings['batch_execution_ns']})
    # Keep the Python/FFI boundary explicit. Native MC acceptance is exercised
    # by the compiler tests; never substitute CLI latency for a binding result.
    import sim_engine_compiler
    if sim_engine_compiler.native_available():
        identity['binding_boundary'] = 'available; measured separately in binding.json'
        requests = [{'sample_index': i, 'seed': seed, 'canonical_inputs': json.loads(INPUT.read_text())}
                    for i, seed in enumerate(seeds)]
        calls = []
        expected = None
        with tempfile.TemporaryDirectory(prefix='sim-integrated-mc-') as cache:
            for repeat in range(args.repeats):
                for count in threads if repeat % 2 == 0 else list(reversed(threads)):
                    started = time.perf_counter_ns()
                    result = sim_engine_compiler.run_canonical_batch(requests, worker_threads=count, cache_dir=cache)
                    elapsed = time.perf_counter_ns() - started
                    if result['failed_samples']:
                        raise AssertionError(result['failed_samples'])
                    if expected is None:
                        expected = result['samples']
                    if result['samples'] != expected:
                        raise AssertionError('MC binding result/order changed')
                    calls.append({'repeat': repeat, 'threads': count, 'call_ns': elapsed,
                                  'timings': result['timings'], 'cache_status': result['plan_cache_status']})
        save(out / 'binding.json', {'records': calls, 'metadata': result['engine_metadata']})
    else:
        identity['binding_boundary'] = 'unavailable; no Python/FFI performance claim'
    identity['background_load_after'] = os.getloadavg()
    save(out / 'identity.json', identity)
    save(out / 'summary.json', summary)
    print('Completed: ' + str(out), flush=True)


if __name__ == '__main__':
    main()
