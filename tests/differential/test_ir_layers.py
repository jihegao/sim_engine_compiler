from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sim_engine_compiler.compiler import compile_aircraft_support, CompilationError
from sim_engine_compiler.compiler.layout import compile_core, revision_impact, lineage
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR, digest
from sim_engine_compiler.reference import SimpyReferenceRuntime

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT/'tests/fixtures/synthetic'
CASES = [FIXTURES/name for name in ('b1-daily-operations.json','b2-failure-repair.json','b2-preventive-maintenance.json','b3-upstream-transport.json')]
CASES.append(ROOT/'tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json')


class PersistedIRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(['cargo','build','--quiet','--locked','--release','--manifest-path',str(ROOT/'rust/compiler/Cargo.toml'),'--bin','sim_ir_compiler'],check=True,cwd=ROOT)
        cls.binary = ROOT/'rust/compiler/target/release/sim_ir_compiler'

    def invoke(self,source,destination,stage,profile='legacy-minute-v1'):
        completed = subprocess.run([str(self.binary),str(source),str(destination),'--output-kind',stage,'--semantic-profile',profile],capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        return json.loads(destination.read_text())

    def test_all_fixtures_cross_language_artifacts_and_disk_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            for source in CASES:
                for profile in ('legacy-minute-v1','event-time-v2'):
                    with self.subTest(source=source.name,profile=profile):
                        inputs=json.loads(source.read_text())
                        business=import_business_ir(inputs,semantic_profile=profile)
                        self.assertEqual(business.canonical_view(),inputs)
                        core=lower_business(business)
                        expected=json.loads(json.dumps(compile_aircraft_support(inputs,semantic_profile=profile).to_dict()))
                        self.assertEqual(self.invoke(source,tmp/'rust-business.json','business',profile),business.to_dict())
                        self.assertEqual(self.invoke(source,tmp/'rust-core.json','core',profile),core.to_dict())
                        self.assertEqual(self.invoke(tmp/'rust-business.json',tmp/'from-business.json','plan'),expected)
                        self.assertEqual(self.invoke(tmp/'rust-core.json',tmp/'from-core.json','plan'),expected)
                        restored=CoreIR.from_dict(json.loads((tmp/'rust-core.json').read_text()))
                        self.assertEqual(json.loads(json.dumps(compile_core(restored).to_dict())),expected)
                        # A fresh Python process receives only the Core file.
                        subprocess.run([sys.executable,str(ROOT/'scripts/compile_ir.py'),str(tmp/'rust-core.json'),str(tmp/'python-reloaded.json')],check=True,capture_output=True,cwd=ROOT)
                        self.assertEqual(json.loads((tmp/'python-reloaded.json').read_text()),expected)

    def test_business_rule_edit_is_traceable_and_changes_execution(self):
        inputs=json.loads(CASES[0].read_text())
        business=import_business_ir(inputs)
        before=lower_business(business)
        edited=copy.deepcopy(business.payload)
        entity=edited['sections']['support_activities']['collections']['activities'][0]
        entity['definition']['jobs'][0]['durationMinutes']=30
        after=lower_business(BusinessIR.create(edited))
        impact=revision_impact(before,after)
        self.assertTrue(any(c.get('after_plan_path')=='activities[0].steps[0]' and c['source_path']=='support_activities.activities[0].jobs[0]' for c in impact['changes']))
        old_plan,new_plan=compile_core(before),compile_core(after)
        self.assertNotEqual(old_plan.fingerprint,new_plan.fingerprint)
        self.assertEqual(new_plan.activities[0].steps[0].duration_minutes,30)
        self.assertNotEqual(SimpyReferenceRuntime(old_plan).run()['trace'],SimpyReferenceRuntime(new_plan).run()['trace'])

    def test_core_edit_does_not_require_business_or_canonical_input(self):
        core=lower_business(import_business_ir(json.loads(CASES[0].read_text())))
        payload=copy.deepcopy(core.payload)
        payload['tables']['activities'][0]['steps'][0]['attributes']['duration_minutes']=9
        edited=CoreIR.create(payload)
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'core.json';source.write_text(json.dumps(edited.to_dict()))
            rust=self.invoke(source,tmp/'plan.json','plan')
            self.assertEqual(rust['activities'][0]['steps'][0]['duration_minutes'],9)
            self.assertEqual(rust,json.loads(json.dumps(compile_core(edited).to_dict())))

    def test_symbol_references_are_relocated_by_layout(self):
        core=lower_business(import_business_ir(json.loads(CASES[3].read_text())))
        payload=copy.deepcopy(core.payload)
        payload['tables']['resource_nodes'].reverse()
        edited=CoreIR.create(payload)
        plan=compile_core(edited)
        for activity,row in zip(plan.activities,payload['tables']['activities']):
            self.assertEqual(plan.resource_nodes[activity.resource_node_index].node_id,row['references']['resource_node_index'])

    def test_contract_and_aircraft_layout_changes_are_reported(self):
        before=lower_business(import_business_ir(json.loads(CASES[0].read_text())))
        for field,value in (('duration_minutes',61),('semantic_profile','event-time-v2')):
            payload=copy.deepcopy(before.payload);payload['contract'][field]=value
            after=CoreIR.create(payload)
            self.assertNotEqual(compile_core(before).fingerprint,compile_core(after).fingerprint)
            changes=revision_impact(before,after)['changes']
            self.assertTrue(any(c.get('kind')=='contract' and c.get('field')==field for c in changes))
        payload=copy.deepcopy(before.payload);payload['tables']['aircraft'].reverse()
        after=CoreIR.create(payload)
        self.assertNotEqual(compile_core(before).fingerprint,compile_core(after).fingerprint)
        changes=revision_impact(before,after)['changes']
        moved=[c for c in changes if c.get('kind')=='layout' and c['core_symbol'].startswith('aircraft/')]
        self.assertEqual(len(moved),2)
        self.assertTrue(all(c['before_plan_path']!=c['after_plan_path'] for c in moved))

    def test_aircraft_origins_survive_core_reordering_and_reload(self):
        business=import_business_ir(json.loads(CASES[0].read_text()))
        core=lower_business(business)
        payload=copy.deepcopy(core.payload);payload['tables']['aircraft'].reverse()
        after=CoreIR.from_dict(CoreIR.create(payload).to_dict())
        mapping=lineage(business,after,compile_core(after))['symbols']['aircraft']
        self.assertEqual(mapping[0],{'id':'F35-02','source_path':'aircraft.assets[1]','plan_path':'aircraft[0]'})
        self.assertEqual(mapping[1],{'id':'F35-01','source_path':'aircraft.assets[0]','plan_path':'aircraft[1]'})

    def test_generated_aircraft_origin_does_not_invent_an_asset_record(self):
        inputs=json.loads(CASES[0].read_text());inputs['aircraft']['assets']=[]
        core=lower_business(import_business_ir(inputs))
        self.assertEqual([r['source_path'] for r in core.payload['tables']['aircraft']],
                         ['aircraft.fleet_count','aircraft.fleet_count'])

    def test_preventive_symbols_survive_aircraft_reordering(self):
        inputs=json.loads(CASES[2].read_text())
        a=copy.deepcopy(inputs['aircraft']['assets'][0]);a['tail_number']='F35-02'
        inputs['aircraft']['assets'].append(a)
        inputs['aircraft'].update(fleet_count=2,initial_ready=2)
        before=lower_business(import_business_ir(inputs))
        inputs['aircraft']['assets'].reverse()
        after=lower_business(import_business_ir(inputs))
        owners=lambda c:{r['id']:r['references'] for r in c.payload['tables']['preventive_cycles']}
        self.assertEqual(owners(before),owners(after))
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'inputs.json';source.write_text(json.dumps(inputs))
            self.assertEqual(self.invoke(source,Path(tmp)/'core.json','core'),after.to_dict())

    def test_cycle_identity_survives_insert_reorder_and_parameter_edit_in_both_languages(self):
        inputs=json.loads(CASES[2].read_text())
        first=inputs['aircraft']['assets'][0]['preventive_cycles'][0]
        first['id']='calendar-check'
        second=copy.deepcopy(first);second.pop('id');second['cycle_id']='flight-check'
        inputs['aircraft']['assets'][0]['preventive_cycles'].append(second)
        before=lower_business(import_business_ir(inputs))
        edited=copy.deepcopy(inputs)
        cycles=edited['aircraft']['assets'][0]['preventive_cycles'];cycles.reverse()
        cycles[0]['thresholds']['flight_hours']=42
        inserted=copy.deepcopy(cycles[1]);inserted['id']='new-check';cycles.insert(0,inserted)
        another=copy.deepcopy(edited['aircraft']['assets'][0]);another['tail_number']='F35-00'
        edited['aircraft']['assets'].insert(0,another)
        edited['aircraft'].update(fleet_count=2,initial_ready=2)
        after=lower_business(import_business_ir(edited))
        old={r['id']:r for r in before.payload['tables']['preventive_cycles']}
        new={r['id']:r for r in after.payload['tables']['preventive_cycles']}
        self.assertTrue(old.keys() <= new.keys())
        for symbol,row in old.items():
            self.assertEqual(row['references'],new[symbol]['references'])
            self.assertNotEqual(row['source_path'],new[symbol]['source_path'])
        changes=revision_impact(before,after)['changes']
        self.assertTrue(any(c.get('kind')=='layout' and c['core_symbol'].startswith('preventive_cycles/') for c in changes))
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            for data,core in ((inputs,before),(edited,after)):
                source=tmp/'inputs.json';source.write_text(json.dumps(data))
                rust=self.invoke(source,tmp/'core.json','core')
                self.assertEqual(rust,core.to_dict())
                self.assertEqual(self.invoke(tmp/'core.json',tmp/'plan.json','plan'),
                    json.loads(json.dumps(compile_core(core).to_dict())))

    def test_ambiguous_cycle_identity_is_rejected_in_both_languages(self):
        inputs=json.loads(CASES[2].read_text())
        cycles=inputs['aircraft']['assets'][0]['preventive_cycles']
        cycles.append(copy.deepcopy(cycles[0]))
        with self.assertRaises(CompilationError):lower_business(import_business_ir(inputs))
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'inputs.json';source.write_text(json.dumps(inputs))
            result=subprocess.run([str(self.binary),str(source),str(Path(tmp)/'out.json')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('duplicate',result.stderr)

    def test_business_reorder_keeps_original_aircraft_origins(self):
        business=import_business_ir(json.loads(CASES[0].read_text()))
        payload=copy.deepcopy(business.payload)
        payload['sections']['aircraft']['collections']['assets'].reverse()
        reordered=BusinessIR.create(payload);core=lower_business(reordered)
        self.assertEqual(core.payload['tables']['aircraft'][0]['source_path'],'aircraft.assets[1]')
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'business.json';source.write_text(json.dumps(reordered.to_dict()))
            self.assertEqual(self.invoke(source,Path(tmp)/'core.json','core'),core.to_dict())

    def test_missing_origin_forged_cycle_owner_and_old_core_version_fail_closed(self):
        core=lower_business(import_business_ir(json.loads(CASES[2].read_text())))
        with tempfile.TemporaryDirectory() as tmp:
            for edit in (lambda p:p['tables']['aircraft'][0].pop('source_path'),
                         lambda p:p['tables']['preventive_cycles'][0]['cycle_key'].__setitem__(1,'another-cycle')):
                payload=copy.deepcopy(core.payload);edit(payload)
                with self.assertRaises(CompilationError):CoreIR.create(payload)
                envelope={'version':core.to_dict()['version'],'payload':payload}
                envelope['fingerprint']=digest(envelope)
                source=Path(tmp)/'invalid.json';source.write_text(json.dumps(envelope))
                result=subprocess.run([str(self.binary),str(source),str(Path(tmp)/'out.json')],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('panicked',result.stderr)
        old=core.to_dict();old['version']='simulation-core-ir/v1'
        old['fingerprint']=digest({k:v for k,v in old.items() if k!='fingerprint'})
        with self.assertRaises(CompilationError):CoreIR.from_dict(old)

    def test_rejects_resealed_unknown_ops_dependencies_units_references_and_schema(self):
        core=lower_business(import_business_ir(json.loads(CASES[0].read_text())))
        edits=[lambda p:p['tables']['activities'][0].update(steps=None),
               lambda p:p['tables']['activities'][0]['steps'][0].update(attributes=[]),
               lambda p:p['tables']['activities'][0]['steps'][0].update(predecessors=[{}]),
               lambda p:p['operations'][0].update(operation='unknown/v1'),
               lambda p:p['operations'][0].update(reads=[]),
               lambda p:p['operations'][0].update(backends=[]),
               lambda p:p['tables']['activities'][0]['references'].update(resource_node_index='missing'),
               lambda p:p['tables']['activities'][0]['steps'][0]['attributes'].update(duration_minutes='3 hours'),
               lambda p:p['tables']['activities'][0]['steps'][0]['attributes'].update(duration_minutes=-3),
               lambda p:p['tables']['activities'][0]['steps'][0]['attributes'].update(arbitrary_expression='run()'),
               lambda p:p['tables']['activities'][0]['steps'][0]['dependencies'].update(wakeups=[]),
               lambda p:p['contract'].update(phases=list(reversed(p['contract']['phases'])))]
        with tempfile.TemporaryDirectory() as tmp:
            for i,edit in enumerate(edits):
                payload=copy.deepcopy(core.payload);edit(payload)
                with self.subTest(i=i):
                    with self.assertRaises(CompilationError): CoreIR.create(payload)
                    envelope={'version':core.to_dict()['version'],'payload':payload}
                    envelope['fingerprint']=digest(envelope)
                    source=Path(tmp)/'invalid.json';source.write_text(json.dumps(envelope))
                    result=subprocess.run([str(self.binary),str(source),str(Path(tmp)/'out.json')],capture_output=True,text=True)
                    self.assertNotEqual(result.returncode,0)
                    self.assertNotIn('panicked',result.stderr)

    def test_checksums_and_backend_gaps_fail_closed(self):
        business=import_business_ir(json.loads(CASES[0].read_text()))
        raw=business.to_dict();raw['fingerprint']='0'*64
        with self.assertRaises(CompilationError):BusinessIR.from_dict(raw)
        core=lower_business(business);raw=core.to_dict();raw['payload']['contract']['duration_minutes']=123
        with self.assertRaises(CompilationError):CoreIR.from_dict(raw)
        with self.assertRaises(CompilationError):compile_core(core,backend='unimplemented')
