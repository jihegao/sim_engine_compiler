"""Deterministic byte index of this bounded, zero-native classification."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import copy_classification_proofs
import copy_root_publication_methods
import source_gate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INDEX = HERE / 'evidence-index.json'
CATALOG = REPO / 'cases/simlox-air-support/publication-index-v1.json'
PUB_ID = 'I04.var09.arrived_system_next_mission.1.0.0'
GO_SHA = '4261b3318d47ea0fdbbae0e53701f51071a3d64776032bb3f9af06911c5da35d'


def pin(data: bytes) -> dict:
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def exact_file(path: Path, row: dict) -> None:
    assert pin(path.read_bytes()) == {k: row[k] for k in ('bytes', 'sha256')}, str(path)


def read(path: Path) -> dict:
    return source_gate.decode(path.read_bytes())


def encode(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def proof_write_originals() -> dict:
    data = read(HERE / 'proof-write-originals.json')
    assert data['schema'] == 'i04-var09-proof-write-originals/v1'
    assert len(data['records']) == 4
    assert [Path(r['path']).name for r in data['records']] == [
        'receipt.json', 'stdout.bin', 'stderr.bin', 'i04-var09-proof-custody-capture-20261008.py']
    for row in data['records']:
        path = Path(row['path'])
        assert path.is_absolute() and path.is_file()
        exact_file(path, row)
    receipt = read(Path(data['records'][0]['path']))
    assert type(receipt['actual_exit']) is int and receipt['actual_exit'] == 0
    assert receipt['streams']['stdout.bin'] == {k: data['records'][1][k] for k in ('bytes', 'sha256')}
    assert receipt['streams']['stderr.bin'] == {k: data['records'][2][k] for k in ('bytes', 'sha256')}
    assert data['records'][2]['bytes'] == 0
    return data


def source_rows() -> list[dict]:
    actual = set()
    for path in HERE.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(HERE).as_posix()
        parts = rel.split('/')
        if rel == INDEX.name or parts[0] == 'test-output':
            continue
        if '__pycache__' in parts and path.suffix == '.pyc':
            continue
        assert not any(part in ('runs', 'transport-evidence') for part in parts), rel
        assert not (rel.startswith('review/independent-content-') or
                    rel.startswith('review/independent-staged-') or
                    rel.startswith('review/independent-remote-')), rel
        assert rel not in actual
        actual.add(rel)
    assert len(actual) == len({r.casefold() for r in actual})
    required = {'.gitattributes', '.gitignore', 'classify.py', 'self_check.py',
                'source_gate.py', 'make_custody.py', 'copy_classification_proofs.py',
                'classification-proof-custody.json', 'copy_root_publication_methods.py',
                'root-publication-method-custody.json', 'proof-write-originals.json',
                'prospective-contract.json', 'prospective-contract.md',
                'context-custody.json', 'parent-source-pairs.json',
                'raw-custody-map.json', 'preflight-custody-map.json',
                'README-publication.md', 'REPRODUCTION-postrun.md',
                'results-summary.json', 'publication-entry.json',
                'cli-scope-signoff-2026-10-08.md', 'make_evidence_index.py',
                'review/independent-classification-go-2026-10-08.json',
                'review/independent-classification-go-2026-10-08.md'}
    assert required <= actual, sorted(required - actual)
    context = {'preserved-context/' + name for name in (
        'owned-catalog-git-498.json.bytes', 'owned-catalog-local-498.json.bytes',
        'parent-independent-postrun-go.md.bytes', 'root-selection.json.bytes',
        'var07-author-no-go.md.bytes', 'var07-independent-no-go.md.bytes',
        'var09-independent-contract-go.md.bytes', 'var09-independent-feasibility.md.bytes')}
    development = {'preserved-development/' + name for name in (
        'author-proof-path-read-diagnostic.md',
        'classify-v1-before-turnround-order-note.md',
        'classify-v1-before-turnround-order.py.bytes',
        'make-custody-v1-note.md', 'make-custody-v1-preappend.py.bytes',
        'make-custody-v2-before-relocation-note.md',
        'make-custody-v2-before-relocation.py.bytes',
        'source-gate-v1-before-403-topology-note.md',
        'source-gate-v1-before-403-topology.py.bytes')}
    assert {r for r in actual if r.startswith('preserved-proof/')} == {
        f'preserved-proof/proof-{i:02d}.bytes' for i in range(36)}
    assert {r for r in actual if r.startswith('preserved-root-publication/')} == {
        f'preserved-root-publication/method-{i:02d}.bytes' for i in range(8)}
    assert {r for r in actual if r.startswith('review/')} == {
        'review/independent_classifier.py', 'review/independent_self_check.py',
        'review/preserved-independent-v1-initial-failure-clock.py.bytes',
        'review/preserved-self-check-v1-decoded-only.py.bytes',
        'review/preserved-self-check-v2-return-reason.py.bytes',
        'review/preserved-independent-v2-before-priority-station.py.bytes',
        'review/independent-method-static-go-2026-10-08.md',
        'review/independent-classification-go-2026-10-08.json',
        'review/independent-classification-go-2026-10-08.md'}
    expected = required | context | development | {
        f'preserved-proof/proof-{i:02d}.bytes' for i in range(36)} | {
        f'preserved-root-publication/method-{i:02d}.bytes' for i in range(8)} | {
        'review/independent_classifier.py', 'review/independent_self_check.py',
        'review/preserved-independent-v1-initial-failure-clock.py.bytes',
        'review/preserved-self-check-v1-decoded-only.py.bytes',
        'review/preserved-self-check-v2-return-reason.py.bytes',
        'review/preserved-independent-v2-before-priority-station.py.bytes',
        'review/independent-method-static-go-2026-10-08.md',
        'review/independent-classification-go-2026-10-08.json',
        'review/independent-classification-go-2026-10-08.md'}
    assert actual == expected, {'unindexed': sorted(actual - expected),
                                'missing': sorted(expected - actual)}
    return [{'path': rel, **pin((HERE / rel).read_bytes())} for rel in sorted(actual)]


def build() -> dict:
    gate = source_gate.verify('sealed')
    assert {k: gate[k] for k in ('parent_indexed_sources', 'parent_current_disk_git_pairs',
              'accepted_dependency_pairs', 'parent_manifest_roles', 'mandatory_raw_originals',
              'mandatory_preflight_originals', 'private_local_only_originals',
              'catalog_required_prefix', 'native_calls', 'accepted_checker_reruns')} == {
        'parent_indexed_sources': 401, 'parent_current_disk_git_pairs': 403,
        'accepted_dependency_pairs': 76, 'parent_manifest_roles': 456,
        'mandatory_raw_originals': 153, 'mandatory_preflight_originals': 15,
        'private_local_only_originals': 2, 'catalog_required_prefix': 498,
        'native_calls': 0, 'accepted_checker_reruns': 0}
    root_methods = copy_root_publication_methods.candidate(False)
    proofs = copy_classification_proofs.candidate(False)
    assert root_methods['records'] == 8 and proofs['records'] == 36
    write_proof = proof_write_originals()
    go = read(HERE / 'review/independent-classification-go-2026-10-08.json')
    assert pin((HERE / 'review/independent-classification-go-2026-10-08.json').read_bytes())['sha256'] == GO_SHA
    assert go['decision'] == 'GO_BOUNDED_CLASSIFICATION'
    assert type(go['new_native_runs']) is int and go['new_native_runs'] == 0
    assert type(go['accepted_parent_runs_repeated']) is int and go['accepted_parent_runs_repeated'] == 0
    entry = read(HERE / 'publication-entry.json')
    assert entry['publication_id'] == PUB_ID
    assert type(entry['new_native_runs']) is int and entry['new_native_runs'] == 0
    assert type(entry['accepted_parent_runs_repeated']) is int and entry['accepted_parent_runs_repeated'] == 0
    live = read(CATALOG)
    archive = read(HERE / 'preserved-context/owned-catalog-local-498.json.bytes')
    assert source_gate.typed_equal(live['entries'][:498], archive['entries'])
    matches = [row for row in live['entries'] if row['publication_id'] == PUB_ID]
    assert (len(live['entries']) == 498 and not matches) or (len(matches) == 1 and source_gate.typed_equal(matches[0], entry))
    raw = read(HERE / 'raw-custody-map.json')['records']
    pref = read(HERE / 'preflight-custody-map.json')['records']
    assert len(raw) == 153 and len(pref) == 15
    rows = source_rows()
    return {'schema': 'i04-var09-readonly-classification-evidence-index/v1',
            'publication_id': PUB_ID, 'decision': go['decision'],
            'classification_id': go['classification_id'],
            'accepted_parent_run_id': go['accepted_parent_run_id'],
            'new_native_runs': 0, 'accepted_parent_runs_repeated': 0,
            'source_count': len(rows), 'source_files': rows,
            'raw_count': len(raw), 'raw_files': raw,
            'preflight_original_count': len(pref), 'preflight_original_files': pref,
            'parent_source_pairs': 403, 'accepted_dependency_pairs': 76,
            'parent_prelaunch_roles': 456,
            'historical_catalog_prefix_entries': 498,
            'prior_full_parent_report_cells': 4044,
            'new_selected_report_behavior_values': 10,
            'new_selected_report_time_values': 10,
            'new_selected_report_row_identities': 10,
            'classification_log_lines': 118, 'classification_timed_records': 104,
            'owned_small_proof_copies': 36,
            'root_publication_method_copies': 8,
            'mandatory_proof_write_originals': write_proof['records'],
            'independent_classification_go_sha256': GO_SHA}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--candidate', type=Path)
    args = ap.parse_args()
    assert sum((args.dry, args.write, args.candidate is not None)) <= 1
    body = encode(build())
    if args.write:
        assert not INDEX.exists()
        INDEX.write_bytes(body)
    elif args.candidate is not None:
        assert not args.candidate.exists()
        args.candidate.write_bytes(body)
    elif INDEX.exists():
        assert INDEX.read_bytes() == body
    print(json.dumps({'schema': 'i04-var09-evidence-index-builder/v1',
                      'bytes': len(body), 'sha256': pin(body)['sha256'],
                      'source_count': json.loads(body)['source_count'],
                      'raw_count': 153, 'preflight_original_count': 15,
                      'wrote_canonical': args.write}, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
