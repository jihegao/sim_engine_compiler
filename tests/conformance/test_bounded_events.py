"""Behavioral contracts on independent small IR compositions, not case IDs."""
import copy
import unittest

from sim_engine_compiler.ir.bounded import CORE, PLAN, PROFILE, Document, ticks
from sim_engine_compiler.integrations.spare_mvp.bounded import import_bounded_business
from sim_engine_compiler.domains.aircraft_support.bounded import lower_bounded, operation_contracts
from sim_engine_compiler.compiler.bounded_layout import compile_bounded
from sim_engine_compiler.domains.aircraft_support.bounded_runtime import BoundedAircraftRuntime
from sim_engine_compiler.reference.event_calendar import EventCalendar, CapacityLedger


def model(count=2, capacity=1):
    aircraft=[dict(id=f'asset-{i}',type='utility',turnround_hours=0,repair_mode='none',repair_hours=0,
                   remove_hours=0,fit_hours=0,item_repair_hours=0,stock_node=None,repair_node=None,
                   installed_item=None,pm=None) for i in range(count)]
    return {'schema_version':'aircraft-bounded-input/v1','semantic_profile':PROFILE,'model':{
        'horizon_hours':12,'report_interval_hours':.25,'rng_profile':'none','aircraft':aircraft,
        'resources':[{'id':'technician','capacity':capacity}],
        'processes':[{'id':'inspection','scalar_hours':.25,'steps':[{'id':'check','duration_hours':.25,'demands':{'technician':1}}]}],
        'missions':[dict(id='survey',start_hours=3,notice_hours=2.75,duration_hours=1,delay_hours=.5,
                         priority=1,requirements={'utility':count},process='inspection',depends_on=[])],
        'nodes':[],'routes':[],'external_events':[]}}


def compile_model(value, backend='python-bounded-reference'):
    core=lower_bounded(import_bounded_business(value))
    core=Document.from_dict(core.to_dict(),CORE)
    plan=compile_bounded(core,operations=operation_contracts(),backend=backend)
    return Document.from_dict(plan.to_dict(),PLAN)


def execute(value):
    return BoundedAircraftRuntime(compile_model(value)).run()


def hours(result, kind):
    return [e['hour'] for e in result['trace'] if e['kind']==kind]


def driver(operation,time=3.5,value=0):
    return dict(id='driver',time_hours=time,operation=operation,aircraft='asset-0',node=None,item=None,value_hours=value)


