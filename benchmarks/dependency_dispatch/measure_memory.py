#!/usr/bin/env python3
"""Separate macOS peak RSS probe; never mix instrumented runs into latency medians."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args();evidence=args.evidence.resolve()
    if platform.system()!='Darwin':parser.error('RSS units and flags are pinned to macOS /usr/bin/time -l')
    binary=ROOT/'rust/runtime/target/release/sim-engine-runtime'
    identity=json.loads((evidence/'identity.json').read_text())
    assert hashlib.sha256(binary.read_bytes()).hexdigest()==identity['runtime_sha256']
    rows=[]
    with tempfile.TemporaryDirectory() as tmp:
        for plan in sorted(evidence.glob('*/*/indexed-plan.json')):
            for level in ('full','summary'):
                for arm in ('scan','cache','candidates'):
                    values=[]
                    for repeat in range(3):
                        command=['/usr/bin/time','-l',str(binary),str(plan.with_name('scan-plan.json') if arm=='scan' else plan),
                                 str(Path(tmp)/'result.json'),'--seed','0','--observation-level',level]
                        if arm=='candidates':command.append('--dependency-dispatch')
                        result=subprocess.run(command,check=True,text=True,capture_output=True)
                        rss=next(int(line.strip().split()[0]) for line in result.stderr.splitlines()
                                 if line.strip().endswith('maximum resident set size'))
                        values.append(rss)
                    rows.append({'case':plan.parent.parent.name,'profile':plan.parent.name,'observation':level,
                                 'arm':arm,'peak_rss_bytes':values,'median_peak_rss_bytes':statistics.median(values)})
    report={'source_commit':identity['source_commit'],'runtime_sha256':identity['runtime_sha256'],
            'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'method':'macOS /usr/bin/time -l, separate processes, seed 0, 3 repeats; whole CLI peak includes output',
            'allocation_count':'not measured','records':rows}
    (evidence/'memory.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
