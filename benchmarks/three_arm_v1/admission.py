#!/usr/bin/env python3
"""Prepare current three-layer artifacts and retain field-level semantic evidence.

This is an untimed semantic/diagnostic driver, never a formal performance run.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.compiler.layout import compile_core
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR
from sim_engine_compiler.reference import SimpyReferenceRuntime


RECEIPT_SCHEMA = 'three-arm-regression-receipt/v1'
REQUIRED_CHECK_IDS = {
    'rust-unit',
    'dispatch-regression',
    'ir-reuse',
    'admission-controls',
    'driver-controls',
}
BUILD_COMMAND = [
    'cargo', '+1.90.0', 'build', '--locked', '--release',
    '--manifest-path', 'rust/runtime/Cargo.toml',
    '--bin', 'sim-engine-runtime', '--bin', 'stage-c-benchmark',
]
J35_MANIFEST_SHA256 = 'f486e1f9c6a390bffb867547781a5e68a44564fa30c27fc4eba77b6e4d85b175'
J35_CANONICAL_SHA256 = 'ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793'
J35_SEMANTIC_SHA256 = 'faf7c801351fd1cd3817fe3f03fe2b7e95056a7c1d9733e5863b291fddc2a689'
PROFILE_COUNTER_FIELDS = {
    'minute_iterations', 'event_calendar_rebuilds', 'event_candidates_pushed',
    'event_candidates_popped', 'event_wakeups', 'event_skipped_minutes',
    'event_max_queue_len', 'event_continuous_job_ticks',
    'event_continuous_failure_ticks', 'mission_scan_items', 'aircraft_scan_items',
    'job_scan_items', 'resource_dispatch_phase_calls',
    'resource_dispatch_waiting_jobs_observed', 'resource_dispatch_candidate_visits',
    'resource_dispatch_guard_evaluations', 'resource_dispatch_cache_hits',
    'resource_dispatch_replay_visits', 'resource_dispatch_index_lookups',
    'resource_dispatch_index_candidate_visits', 'resource_dispatch_index_waiter_visits',
    'resource_dispatch_waiting_index_updates', 'resource_dispatch_sort_items',
    'resource_dispatch_merge_inputs', 'resource_dispatch_merge_insertions',
    'resource_dispatch_queue_updates', 'resource_dispatch_event_attempts',
    'job_progress_candidate_visits', 'waiting_job_indexes_peak',
    'running_job_indexes_peak', 'component_scan_items', 'preventive_scan_items',
    'shipment_scan_items', 'trace_events_attempted', 'trace_events_materialized',
    'trace_event_string_values', 'rng_requests', 'plan_spec_clones',
    'indexed_map_reads', 'indexed_map_writes',
}
PROFILE_TIMING_FIELDS = {
    'execution_ns', 'resource_dispatch_queue_ns', 'trace_event_build_ns', 'rng_ns',
    'metrics_build_ns', 'terminal_state_build_ns',
}
PROFILE_TOP_TIMING_FIELDS = {
    'plan_load_ns', 'initialization_ns', 'execution_ns', 'result_write_ns',
    'process_wall_ns',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def archive(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=str(path), mode='wb', mtime=0) as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode())


def canonical_sha(value):
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _nonnegative_integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer')


def validate_profile_output(value, *, arm):
    if not isinstance(value, dict):
        raise ValueError('profile output must be an object')
    for field in PROFILE_TOP_TIMING_FIELDS:
        _nonnegative_integer(value.get(field), f'profile output {field}')
    profile = value.get('profile')
    if not isinstance(profile, dict):
        raise ValueError('profile output lacks profile object')
    missing = (PROFILE_COUNTER_FIELDS | PROFILE_TIMING_FIELDS | {'phases'}) - set(profile)
    if missing:
        raise ValueError(f'profile output lacks workload fields: {sorted(missing)}')
    for field in PROFILE_COUNTER_FIELDS | PROFILE_TIMING_FIELDS:
        _nonnegative_integer(profile[field], f'profile.{field}')
    if value['execution_ns'] != profile['execution_ns']:
        raise ValueError('top-level and runtime execution_ns differ')
    phases = profile['phases']
    if not isinstance(phases, dict):
        raise ValueError('profile.phases must be an object')
    for phase, record in phases.items():
        if not isinstance(phase, str) or not isinstance(record, dict):
            raise ValueError('profile phase entries must be named objects')
        _nonnegative_integer(record.get('calls'), f'profile.phases.{phase}.calls')
        _nonnegative_integer(record.get('elapsed_ns'), f'profile.phases.{phase}.elapsed_ns')
    if profile['resource_dispatch_merge_insertions'] > profile['resource_dispatch_merge_inputs']:
        raise ValueError('dispatch merge insertions exceed inputs')
    visits = (
        profile['resource_dispatch_candidate_visits']
        + profile['resource_dispatch_replay_visits']
    )
    if profile['resource_dispatch_guard_evaluations'] > visits:
        raise ValueError('dispatch guard evaluations exceed visited work')
    if profile['resource_dispatch_cache_hits'] > visits:
        raise ValueError('dispatch cache hits exceed visited work')
    if profile['resource_dispatch_event_attempts'] > profile['trace_events_attempted']:
        raise ValueError('dispatch events exceed all attempted trace events')
    if profile['trace_events_materialized'] > profile['trace_events_attempted']:
        raise ValueError('materialized trace events exceed attempted events')
    if (
        profile['resource_dispatch_index_candidate_visits'] > 0
        and profile['resource_dispatch_index_lookups'] == 0
    ):
        raise ValueError('index candidates exist without an index lookup')
    if (
        profile['resource_dispatch_index_waiter_visits'] > 0
        and profile['resource_dispatch_index_candidate_visits'] == 0
    ):
        raise ValueError('indexed waiters exist without a dependency candidate')
    if arm in ('scan', 'cache'):
        if (
            profile['resource_dispatch_sort_items']
            != profile['resource_dispatch_waiting_jobs_observed']
        ):
            raise ValueError(f'{arm} sort workload must equal observed waiting workload')
        if profile['resource_dispatch_merge_inputs'] != 0:
            raise ValueError(f'{arm} must not report candidate-queue merge inputs')
    elif arm == 'candidates':
        if profile['resource_dispatch_sort_items'] != 0:
            raise ValueError('candidate dispatch must not report full-scan sort work')
    else:
        raise ValueError(f'unsupported profile arm {arm!r}')
    return profile


def _resolve_recorded_path(raw):
    if not isinstance(raw, str) or not raw:
        raise ValueError('evidence path must be a nonempty string')
    path = Path(raw)
    return (path if path.is_absolute() else ROOT / path).resolve()


def _validate_success_log(check_id, path):
    text = path.read_text(errors='replace')
    if not text.strip():
        raise ValueError(f'{check_id} log is empty')
    if check_id == 'rust-unit':
        counts = [int(value) for value in re.findall(r'(?m)^running (\d+) tests?$', text)]
        passed = (
            any(value > 0 for value in counts)
            and bool(re.search(
                r'test result: ok\. \d+ passed; 0 failed; 0 ignored; '
                r'0 measured; 0 filtered out', text,
            ))
        )
    else:
        counts = [int(value) for value in re.findall(r'(?m)^Ran (\d+) tests?', text)]
        passed = any(value > 0 for value in counts) and bool(re.search(r'(?m)^OK\s*$', text))
    if not passed:
        raise ValueError(f'{check_id} log lacks a recognized success result')


def build_source_files():
    required = {
        'rust/runtime/Cargo.lock',
        'rust/runtime/Cargo.toml',
        'rust/runtime/rust-toolchain.toml',
    }
    paths = checked([
        'git', 'ls-files', 'rust/runtime/src', *sorted(required),
    ]).stdout.splitlines()
    if not paths or not required.issubset(paths):
        raise ValueError('tracked Rust source/toolchain manifest inventory is incomplete')
    return {path: sha(ROOT / path) for path in paths}


def expected_verification_commands(python, plugin, mlir):
    # plugin/mlir are deliberately accepted here so the receipt producer uses
    # one helper for both the fixed argv and its paired environment identity.
    Path(plugin)
    Path(mlir)
    python = str(Path(python).absolute())
    return {
        'rust-unit': [
            'cargo', '+1.90.0', 'test', '--locked', '--release',
            '--manifest-path', 'rust/runtime/Cargo.toml', '--lib',
        ],
        'dispatch-regression': [
            python, '-m', 'unittest',
            'tests.differential.test_dependency_dispatch',
            'tests.conformance.test_b2_b3_reference',
            'tests.conformance.test_b1_reference',
            'tests.differential.test_ir_layers', '-v',
        ],
        'ir-reuse': [
            'env', 'SIM_ENGINE_REQUIRE_THREE_ARM=1', python, '-m', 'unittest',
            'tests.differential.test_three_arm_reuse', '-v',
        ],
        'admission-controls': [
            python, '-m', 'unittest',
            'tests.conformance.test_three_arm_admission', '-v',
        ],
        'driver-controls': [
            python, '-m', 'unittest',
            'tests.conformance.test_three_arm_driver',
            'tests.conformance.test_three_arm_summary',
            'tests.conformance.test_cpu_batch_baseline', '-v',
        ],
    }


def expected_verification_environment(plugin, mlir):
    plugin = Path(plugin).resolve()
    mlir = Path(mlir).resolve()
    library_dir = mlir.parent.parent / 'lib'
    return {
        'variables': {
            'RUSTUP_TOOLCHAIN': '1.90.0',
            'SIM_ENGINE_REQUIRE_MLIR': '1',
            'SIM_ENGINE_REQUIRE_THREE_ARM': '1',
            'SIM_ENGINE_MLIR_PLUGIN_DIR': str(plugin),
            'SIM_ENGINE_MLIR_OPT': str(mlir),
            'LD_LIBRARY_PATH': str(library_dir),
        },
        'artifacts': {
            'mlir_opt': {'path': str(mlir), 'sha256': sha(mlir)},
            'plugins': {
                name: {
                    'path': str(plugin / name),
                    'sha256': sha(plugin / name),
                }
                for name in ('SimDialect.so', 'SimResourceDispatchPass.so')
            },
        },
    }


def validate_regression_receipt(
    receipt, *, source_commit, expected_binaries, rustc_vv,
    expected_commands, expected_environment,
):
    if receipt.get('schema_version') != RECEIPT_SCHEMA or receipt.get('status') != 'passed':
        raise ValueError(f'regression receipt must be passed {RECEIPT_SCHEMA}')
    if receipt.get('source_commit') != source_commit:
        raise ValueError('regression receipt source_commit differs from current HEAD')
    if receipt.get('environment') != expected_environment:
        raise ValueError('regression receipt MLIR/toolchain environment mismatch')
    raw_files = receipt.get('raw_files')
    if not isinstance(raw_files, dict) or not raw_files:
        raise ValueError('regression receipt raw_files must be nonempty')
    resolved_raw = {}
    for raw_path, digest in raw_files.items():
        path = _resolve_recorded_path(raw_path)
        if not re.fullmatch(r'[0-9a-f]{64}', digest or ''):
            raise ValueError(f'invalid evidence SHA-256: {raw_path}')
        if not path.is_file() or sha(path) != digest:
            raise ValueError(f'regression evidence changed or missing: {path}')
        if path in resolved_raw:
            raise ValueError(f'duplicate regression evidence path: {path}')
        resolved_raw[path] = digest
    checks = receipt.get('checks')
    if not isinstance(checks, list):
        raise ValueError('regression receipt checks must be a list')
    by_id = {}
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get('id'), str):
            raise ValueError('receipt check must be an object with an id')
        check_id = check['id']
        if check_id in by_id:
            raise ValueError(f'duplicate receipt check id: {check_id}')
        by_id[check_id] = check
    if set(by_id) != REQUIRED_CHECK_IDS:
        raise ValueError(f'receipt check IDs must be exactly {sorted(REQUIRED_CHECK_IDS)}')
    for check_id, check in by_id.items():
        command = check.get('command')
        if not isinstance(command, list) or not command or any(
            not isinstance(item, str) or not item for item in command
        ):
            raise ValueError(f'{check_id} command must be a nonempty argv list')
        if command != expected_commands[check_id]:
            raise ValueError(f'{check_id} command differs from the frozen argv')
        if check.get('passed') is not True or check.get('exit_code') != 0:
            raise ValueError(f'{check_id} did not pass with exit code zero')
        log_path = _resolve_recorded_path(check.get('log_path'))
        if log_path not in resolved_raw:
            raise ValueError(f'{check_id} log is absent from raw_files')
        _validate_success_log(check_id, log_path)
    reuse_paths = [
        path for path in resolved_raw
        if path.as_posix().endswith('/runs/three-arm-v1/reuse/manifest.json')
    ]
    if len(reuse_paths) != 1:
        raise ValueError('receipt must bind exactly one IR reuse manifest')
    reuse = json.loads(reuse_paths[0].read_text())
    if reuse.get('schema_version') != 'three-arm-ir-reuse-artifacts/v1' or not reuse.get('variants'):
        raise ValueError('IR reuse manifest is incomplete')
    build = receipt.get('build')
    if not isinstance(build, dict):
        raise ValueError('receipt lacks build identity')
    if build.get('command') != BUILD_COMMAND:
        raise ValueError('receipt build command is not the frozen Rust 1.90.0 command')
    if build.get('passed') is not True or build.get('exit_code') != 0:
        raise ValueError('receipt build did not pass with exit code zero')
    if build.get('source_commit') != source_commit:
        raise ValueError('receipt build source_commit differs from current HEAD')
    if build.get('rustc_vv') != rustc_vv or not rustc_vv.startswith('rustc 1.90.0 '):
        raise ValueError('receipt build rustc identity mismatch')
    if build.get('source_files') != build_source_files():
        raise ValueError('receipt build Rust source/Cargo.lock hashes mismatch')
    build_log = _resolve_recorded_path(build.get('log_path'))
    if build_log not in resolved_raw:
        raise ValueError('build log is absent from raw_files')
    build_text = build_log.read_text(errors='replace')
    if not build_text.strip() or 'Finished `release` profile' not in build_text:
        raise ValueError('build log lacks successful release completion')
    binaries = build.get('binaries')
    if not isinstance(binaries, dict) or set(binaries) != set(expected_binaries):
        raise ValueError('receipt build binaries are incomplete')
    for name, expected_path in expected_binaries.items():
        record = binaries[name]
        if not isinstance(record, dict):
            raise ValueError(f'invalid build binary record: {name}')
        path = _resolve_recorded_path(record.get('path'))
        if path != expected_path.resolve() or not path.is_file():
            raise ValueError(f'build binary path mismatch: {name}')
        if record.get('sha256') != sha(path):
            raise ValueError(f'build binary hash mismatch: {name}')
    return {str(path): digest for path, digest in resolved_raw.items()}


def _git_source_snapshot():
    head = checked(['git', 'rev-parse', 'HEAD']).stdout.strip()
    status = checked(
        ['git', 'status', '--porcelain=v1', '--untracked-files=all']
    ).stdout.strip()
    require_clean_source_state(status)
    return head


def require_clean_source_state(status):
    if status:
        raise ValueError(f'admission requires committed clean tracked/untracked source:\n{status}')


def admission_status(selected_case_ids, expected_case_ids):
    admissible = list(selected_case_ids) == list(expected_case_ids)
    return ('passed', True) if admissible else ('partial', False)


def validate_profile_manifest(records, case_ids, *, require_complete):
    keys = {
        (record.get('case'),record.get('arm'),record.get('level'),record.get('seed'))
        for record in records
    }
    expected = {
        (case,arm,level,0)
        for case in case_ids
        for arm in ('scan','cache','candidates')
        for level in ('full','summary')
    }
    if (
        len(records)!=len(keys)
        or keys!=expected
        or any(
            record.get('workload_fields_validated') is not True
            or record.get('timing_fields_semantic') is not False
            or record.get('passed') is not True
            or not isinstance(record.get('input_sha256'),str)
            or not re.fullmatch(r'[0-9a-f]{64}',record['input_sha256'])
            or not isinstance(record.get('profile_path'),str)
            or not record['profile_path']
            for record in records
        )
    ):
        raise ValueError('profile manifest is incomplete, duplicated, or invalid')
    if require_complete and len(records)!=60:
        raise ValueError('passed semantic admission requires exactly 60 profile outputs')
    return keys


def _require_source_unchanged(head):
    current = checked(['git', 'rev-parse', 'HEAD']).stdout.strip()
    if current != head:
        raise ValueError('source commit changed during semantic admission')
    status = checked(
        ['git', 'status', '--porcelain=v1', '--untracked-files=all']
    ).stdout.strip()
    if status:
        raise ValueError(f'source became dirty during semantic admission:\n{status}')


def _git_blob_sha256(repository, revision, path):
    result = subprocess.run(
        ['git', '-C', str(repository), 'show', f'{revision}:{path}'],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f'pinned upstream blob is unavailable: {revision}:{path}')
    return hashlib.sha256(result.stdout).hexdigest()


def validate_j35_source(source_manifest_path, source_input_path, audit_path):
    if sha(source_manifest_path) != J35_MANIFEST_SHA256:
        raise ValueError('frozen J35 source manifest hash mismatch')
    manifest = json.loads(source_manifest_path.read_text())
    audit = json.loads(audit_path.read_text())
    if sha(source_input_path) != J35_CANONICAL_SHA256:
        raise ValueError('frozen J35 canonical file hash mismatch')
    if manifest.get('canonical_file_sha256') != J35_CANONICAL_SHA256:
        raise ValueError('J35 manifest canonical hash mismatch')
    if canonical_sha(json.loads(source_input_path.read_text())) != J35_SEMANTIC_SHA256:
        raise ValueError('J35 canonical semantic digest mismatch')
    if audit.get('schema_version') != 'three-arm-source-audit/v1':
        raise ValueError('J35 source audit schema mismatch')
    upstream = audit.get('upstream', {})
    identity = audit.get('source_identity', {})
    canonical = audit.get('canonical_identity', {})
    result = audit.get('result', {})
    reproduction = audit.get('reproduction', {}).get('comparisons', {})
    if upstream.get('head') != manifest.get('spare_mvp_commit'):
        raise ValueError('J35 audit upstream revision differs from manifest')
    if identity.get('project_file_sha256') != manifest.get('source_sha256'):
        raise ValueError('J35 audit project hash differs from manifest')
    if identity.get('input_schema_sha256') != manifest.get('schema_sha256'):
        raise ValueError('J35 audit input schema hash differs from manifest')
    if identity.get('adapter_entrypoint') != manifest.get('adapter'):
        raise ValueError('J35 audit Adapter entrypoint differs from manifest')
    if canonical.get('manifest_file_sha256') != J35_MANIFEST_SHA256:
        raise ValueError('J35 audit manifest hash mismatch')
    if canonical.get('canonical_file_sha256') != J35_CANONICAL_SHA256:
        raise ValueError('J35 audit canonical hash mismatch')
    if canonical.get('canonical_semantic_digest') != J35_SEMANTIC_SHA256:
        raise ValueError('J35 audit semantic digest mismatch')
    if result != {
        'j35_source_provenance_verified': True,
        'canonical_export_byte_reproducible': True,
        'source_blocker': None,
        'float_whitelist_blocker_before_execution': None,
    }:
        raise ValueError('J35 source audit result flags are not verified')
    if (
        reproduction.get('canonical_cmp_exit') != 0
        or reproduction.get('manifest_cmp_exit') != 0
        or reproduction.get('canonical_byte_identical') is not True
        or reproduction.get('manifest_byte_identical') is not True
    ):
        raise ValueError('J35 source audit reproduction did not pass byte-for-byte')
    selected = upstream.get('selected_git_objects')
    repository = Path(upstream.get('path', ''))
    revision = upstream.get('head')
    if not isinstance(selected, dict) or not selected or not repository.is_dir():
        raise ValueError('J35 source audit lacks pinned upstream git objects')
    for path, expected_blob in selected.items():
        actual_blob = checked(
            ['git', '-C', repository, 'rev-parse', f'{revision}:{path}']
        ).stdout.strip()
        if actual_blob != expected_blob:
            raise ValueError(f'J35 recorded git blob mismatch: {path}')
    if _git_blob_sha256(repository, revision, 'exports/project-case-large.json') != manifest['source_sha256']:
        raise ValueError('J35 pinned Project blob bytes differ from manifest')
    if (
        _git_blob_sha256(
            repository, revision, 'contracts/aircraft_support_v1_input.schema.json'
        )
        != manifest['schema_sha256']
    ):
        raise ValueError('J35 pinned input schema bytes differ from manifest')
    return manifest, audit


def compare(left, right, *, reference=False, path='root'):
    if type(left) is not type(right):
        raise AssertionError(f'{path}: type {type(left).__name__} != {type(right).__name__}')
    if isinstance(left, dict):
        if left.keys() != right.keys():
            raise AssertionError(f'{path}: keys differ')
        for k in left:
            compare(left[k], right[k], reference=reference, path=f'{path}.{k}')
    elif isinstance(left, list):
        if len(left) != len(right):
            raise AssertionError(f'{path}: length {len(left)} != {len(right)}')
        for i, (a, b) in enumerate(zip(left, right)):
            compare(a, b, reference=reference, path=f'{path}[{i}]')
    elif isinstance(left, float):
        if not math.isfinite(left) or not math.isfinite(right):
            raise AssertionError(f'{path}: nonfinite value')
        permitted = reference and re.fullmatch(r'root\.sample_requests\[\d+\]\.value_minutes', path)
        if left != right and not (permitted and math.isclose(left, right, rel_tol=2e-15, abs_tol=1e-12)):
            raise AssertionError(f'{path}: {left!r} != {right!r}')
    elif left != right:
        raise AssertionError(f'{path}: {left!r} != {right!r}')


def checked(command, *, timeout=300):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{command}: {result.stderr[-5000:]}')
    return result


def compile_case(name, inputs, out, plugin, mlir):
    directory = out / name
    source = directory / 'canonical.json'
    save(source, inputs)
    paths = {}
    compilation = []
    for profile, label in [('legacy-minute-v1', 'legacy'), ('event-time-v2', 'o5')]:
        import_started = time.perf_counter_ns()
        business = import_business_ir(inputs, semantic_profile=profile)
        import_ns = time.perf_counter_ns() - import_started
        save(directory / f'{label}-business.json', business.to_dict())
        # Reload each persisted layer; the compiler does not see hidden live objects.
        business = BusinessIR.from_dict(json.loads((directory / f'{label}-business.json').read_text()))
        lower_started = time.perf_counter_ns()
        core = lower_business(business)
        lower_ns = time.perf_counter_ns() - lower_started
        core_path = directory / f'{label}-core.json'
        save(core_path, core.to_dict())
        core = CoreIR.from_dict(json.loads(core_path.read_text()))
        scan = directory / f'{label}-scan.json'
        layout_started = time.perf_counter_ns()
        scan_plan = compile_core(core)
        layout_ns = time.perf_counter_ns() - layout_started
        save(scan, scan_plan.to_dict())
        indexed = directory / f'{label}-indexed.json'
        command = [sys.executable, ROOT/'scripts/compile_mlir_execution_plan.py', core_path, indexed,
                   '--plugin-dir', plugin, '--mlir-opt', mlir]
        rss_path = directory / f'{label}-compile-rss.txt'
        timed_command = ['/usr/bin/time', '-v', '-o', rss_path, *command]
        started = time.perf_counter_ns()
        result = checked(timed_command)
        record = json.loads(result.stdout)
        rss_text = rss_path.read_text()
        rss_match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', rss_text)
        if not rss_match:
            raise ValueError(f'GNU time did not report compile RSS for {name}/{label}')
        record.update(
            boundary='persisted Core read, MLIR pass, Plan validation and write; Business import/lowering excluded',
            profile=profile,
            diagnostic_process_wall_ns=time.perf_counter_ns()-started,
            command=[str(x) for x in timed_command],
            inner_command=[str(x) for x in command],
            peak_rss_kib=int(rss_match.group(1)),
            peak_rss_log=str(rss_path),
            python_stages={
                'import_business_ir_ns': import_ns,
                'lower_business_ns': lower_ns,
                'compile_core_ns': layout_ns,
                'peak_rss': {
                    'status': 'unavailable',
                    'reason': 'in-process Python stages are not isolated for peak RSS measurement',
                },
            },
            timing_role='unmeasured preparation diagnostic',
        )
        compilation.append(record)
        scan_raw = json.loads(scan.read_text())
        indexed_raw = json.loads(indexed.read_text())
        index = indexed_raw.pop('resource_dispatch_index')
        compare(scan_raw, indexed_raw)
        if index['schema_version'] != 'resource-dispatch-index/v2':
            raise AssertionError('v2 index required')
        paths[label] = {'scan': scan, 'cache': indexed, 'candidates': indexed}
    save(directory/'compilation.json', compilation)
    return directory, paths


def run_case(name, inputs, out, binary, plugin, mlir):
    directory, paths = compile_case(name, inputs, out, plugin, mlir)
    input_sha256 = canonical_sha(inputs)
    rows = []
    profile_records = []
    def execute(label, arm, seed, level, *, profile=False, seeds=None, threads=1):
        output = directory / 'current-result.json'
        cmd = [binary, paths[label][arm], output, '--observation-level', level]
        if seeds is None:
            cmd += ['--seed', seed]
        else:
            cmd += ['--seeds', ','.join(map(str,seeds)), '--worker-threads', threads]
        if arm == 'candidates':
            cmd += ['--dependency-dispatch']
        key = f'{label}-{arm}-{level}-' + (f'batch-{threads}' if seeds else f'{seed}')
        profile_path = None
        if profile:
            profile_path = directory/f'{key}-profile.json'
            cmd += ['--profile-output', profile_path]
            key += '-profiled'
        checked(cmd)
        result = json.loads(output.read_text())
        if profile_path is not None:
            profile_output = json.loads(profile_path.read_text())
            validate_profile_output(profile_output, arm=arm)
            profile_records.append({
                'case': name,
                'input_sha256': input_sha256,
                'arm': arm,
                'level': level,
                'seed': seed,
                'profile_path': str(profile_path),
                'workload_fields_validated': True,
                'timing_fields_semantic': False,
                'passed': True,
            })
        archive(directory/f'{key}.json.gz',result)
        output.unlink()
        return result
    fulls = {}
    for seed in (0,1,7):
        from sim_engine_compiler.ir.plan import ExecutionPlan
        ref = SimpyReferenceRuntime(ExecutionPlan.from_dict(json.loads(paths['legacy']['scan'].read_text())), seed=seed).run()
        archive(directory/f'reference-{seed}.json.gz',ref)
        legacy = execute('legacy','scan',seed,'full')
        compare(ref,legacy,reference=True)
        rows.append({'check':'reference-legacy','seed':seed,'strict_equal':ref==legacy,'passed':True})
        expected = copy.deepcopy(legacy)
        for arm in ('scan','cache','candidates'):
            full = execute('o5',arm,seed,'full')
            expected['plan_fingerprint'] = full['plan_fingerprint']
            compare(expected,full)
            summary = execute('o5',arm,seed,'summary')
            projected = {**full,'trace':[]}
            compare(projected,summary)
            if seed == 0:
                for level, result in [('full',full),('summary',summary)]:
                    profiled = execute('o5',arm,seed,level,profile=True)
                    compare(result,profiled)
            if arm == 'scan':
                fulls[seed] = full
            else:
                compare(fulls[seed], full)
            rows.append({'check':'three-arm/profile/observation','arm':arm,'seed':seed,'passed':True})
        print(f'{name}: seed {seed} reference/three arms/observations passed',flush=True)
    for level in ('full','summary'):
        prior = None
        for arm in ('scan','cache','candidates'):
            for threads in (1,3):
                batch = execute('o5',arm,0,level,seeds=[7,0,7,1],threads=threads)
                samples = batch['samples']
                if [s['sample_index'] for s in samples] != [0,1,2,3] or [s['seed'] for s in samples] != [7,0,7,1]:
                    raise AssertionError('sample order mismatch')
                for sample,seed in zip(samples,[7,0,7,1]):
                    expected = fulls[seed] if level=='full' else {**fulls[seed],'trace':[]}
                    compare(expected,sample['result'])
                if prior is not None:
                    compare(prior,samples)
                prior = samples
                rows.append({'check':'batch-order-duplicate-thread','arm':arm,'level':level,'threads':threads,'passed':True})
    save(directory/'checks.json',rows)
    gate_cases = {}
    for level in ('summary','full'):
        identity = name if level == 'summary' else f'{name}-full'
        gate_cases[identity] = {
            'semantic_profile':'event-time-v2','observation_level':level,
            'input_path':str((directory/'canonical.json').resolve()),
            'input_sha256':input_sha256,'seeds':[0,1,7],'untils':[None],
            'plans':{'scan_sha256':sha(paths['o5']['scan']), 'indexed_sha256':sha(paths['o5']['cache']),
                     'plan_fingerprint':fulls[0]['plan_fingerprint']},
            'comparisons':{'rust_three_arm_exact':True,
                'reference':{key:({'passed':True,'exact':False,'float_fields':['sample_requests[*].value_minutes'],'rel_tol':2e-15,'abs_tol':1e-12} if key=='sample_requests' else {'passed':True,'exact':True})
                    for key in ('trace_business_projection','sample_requests','metrics','terminal_state')},
                'threads':{'counts':[1,3],'duplicate_seed_order_exact':True}},
            'profile_validation':{
                'workload_counters_validated':True,
                'timing_fields_used_as_semantic_evidence':False,
                'outputs':[record for record in profile_records if record['level']==level],
            },
            'result_sha256_by_seed':{str(seed):hashlib.sha256(json.dumps(fulls[seed] if level=='full' else {**fulls[seed],'trace':[]},
                sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest() for seed in (0,1,7)}}
    return (
        {'id':name,'scan_plan':str(paths['o5']['scan']),'indexed_plan':str(paths['o5']['cache'])},
        rows,
        gate_cases,
        profile_records,
    )


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--plugin-dir',type=Path,required=True)
    parser.add_argument('--mlir-opt',type=Path,required=True)
    parser.add_argument('--regression-receipt',type=Path,required=True)
    parser.add_argument('--cases',nargs='+',help='Restrict preparation only; no formal timing implied')
    args=parser.parse_args()
    source_commit = _git_source_snapshot()
    out=args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('admission output must be empty; retain failed evidence separately')
    out.mkdir(parents=True,exist_ok=True)
    receipt=json.loads(args.regression_receipt.read_text())
    binary=ROOT/'rust/runtime/target/release/sim-engine-runtime'
    stage_binary=ROOT/'rust/runtime/target/release/stage-c-benchmark'
    rustc_vv=checked(['rustc','+1.90.0','-Vv']).stdout.strip()
    plugin_dir=args.plugin_dir.resolve()
    mlir_opt=args.mlir_opt.resolve()
    receipt_raw_files=validate_regression_receipt(
        receipt,
        source_commit=source_commit,
        expected_binaries={
            'sim-engine-runtime': binary,
            'stage-c-benchmark': stage_binary,
        },
        rustc_vv=rustc_vv,
        expected_commands=expected_verification_commands(sys.executable, plugin_dir, mlir_opt),
        expected_environment=expected_verification_environment(plugin_dir, mlir_opt),
    )
    save(out/'regression-receipt.json',receipt)
    source_manifest=ROOT/'benchmarks/batch_preparation/results/amd128-j35-20260926/source/manifest.json'
    source_input=source_manifest.with_name('simulation-inputs.json')
    source_audit=ROOT/'benchmarks/three_arm_v1/source-audit.json'
    source_manifest_value, source_audit_value = validate_j35_source(
        source_manifest, source_input, source_audit
    )
    save(out/'upstream-manifest.json',source_manifest_value)
    save(out/'source-audit.json',source_audit_value)
    artifact_paths=[binary,stage_binary,
                    mlir_opt,plugin_dir/'SimDialect.so',plugin_dir/'SimResourceDispatchPass.so',
                    ROOT/'rust/runtime/Cargo.lock',ROOT/'benchmarks/three_arm_v1/PROTOCOL.md']
    tracked=checked(['git','ls-files','src','rust/runtime/src','scripts/compile_mlir_execution_plan.py','tools/mlir_dispatch/src','benchmarks/three_arm_v1','tests/differential/test_three_arm_reuse.py']).stdout.splitlines()
    artifact_paths += [ROOT/p for p in tracked]
    save(out/'artifacts.json',{'source_commit':source_commit,'source_tree':checked(['git','rev-parse','HEAD^{tree}']).stdout.strip(),
         'files':{str(p):sha(p) for p in artifact_paths},'rustc':rustc_vv,
         'cargo':checked(['cargo','+1.90.0','-V']).stdout,'python':sys.version,'mlir':checked([mlir_opt,'--version']).stdout})
    from benchmarks.three_arm_v1.workloads import structural_workloads
    all_cases={'j35':json.loads(source_input.read_text())}
    for spec in structural_workloads():
        all_cases[spec.case_id]=spec.canonical_inputs
    expected_input_ids=list(all_cases)
    if args.cases:
        if len(args.cases)!=len(set(args.cases)):
            raise ValueError('--cases must not contain duplicate case IDs')
        unknown=set(args.cases)-set(all_cases)
        if unknown:
            raise ValueError(f'unknown case IDs: {sorted(unknown)}')
        cases={k:all_cases[k] for k in args.cases}
    else:
        cases=all_cases
    gate_status,admissible=admission_status(cases,expected_input_ids)
    all_rows=[];plan_cases=[];gate_cases={};profile_manifest=[]
    try:
        for name,inputs in cases.items():
            case,rows,case_gates,case_profiles=run_case(
                name,inputs,out,binary,plugin_dir,mlir_opt
            )
            gate_cases.update(case_gates)
            profile_manifest.extend(case_profiles)
            plan_cases.append(case);all_rows.extend({'case':name,**r} for r in rows)
        plan_map_cases=plan_cases + ([{**next(c for c in plan_cases if c['id']=='j35'),'id':'j35-full','observation_level':'full'}] if 'j35' in cases else [])
        published_case_ids=[c['id'] for c in plan_map_cases]
        if admissible and (len(cases)!=10 or len(plan_map_cases)!=11):
            raise ValueError('passed semantic admission requires 10 inputs and 11 case groups')
        if not all_rows or not all(row.get('passed') is True for row in all_rows):
            raise ValueError('semantic admission checks are empty or incomplete')
        if admissible and len(all_rows)!=240:
            raise ValueError('passed semantic admission requires exactly 240 semantic check rows')
        validate_profile_manifest(
            profile_manifest,cases,require_complete=admissible
        )
        save(out/'plan-map.json',{
            'schema_version':'three-arm-plan-map/v1','seeds':[0,1,7],
            'cases':plan_map_cases,
        })
        _require_source_unchanged(source_commit)
        inventory={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='gate.json'}
        for record in profile_manifest:
            if record['profile_path'] not in inventory:
                raise ValueError(f"profile evidence is absent from raw files: {record['profile_path']}")
        gate={'schema_version':'three-arm-semantic-gate/v1','status':gate_status,
            'admissible':admissible,'input_case_count':len(cases),
            'admission_case_count':len(plan_map_cases),'case_order':published_case_ids,
            'artifacts':{
                'sim_engine_runtime_path':str(binary),
                'sim_engine_runtime_sha256':sha(binary),
                'stage_c_benchmark_path':str(stage_binary),
                'stage_c_benchmark_sha256':sha(stage_binary),
            },
            'cases':{k:gate_cases[k] for k in published_case_ids},
            'source_commit':source_commit,
            'plan_sha256':{str(p):sha(p) for c in plan_cases for p in [Path(c['scan_plan']),Path(c['indexed_plan'])]},
            'raw_files':{**inventory,**receipt_raw_files,**{str(p):sha(p) for p in artifact_paths}},
            'checks':all_rows,'profile_manifest':profile_manifest}
        if not admissible:
            gate['nonadmissible_reason']='selected cases do not equal the frozen 10-input matrix in canonical order'
        save(out/'gate.json',gate)
    except BaseException as error:
        save(out/'gate.json',{'schema_version':'three-arm-semantic-gate/v1','status':'failed','error':str(error),'checks':all_rows})
        raise


if __name__=='__main__':main()
