from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT/'tests/fixtures/synthetic'


class DependencyDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(['cargo','build','--quiet','--locked','--release','--manifest-path',str(ROOT/'rust/runtime/Cargo.toml'),'--bin','sim-engine-runtime'],check=True,cwd=ROOT)
        cls.binary=ROOT/'rust/runtime/target/release/sim-engine-runtime'
        cls.plugin=Path(os.environ.get('SIM_ENGINE_MLIR_PLUGIN_DIR',ROOT/'tools/mlir_dispatch/build-make'))
        cls.mlir=Path(os.environ.get('SIM_ENGINE_MLIR_OPT','/opt/homebrew/opt/llvm/bin/mlir-opt'))
        if not cls.mlir.is_file() or not (cls.plugin/'SimResourceDispatchPass.so').is_file():
            if os.environ.get('SIM_ENGINE_REQUIRE_MLIR') == '1':
                raise AssertionError('candidate dispatch acceptance requires the pinned current-checkout MLIR plugin')
            raise unittest.SkipTest('candidate dispatch requires MLIR 23.1.1 plugins')

    def compile(self,inputs,directory,profile):
        source=directory/'inputs.json';source.write_text(json.dumps(inputs))
        plan=directory/'indexed.json'
        subprocess.run([sys.executable,str(ROOT/'scripts/compile_mlir_execution_plan.py'),str(source),str(plan),'--semantic-profile',profile,'--plugin-dir',str(self.plugin),'--mlir-opt',str(self.mlir)],check=True,capture_output=True,cwd=ROOT)
        raw=json.loads(plan.read_text());self.assertEqual(raw['resource_dispatch_index']['schema_version'],'resource-dispatch-index/v2')
        raw.pop('resource_dispatch_index');baseline=directory/'baseline.json';baseline.write_text(json.dumps(raw))
        return baseline,plan

    def run_arm(self,plan,directory,seed,level,candidates=False,until=None):
        output=directory/'result.json';profile=directory/'profile.json'
        command=[str(self.binary),str(plan),str(output),'--seed',str(seed),'--observation-level',level,'--profile-output',str(profile)]
        if candidates:command.append('--dependency-dispatch')
        if until is not None:command.extend(['--until',str(until)])
        completed=subprocess.run(command,capture_output=True,text=True,cwd=ROOT)
        self.assertEqual(completed.returncode,0,completed.stderr)
        return json.loads(output.read_text()),json.loads(profile.read_text())['profile']

    def assert_three_arms(self,inputs,seeds=(0,),untils=(None,)):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            for profile in ('legacy-minute-v1','event-time-v2'):
                baseline,indexed=self.compile(inputs,tmp,profile)
                for seed in seeds:
                    for level in ('full','summary'):
                        for until in untils:
                            with self.subTest(profile=profile,seed=seed,level=level,until=until):
                                old,p0=self.run_arm(baseline,tmp,seed,level,until=until)
                                cached,p1=self.run_arm(indexed,tmp,seed,level,until=until)
                                candidate,p2=self.run_arm(indexed,tmp,seed,level,True,until)
                                self.assertEqual(old,cached)
                                self.assertEqual(old,candidate)
                                self.assertLessEqual(p2['resource_dispatch_guard_evaluations'],p0['resource_dispatch_guard_evaluations'])

    def test_f35_seeds_profiles_and_observations(self):
        inputs=json.loads((ROOT/'tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json').read_text())
        self.assert_three_arms(inputs,seeds=(0,1,7))

    def test_rust_aot_persisted_core_feeds_mlir(self):
        subprocess.run(['cargo','build','--quiet','--locked','--release','--manifest-path',
            str(ROOT/'rust/compiler/Cargo.toml'),'--bin','sim_ir_compiler'],check=True,cwd=ROOT)
        source=ROOT/'tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json'
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            for profile in ('legacy-minute-v1','event-time-v2'):
                _,indexed=self.compile(json.loads(source.read_text()),tmp,profile)
                subprocess.run([str(ROOT/'rust/compiler/target/release/sim_ir_compiler'),
                    str(source),str(tmp/'rust-core.json'),'--output-kind','core',
                    '--semantic-profile',profile],check=True,capture_output=True)
                subprocess.run([sys.executable,str(ROOT/'scripts/compile_mlir_execution_plan.py'),
                    str(tmp/'rust-core.json'),str(tmp/'rust-indexed.json'),
                    '--plugin-dir',str(self.plugin),'--mlir-opt',str(self.mlir)],check=True,capture_output=True)
                self.assertEqual(json.loads(indexed.read_text()),json.loads((tmp/'rust-indexed.json').read_text()))

    def test_existing_failure_preventive_transport_and_time_boundaries(self):
        for name in ('b1-daily-operations.json','b2-failure-repair.json','b2-preventive-maintenance.json','b3-upstream-transport.json'):
            with self.subTest(case=name):
                self.assert_three_arms(json.loads((FIXTURES/name).read_text()),untils=(None,1,3,15,20,21))

    def contention(self,stock=False):
        inputs=json.loads((FIXTURES/'b1-daily-operations.json').read_text())
        base=inputs['aircraft']['assets'][0]
        inputs['aircraft']['assets']=[{**copy.deepcopy(base),'tail_number':f'AC-{i:03d}'} for i in range(16)]
        inputs['aircraft']['fleet_count']=16;inputs['aircraft']['initial_ready']=16
        for basic in inputs['mission_profile']['basic_missions']:
            basic['equipmentQuantity']=16;basic['minRequiredSorties']=1
        for composite in inputs['mission_profile']['composite_tasks']:
            for item in composite['taskItems']:item['equipmentQuantity']=16
        if stock:
            inputs['support_network']['nodes'][0]['inventory']={}
            inputs['support_activities']['activities'][0]['jobs'][0]['spare']='filter,1'
        return inputs

    def test_dense_capacity_contention_preserves_every_delay_event(self):
        self.assert_three_arms(self.contention())

    def shared_remote_pools(self, kinds):
        """Two destinations compete for one unit at each actual supplier."""
        inputs=json.loads((FIXTURES/'b2-preventive-maintenance.json').read_text())
        asset=inputs['aircraft']['assets'][0]
        inputs['aircraft']['assets']=[copy.deepcopy(asset),copy.deepcopy(asset)]
        inputs['aircraft'].update(fleet_count=2,initial_ready=2)
        activity=inputs['support_activities']['activities'][0]
        inputs['support_activities']['activities']=[]
        nodes=[];routes=[]
        for index,tail in enumerate(('F35-01','F35-02')):
            destination=f'line-{index}'
            a=inputs['aircraft']['assets'][index];a['tail_number']=tail
            a['preventive_cycles'][0]['activity_id']=f'preventive-{tail}'
            work=copy.deepcopy(activity)
            work.update(id=f'preventive-{tail}',resource_id=destination)
            work['jobs'][0].update(durationMinutes=2,personnel=[{'quantity':1}],equipment=[{'quantity':1}])
            inputs['support_activities']['activities'].append(work)
            nodes.append({'id':destination,'name':destination,'inventory':{},
                'personnel_capacity':0 if 'personnel' in kinds else 1,
                'equipment_capacity':0 if 'equipment' in kinds else 1})
            for kind in kinds:
                routes.append({'id':f'{kind}-{destination}',
                    'from_organization_node_id':f'{kind}-pool',
                    'to_organization_node_id':destination,'product_id':kind,
                    'capacity':1,'transport_minutes':1,'priority':1})
        for kind in kinds:
            nodes.append({'id':f'{kind}-pool','name':kind,'inventory':{},
                'personnel_capacity':int(kind=='personnel'),
                'equipment_capacity':int(kind=='equipment')})
        inputs['support_network']={'nodes':nodes,'organization_graph':{
            'runtime_mode':'vertical','nodes':[{'id':n['id']} for n in nodes],
            'parent_edges':[{'from_node_id':r['from_organization_node_id'],
                'to_node_id':r['to_organization_node_id']} for r in routes],
            'lateral_edges':[],'resource_ownership':[],'transport_policies':routes}}
        return inputs

    def test_shared_suppliers_release_wakes_other_destination(self):
        for kinds in (('personnel',),('equipment',),('personnel','equipment')):
            with self.subTest(kinds=kinds):
                inputs=self.shared_remote_pools(kinds)
                self.assert_three_arms(inputs,untils=(None,2,3,4,5,6))
                with tempfile.TemporaryDirectory() as tmp:
                    tmp=Path(tmp);baseline,indexed=self.compile(inputs,tmp,'legacy-minute-v1')
                    result,_=self.run_arm(indexed,tmp,0,'full',True)
                    completed={e['entity'] for e in result['trace'] if e['kind']=='preventive_completed'}
                    self.assertEqual(len(completed),2)

    def test_shortage_candidates_drop_without_hiding_replay_work(self):
        inputs=self.contention(stock=True)
        self.assert_three_arms(inputs)
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,indexed=self.compile(inputs,tmp,'legacy-minute-v1')
            expected,p1=self.run_arm(indexed,tmp,0,'full')
            actual,p2=self.run_arm(indexed,tmp,0,'full',True)
            self.assertEqual(expected,actual)
            self.assertLess(p2['resource_dispatch_candidate_visits'],p1['resource_dispatch_candidate_visits'])
            self.assertEqual(p2['resource_dispatch_replay_visits'],0)

    def remote_contention(self):
        inputs=self.contention()
        local=inputs['support_network']['nodes'][0]
        local.update(personnel_capacity=0,equipment_capacity=0)
        inputs['support_network']['nodes'].append({
            'id':'remote','name':'Remote pool','personnel_capacity':2,
            'equipment_capacity':2,'inventory':{}})
        inputs['support_network']['organization_graph']={
            'runtime_mode':'vertical',
            'nodes':[{'id':'remote','parent_id':None},{'id':'flight-line','parent_id':'remote'}],
            'parent_edges':[{'from_node_id':'remote','to_node_id':'flight-line'}],
            'lateral_edges':[], 'resource_ownership':[],
            'transport_policies':[{'id':'remote-capacity','from_organization_node_id':'remote',
                'to_organization_node_id':'flight-line','product_id':'*',
                'capacity':1,'transport_minutes':2,'priority':1}]}
        return inputs

    def test_remote_capacity_arrival_release_and_cancel_wakeups(self):
        inputs=self.remote_contention()
        self.assert_three_arms(inputs,seeds=(0,7),untils=(None,12,15,20,21))
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,indexed=self.compile(inputs,tmp,'legacy-minute-v1')
            result,_=self.run_arm(indexed,tmp,0,'full',True)
            events={event['kind'] for event in result['trace']}
            self.assertIn('organization_resource_arrived',events)
            self.assertIn('mission_cancelled',events)
            raw=json.loads(indexed.read_text());index=raw['resource_dispatch_index']
            remote=next(n['index'] for n in raw['resource_nodes'] if n['node_id']=='remote')
            original=len(index['dependencies'])
            index['dependencies']=[d for d in index['dependencies'] if not
                (d['key']['node_index']==remote and d['key']['kind']=='personnel_capacity')]
            self.assertLess(len(index['dependencies']),original)
            index['candidate_rule_count']=sum(len(d['candidates']) for d in index['dependencies'])
            index.pop('checksum')
            from sim_engine_compiler.ir.layers import digest
            index['checksum']=digest(index)
            indexed.write_text(json.dumps(raw))
            completed=subprocess.run([str(self.binary),str(indexed),str(tmp/'invalid.json'),
                '--dependency-dispatch'],capture_output=True,text=True)
            self.assertNotEqual(completed.returncode,0)
            self.assertIn('omits a required resource dependency',completed.stderr)

    def test_candidate_mode_rejects_missing_or_old_index(self):
        # Old snapshot has pre-MC metadata; isolate the schema check using a current
        # index with local-only dependencies (B1 has no remote capacity routes).
        inputs=json.loads((FIXTURES/'b1-daily-operations.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);baseline,indexed=self.compile(inputs,tmp,'legacy-minute-v1')
            raw=json.loads(indexed.read_text());index=raw['resource_dispatch_index'];index['schema_version']='resource-dispatch-index/v1'
            index.pop('checksum')
            from sim_engine_compiler.ir.layers import digest
            index['checksum']=digest(index)
            old=tmp/'v1.json';old.write_text(json.dumps(raw))
            for plan in (baseline,old):
                result=subprocess.run([str(self.binary),str(plan),str(tmp/'out.json'),'--dependency-dispatch'],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('resource-dispatch-index/v2',result.stderr)

    def test_batch_order_and_duplicate_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,plan=self.compile(self.contention(),tmp,'event-time-v2')
            results=[]
            for candidates,threads in ((False,1),(True,1),(True,3)):
                output=tmp/'batch.json';command=[str(self.binary),str(plan),str(output),'--seeds','7,0,7,1','--worker-threads',str(threads)]
                if candidates:command.append('--dependency-dispatch')
                subprocess.run(command,check=True,capture_output=True)
                result=json.loads(output.read_text());results.append(result['samples'])
                self.assertEqual([s['sample_index'] for s in result['samples']],[0,1,2,3])
            self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2])
