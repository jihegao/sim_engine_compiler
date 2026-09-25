#!/usr/bin/env python3
"""Measure canonical MC cache/FFI boundary independently from native CLI timings."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time

from sim_engine_compiler import _runtime, run_canonical_batch

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True, help='Must match the extension build metadata')
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--threads', default='1,2,4,8')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    threads = list(map(int, args.threads.split(',')))
    if args.repeats < 1 or min(threads) < 1 or args.samples < max(threads):
        parser.error('positive repeats/threads and samples >= max threads required')
    inputs_path = ROOT / 'tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json'
    inputs = json.loads(inputs_path.read_text())
    seeds = list(itertools.islice(itertools.cycle([0, 1, 7, 7]), args.samples))
    requests = [{'sample_index': i, 'seed': seed, 'canonical_inputs': inputs} for i, seed in enumerate(seeds)]
    records = []
    expected = None
    with tempfile.TemporaryDirectory(prefix='sim-binding-baseline-') as cache:
        def invoke(count, repeat, phase):
            nonlocal expected
            start = time.perf_counter_ns()
            result = run_canonical_batch(requests, worker_threads=count, cache_dir=cache)
            wall = time.perf_counter_ns() - start
            if result['engine_metadata']['build_commit'] != args.source_commit:
                raise AssertionError('extension build commit mismatch')
            if result['failed_samples']:
                raise AssertionError(result['failed_samples'])
            if [s['sample_index'] for s in result['samples']] != list(range(args.samples)):
                raise AssertionError('sample order changed')
            if [s['seed'] for s in result['samples']] != seeds:
                raise AssertionError('seed order changed')
            if expected is None:
                expected = result['samples']
            if expected != result['samples']:
                raise AssertionError('complete MC result changed across threads or cache paths')
            record = {'repeat': repeat, 'phase': phase, 'threads': count, 'call_ns': wall,
                      'timings': result['timings'], 'cache_status': result['plan_cache_status'],
                      'cache_groups': result['cache_groups'],
                      'samples_sha256': hashlib.sha256(json.dumps(result['samples'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
            records.append(record)
            return result['engine_metadata']
        metadata = invoke(1, -1, 'cold_cache_miss')
        for count in threads:
            invoke(count, -1, 'warmup')
        for repeat in range(args.repeats):
            for count in threads if repeat % 2 == 0 else list(reversed(threads)):
                print(f'MC repeat={repeat} threads={count}', flush=True)
                invoke(count, repeat, 'measured_cache_hit')
    report = {'schema_version': 'integrated-mc-binding-baseline/v1',
              'source_commit': args.source_commit, 'engine_metadata': metadata,
              'platform': platform.platform(), 'python': sys.version,
              'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
              'logical_cpus': os.cpu_count(), 'cpu_topology': subprocess.check_output(['lscpu'], text=True),
              'cpu_affinity': 'OS scheduled, no explicit pinning or frequency control',
              'input_sha256': hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
              'extension_sha256': hashlib.sha256(Path(_runtime.__file__).read_bytes()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'seeds': seeds, 'repeats': args.repeats, 'records': records,
              'process_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
              'summary': [{'threads': count, 'median_call_ns': statistics.median(r['call_ns'] for r in records if r['threads']==count and r['phase']=='measured_cache_hit')}
                          for count in threads]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