class BoundedEventsTests(unittest.TestCase):
    def test_resource_compositions_parallel_and_serial(self):
        self.assertEqual(hours(execute(model(capacity=2)),'mission_started'),[3])
        self.assertEqual(hours(execute(model(capacity=1)),'mission_started'),[3.25])

    def test_three_assets_reuse_same_operations(self):
        result=execute(model(count=3,capacity=2))
        self.assertEqual(hours(result,'mission_started'),[3.25])
        self.assertTrue(all(result['invariants'].values()))

    def test_equal_deadline_completes_before_dispatch_before_cancel(self):
        value=model();value['model']['missions'][0]['delay_hours']=.25
        result=execute(value)
        self.assertEqual(hours(result,'mission_started'),[3.25])
        self.assertEqual(hours(result,'mission_cancelled'),[])

    def test_subminute_cancel_releases_partial_work_and_invalidates_timer(self):
        value=model();value['model']['missions'][0]['delay_hours']=.249
        result=execute(value)
        self.assertEqual(hours(result,'mission_cancelled'),[3.249])
        self.assertEqual(hours(result,'mission_started'),[])
        self.assertEqual(len(hours(result,'work_finished')),1)
        self.assertEqual(result['terminal']['resources'][0]['used'],0)
        self.assertTrue(all(a['ready'] for a in result['terminal']['aircraft']))

    def test_joint_resource_request_has_no_partial_acquisition(self):
        value=model(1);m=value['model'];m['resources'].append(dict(id='equipment',capacity=0))
        m['processes'][0]['steps'][0]['demands']['equipment']=1
        result=execute(value)
        self.assertEqual(hours(result,'resource_acquired'),[])
        self.assertEqual(hours(result,'mission_cancelled'),[3.25])

    def test_explicit_serial_steps_override_scalar(self):
        value=model(1);p=value['model']['processes'][0];p['scalar_hours']=.75
        p['steps']=[dict(id='first',duration_hours=.1,demands={'technician':1}),dict(id='next',duration_hours=.2,demands={})]
        result=execute(value)
        self.assertEqual(hours(result,'work_started'),[2.75,2.85])
        self.assertEqual(hours(result,'preparation_finished'),[3.05])

    def test_plan_readonly_and_runstate_isolation(self):
        plan=compile_model(model());before=plan.to_dict();copy_of_payload=plan.payload
        copy_of_payload['horizon_ticks']=1
        first=BoundedAircraftRuntime(plan).run();second=BoundedAircraftRuntime(plan).run()
        self.assertEqual(plan.to_dict(),before);self.assertEqual(first,second)

    def test_priority_swap_changes_allocation_without_engine_change(self):
        value=model(1);m=value['model'];second=copy.deepcopy(m['missions'][0]);second.update(id='mapping',priority=2)
        m['missions'].append(second)
        a=execute(value);m['missions'][0]['priority']=3;b=execute(value)
        self.assertEqual([e['mission'] for e in a['trace'] if e['kind']=='mission_started'],['survey'])
        self.assertEqual([e['mission'] for e in b['trace'] if e['kind']=='mission_started'],['mapping'])

    def test_start_dependency_is_completion_gate(self):
        value=model(2,2);m=value['model'];m['missions'][0]['requirements']={'utility':1}
        second=copy.deepcopy(m['missions'][0]);second.update(id='mapping',start_hours=3.5,notice_hours=3.25,delay_hours=2,depends_on=['survey'])
        m['missions'].append(second)
        self.assertEqual(hours(execute(value),'mission_started'),[3,4])

    def test_calendar_pm_resets_at_completion(self):
        value=model(1);value['model']['aircraft'][0]['pm']=dict(id='periodic',clock='calendar',interval_hours=5,duration_hours=.5)
        result=execute(value)
        self.assertEqual(hours(result,'pm_started'),[5,10.5])
        self.assertEqual(hours(result,'pm_finished'),[5.5,11])

    def test_flight_pm_ignores_ground_calendar_time(self):
        value=model(1);m=value['model'];m['aircraft'][0]['pm']=dict(id='usage',clock='flight',interval_hours=2,duration_hours=.5)
        second=copy.deepcopy(m['missions'][0]);second.update(id='second',start_hours=8,notice_hours=7.75);m['missions'].append(second)
        self.assertEqual(hours(execute(value),'pm_started'),[9])

    def replacement(self,stock):
        value=model(1);m=value['model'];m['rng_profile']='external-events/v1'
        m['aircraft'][0].update(repair_mode='replacement',stock_node='store',repair_node='store',installed_item='mounted',remove_hours=.1,fit_hours=.2,item_repair_hours=.4)
        m['nodes']=[dict(id='store',items=['spare'] if stock else [])];m['external_events']=[driver('fault')]
        return value

    def test_replacement_with_spare_and_zero_stock_are_distinct_compositions(self):
        immediate=execute(self.replacement(True));waiting=execute(self.replacement(False))
        self.assertEqual(hours(immediate,'fit_finished'),[4.3])
        self.assertEqual(hours(waiting,'fit_finished'),[4.7])
        self.assertEqual(hours(waiting,'backorder_finished'),[4.5])
        self.assertEqual(waiting['terminal']['aircraft'][0]['installed'],'mounted')

    def test_transport_and_in_transfer_preserve_physical_identity(self):
        value=self.replacement(False);m=value['model'];m['aircraft'][0]['repair_node']='depot'
        m['nodes'].append(dict(id='depot',items=['spare']))
        m['routes']=[dict(id='to-base',source='depot',destination='store',duration_hours=.5),dict(id='to-depot',source='store',destination='depot',duration_hours=.5)]
        m['external_events'].append(dict(id='IN',time_hours=1,operation='in_transfer',aircraft=None,node='depot',item='incoming',value_hours=0))
        result=execute(value)
        self.assertEqual(hours(result,'backorder_finished'),[4.5])
        self.assertEqual(result['terminal']['aircraft'][0]['installed'],'spare')
        self.assertEqual(result['terminal']['stock'][1]['nominal'],2)
        self.assertEqual(result['physical_items']['mounted'],['stock',1])

    def test_scheduled_parameter_change_affects_later_repairs(self):
        value=model(1);m=value['model'];m['rng_profile']='external-events/v1';m['aircraft'][0].update(repair_mode='direct',repair_hours=.5)
        m['external_events']=[driver('fault'),dict(driver('set_repair_duration',time=1,value=.75),id='change')]
        self.assertEqual(hours(execute(value),'repair_finished'),[4.75])

    def test_in_progress_parameter_change_rejected(self):
        value=model(1);m=value['model'];m['rng_profile']='external-events/v1';m['aircraft'][0].update(repair_mode='direct',repair_hours=1)
        m['external_events']=[driver('fault'),dict(driver('set_repair_duration',time=4.2,value=.75),id='change')]
        with self.assertRaisesRegex(ValueError,'in-progress'):execute(value)

    def test_external_driver_state_mismatch_rejected(self):
        value=self.replacement(True);value['model']['external_events'][0]['time_hours']=1
        with self.assertRaisesRegex(ValueError,'flying healthy'):execute(value)

    def test_unknown_unit_profile_field_and_reference_rejected(self):
        patches=[lambda v:v.update(semantic_profile='legacy-minute-v1'),
                 lambda v:v['model'].update(horizon_minutes=20),
                 lambda v:v['model']['missions'][0].update(process='missing'),
                 lambda v:v['model']['resources'][0].update(capacity=True),
                 lambda v:v['model']['processes'][0].update(scalar_hours=float('nan'))]
        for patch in patches:
            v=model();patch(v)
            with self.assertRaises(ValueError):compile_model(v)

    def test_cycles_duplicate_ids_and_duplicate_item_ownership_rejected(self):
        v=model();v['model']['missions'][0]['depends_on']=['survey']
        with self.assertRaisesRegex(ValueError,'cyclic'):compile_model(v)
        v=model();v['model']['aircraft'][1]['id']='asset-0'
        with self.assertRaisesRegex(ValueError,'duplicate'):compile_model(v)
        v=self.replacement(True);v['model']['nodes'][0]['items'].append('mounted')
        with self.assertRaisesRegex(ValueError,'identity reused'):compile_model(v)

    def test_unsupported_backend_and_operation_rejected(self):
        with self.assertRaisesRegex(ValueError,'backend'):compile_model(model(),'rust-runtime')
        p=compile_model(model());value=p.payload;value['operations'][0]['name']='custom-code'
        with self.assertRaisesRegex(ValueError,'operation'):BoundedAircraftRuntime(Document.create(PLAN,value))

    def test_invalid_dense_plan_reference_rejected(self):
        p=compile_model(model());value=p.payload;value['tables']['missions'][0]['process']=999
        with self.assertRaisesRegex(ValueError,'dense reference'):BoundedAircraftRuntime(Document.create(PLAN,value))

    def test_persisted_plan_checksum_tampering_rejected(self):
        value=compile_model(model()).to_dict();value['payload']['horizon_ticks']+=1
        with self.assertRaisesRegex(ValueError,'checksum'):Document.from_dict(value,PLAN)

    def test_atomic_ledger_rejects_double_release_and_duplicate_operand(self):
        ledger=CapacityLedger([2,0]);self.assertFalse(ledger.acquire('x',[(0,1),(1,1)]));self.assertEqual(ledger.used,[0,0])
        self.assertTrue(ledger.acquire('x',[(0,1)]));ledger.release('x')
        with self.assertRaises(ValueError):ledger.release('x')
        with self.assertRaises(ValueError):ledger.acquire('y',[(0,1),(0,1)])

    def test_calendar_budget_and_unknown_operation_rejected(self):
        calendar=None
        def loop(_):calendar.schedule(calendar.now,0,'loop',None)
        calendar=EventCalendar({'loop':loop},100,event_budget=4);calendar.schedule(0,0,'loop',None)
        with self.assertRaisesRegex(ValueError,'budget'):calendar.run()
        with self.assertRaisesRegex(ValueError,'unsupported'):calendar.schedule(0,0,'unknown',None)


if __name__=='__main__':unittest.main()
