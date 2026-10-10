#!/usr/bin/env python3
"""Run the fixed untimed verification suites and persist the admission receipt."""
import argparse, json, os, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];os.chdir(root);sys.path[:0]=[str(root),str(root/'src')]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plugin-dir',type=Path,required=True)
parser.add_argument('--mlir-opt',type=Path,required=True)
args=parser.parse_args()
from benchmarks.three_arm_v1.admission import BUILD_COMMAND,build_source_files,sha,expected_verification_commands,expected_verification_environment,_git_source_snapshot,_require_source_unchanged
out=root/'runs/three-arm-v1';out.mkdir(parents=True,exist_ok=True)
if (out/'regression-receipt.json').exists():raise SystemExit('Preserve the existing receipt before a new verification run')
environment=expected_verification_environment(args.plugin_dir.resolve(),args.mlir_opt.resolve())
env={**os.environ,'PYTHONPATH':'src',**environment['variables']}

head=_git_source_snapshot()
def run(label,cmd):
 print('START',label,flush=True)
 log=out/(label+'.log')
 with log.open('w') as f:
  f.write('command='+json.dumps(cmd)+'\n');f.flush()
  completed=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=900)
 print('END',label,'exit',completed.returncode,flush=True)
 if completed.returncode:raise SystemExit('Verification failed: '+label)
 return {'id':label,'command':cmd,'passed':True,'exit_code':0,'log_path':str(log)}
for label in ['build','rust-unit','dispatch-regression','ir-reuse','admission-controls','driver-controls']:
 if (out/(label+'.log')).exists():raise SystemExit('Preserve prior verification log before rerun: '+label)
build=run('build',BUILD_COMMAND)
build.update(source_commit=head,rustc_vv=subprocess.check_output(['rustc','+1.90.0','-Vv'],text=True).strip(),source_files=build_source_files(),binaries={name:{'path':str(root/'rust/runtime/target/release'/name),'sha256':sha(root/'rust/runtime/target/release'/name)} for name in ['sim-engine-runtime','stage-c-benchmark']})
python=str(root/'.venv/bin/python')
commands=expected_verification_commands(python,args.plugin_dir.resolve(),args.mlir_opt.resolve())
checks=[run(label,command) for label,command in commands.items()]
# Persist Business IR edits and bind the exact serialized artifacts.
from benchmarks.three_arm_v1.workloads import persist_ir_reuse_artifacts
persist_ir_reuse_artifacts(out/'reuse')
raw=[Path(c['log_path']) for c in checks+[build]]+list((out/'reuse').rglob('*'))
raw=[p for p in raw if p.is_file()]
receipt={'schema_version':'three-arm-regression-receipt/v1','status':'passed','source_commit':head,'checks':checks,'build':build,'environment':environment,'raw_files':{str(p):sha(p) for p in raw}}
_require_source_unchanged(head)
(out/'regression-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('ALL VERIFICATION PASSED',flush=True)
