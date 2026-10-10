"""Behavioral contracts on independent small IR compositions, not case IDs."""
import copy
import unittest

from sim_engine_compiler.ir.bounded import CORE, PLAN, PROFILE, TICKS_PER_HOUR, Document, ticks
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


def state_at(result, hour):
    return next(row['state'] for row in result['snapshots'] if row['time_ticks']==ticks(hour))


def occupancy_integrals(result):
    """Integrate observable counts independently of the report interval."""
    total={key:0 for key in ('flying','ready','assigned','crew','stock','backorders','jobs')}
    for row, following in zip(result['snapshots'],result['snapshots'][1:]):
        duration=following['time_ticks']-row['time_ticks'];state=row['state']
        counts={'flying':sum(a['state']=='flying' for a in state['aircraft']),
                'ready':sum(a['ready'] for a in state['aircraft']),
                'assigned':sum(a['assigned'] for a in state['aircraft']),
                'crew':sum(r['used'] for r in state['resources']),
                'stock':sum(n['on_hand'] for n in state['stock']),
                'backorders':state['backorders'],'jobs':state['active_jobs']}
        for key,count in counts.items():total[key]+=duration*count
    return total


class BoundedEventsTests(unittest.TestCase):
    def test_report_grid_is_inclusive_sorted_unique_and_retains_transitions(self):
        for interval in (.25,.5,3):
            with self.subTest(interval=interval):
                value=model(1);value['model']['report_interval_hours']=interval
                result=execute(value);times=[r['time_ticks'] for r in result['snapshots']]
                self.assertEqual(times,sorted(set(times)))
                self.assertTrue(set(range(0,ticks(12)+1,ticks(interval))).issubset(times))
                self.assertIn(ticks(2.75),times)
                self.assertEqual(times[0],0);self.assertEqual(times[-1],ticks(12))
                self.assertEqual(state_at(result,12),result['terminal'])

    def test_report_boundary_observes_settled_completion_launch_and_cancellation(self):
        value=model();value['model'].update(horizon_hours=4.25)
        value['model']['missions'][0]['delay_hours']=.25
        result=execute(value)
        self.assertEqual([a['state'] for a in state_at(result,3)['aircraft']],['prepared','preparing'])
        self.assertEqual(state_at(result,3)['resources'][0]['used'],1)
        self.assertTrue(all(a['state']=='flying' for a in state_at(result,3.25)['aircraft']))
        self.assertEqual(state_at(result,3.25)['resources'][0]['used'],0)
        self.assertTrue(all(a['ready'] for a in state_at(result,4.25)['aircraft']))
        value['model']['missions'][0]['delay_hours']=.249
        cancelled=execute(value)
        self.assertEqual(hours(cancelled,'mission_cancelled'),[3.249])
        self.assertTrue(all(a['ready'] for a in state_at(cancelled,3.249)['aircraft']))
        self.assertTrue(all(a['ready'] for a in state_at(cancelled,3.25)['aircraft']))
        self.assertEqual(state_at(cancelled,3.25)['resources'][0]['used'],0)

    def test_zero_time_local_convergence_is_visible_at_report_zero(self):
        value=model(1);m=value['model'];m['processes'][0].update(scalar_hours=0,steps=[])
        m['missions'][0].update(start_hours=0,notice_hours=0,delay_hours=0)
        result=execute(value)
        self.assertEqual(hours(result,'work_finished'),[0]);self.assertEqual(hours(result,'mission_started'),[0])
        self.assertEqual(state_at(result,0)['aircraft'][0]['state'],'flying')
        self.assertEqual(state_at(result,0)['resources'][0]['used'],0)
        self.assertTrue(state_at(result,1)['aircraft'][0]['ready'])

    def test_report_interval_does_not_change_events_state_or_integrals(self):
        values=[model(),self.replacement(False)]
        cancelled=model();cancelled['model']['missions'][0]['delay_hours']=.249;values.append(cancelled)
        for value in values:
            baseline=execute(value)
            for interval in (.5,1,3):
                with self.subTest(interval=interval,repair=value['model']['aircraft'][0]['repair_mode']):
                    changed=copy.deepcopy(value);changed['model']['report_interval_hours']=interval
                    result=execute(changed)
                    for field in ('trace','terminal','mission_states','physical_items','invariants','events_executed'):
                        self.assertEqual(result[field],baseline[field],field)
                    self.assertEqual(occupancy_integrals(result),occupancy_integrals(baseline))
        base=occupancy_integrals(execute(model()))
        self.assertEqual(base['flying'],ticks(2));self.assertEqual(base['crew'],ticks(.5))
        self.assertEqual(base['assigned'],ticks(3))

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

    def test_failed_return_retains_flight_pm_until_direct_repair_finishes(self):
        value=model(1);m=value['model'];m.update(horizon_hours=6,rng_profile='external-events/v1')
        m['aircraft'][0].update(repair_mode='direct',repair_hours=.5,
                              pm=dict(id='usage',clock='flight',interval_hours=1,duration_hours=.5))
        m['external_events']=[driver('fault')]
        result=execute(value)
        returned=next(e for e in result['trace'] if e['kind']=='mission_returned')
        self.assertEqual((returned['hour'],returned['outcome'],returned['flight_hours']),(4,'aborted',1))
        self.assertEqual(hours(result,'repair_started'),[4]);self.assertEqual(hours(result,'repair_finished'),[4.5])
        self.assertEqual(hours(result,'pm_started'),[4.5]);self.assertEqual(hours(result,'pm_finished'),[5])
        self.assertTrue(result['terminal']['aircraft'][0]['ready']);self.assertTrue(all(result['invariants'].values()))

    def test_failed_return_retains_flight_pm_until_replacement_fit_finishes(self):
        for stock,finish in ((True,4.3),(False,4.7)):
            with self.subTest(stock=stock):
                value=self.replacement(stock);m=value['model'];m['horizon_hours']=6
                m['aircraft'][0]['pm']=dict(id='usage',clock='flight',interval_hours=1,duration_hours=.5)
                result=execute(value)
                self.assertEqual(hours(result,'fit_finished'),[finish]);self.assertEqual(hours(result,'pm_started'),[finish])
                self.assertEqual(hours(result,'pm_finished'),[finish+.5])
                self.assertTrue(result['terminal']['aircraft'][0]['ready'])
                self.assertTrue(all(result['invariants'].values()))

    def test_due_flight_pm_precedes_next_mission_at_repair_completion(self):
        direct=model(1);m=direct['model'];m['rng_profile']='external-events/v1'
        m['aircraft'][0].update(repair_mode='direct',repair_hours=.5);m['external_events']=[driver('fault')]
        for base,finish in ((direct,4.5),(self.replacement(True),4.3)):
            for delay in (.5,.49):
                with self.subTest(repair=base['model']['aircraft'][0]['repair_mode'],delay=delay):
                    value=copy.deepcopy(base);m=value['model'];m['horizon_hours']=6
                    m['processes'][0].update(scalar_hours=0,steps=[])
                    m['aircraft'][0]['pm']=dict(id='usage',clock='flight',interval_hours=1,duration_hours=.5)
                    second=copy.deepcopy(m['missions'][0])
                    second.update(id='next',start_hours=finish,notice_hours=finish,duration_hours=.5,delay_hours=delay)
                    m['missions'].append(second)
                    result=execute(value)
                    self.assertEqual(hours(result,'pm_started'),[finish]);self.assertEqual(hours(result,'pm_finished'),[finish+.5])
                    next_starts=[e for e in result['trace'] if e['kind']=='mission_started' and e['mission']=='next']
                    if delay==.5:
                        self.assertEqual([e['time_ticks'] for e in next_starts],[ticks(finish)+ticks(.5)])
                        pm_done=next(e for e in result['trace'] if e['kind']=='pm_finished')
                        self.assertLess(pm_done['sequence'],next_starts[0]['sequence'])
                        self.assertEqual(hours(result,'mission_cancelled'),[])
                    else:
                        self.assertEqual(next_starts,[])
                        self.assertEqual([e['time_ticks'] for e in result['trace'] if e['kind']=='mission_cancelled'],
                                         [ticks(finish)+ticks(delay)])
                    self.assertTrue(all(result['invariants'].values()))

    def test_positive_pm_times_that_round_to_zero_reject_at_import(self):
        for clock in ('calendar','flight'):
            for field in ('interval_hours','duration_hours'):
                for fraction in (.1,.49,.5):
                    with self.subTest(clock=clock,field=field,fraction=fraction):
                        value=model(1);pm=dict(id='usage',clock=clock,interval_hours=1,duration_hours=.5)
                        pm[field]=fraction/TICKS_PER_HOUR;value['model']['aircraft'][0]['pm']=pm
                        with self.assertRaisesRegex(ValueError,'PM .*microsecond'):import_bounded_business(value)

    def test_one_tick_pm_times_roundtrip_and_execute_inclusively(self):
        for clock in ('calendar','flight'):
            with self.subTest(clock=clock):
                value=model(1);m=value['model'];m.update(horizon_hours=2/TICKS_PER_HOUR,report_interval_hours=1/TICKS_PER_HOUR)
                m['processes'][0].update(scalar_hours=0,steps=[])
                m['missions'][0].update(start_hours=0,notice_hours=0,duration_hours=1/TICKS_PER_HOUR,delay_hours=0)
                m['aircraft'][0]['pm']=dict(id='usage',clock=clock,interval_hours=1/TICKS_PER_HOUR,duration_hours=1/TICKS_PER_HOUR)
                runtime=BoundedAircraftRuntime(compile_model(value));result=runtime.run()
                self.assertEqual([e['time_ticks'] for e in result['trace'] if e['kind']=='pm_started'],[1])
                self.assertEqual([e['time_ticks'] for e in result['trace'] if e['kind']=='pm_finished'],[2])
                self.assertEqual([r['time_ticks'] for r in result['snapshots']],[0,1,2])
                self.assertEqual(runtime.air[0]['flight_ticks'],0);self.assertTrue(result['terminal']['aircraft'][0]['ready'])

    def test_positive_mission_duration_rounding_to_zero_rejects_at_import(self):
        for fraction in (.1,.49,.5):
            with self.subTest(fraction=fraction):
                value=model(1);value['model']['missions'][0]['duration_hours']=fraction/TICKS_PER_HOUR
                with self.assertRaisesRegex(ValueError,'mission duration.*microsecond'):import_bounded_business(value)

    def test_mission_start_rounding_to_horizon_rejects_at_import(self):
        value=model(1);value['model']['missions'][0]['start_hours']=12-1e-12
        self.assertLess(value['model']['missions'][0]['start_hours'],12)
        with self.assertRaisesRegex(ValueError,'start.*quantization'):import_bounded_business(value)

    def test_report_budget_uses_normalized_integer_ticks(self):
        value=model(1);m=value['model'];m.update(horizon_hours=12000/TICKS_PER_HOUR,report_interval_hours=1.49/TICKS_PER_HOUR)
        m['processes'][0].update(scalar_hours=0,steps=[])
        m['missions'][0].update(start_hours=1000/TICKS_PER_HOUR,notice_hours=0,duration_hours=1000/TICKS_PER_HOUR,delay_hours=0)
        self.assertLess(m['horizon_hours']/m['report_interval_hours'],10000)
        with self.assertRaisesRegex(ValueError,'report budget'):import_bounded_business(value)

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

    def test_maximum_acyclic_dependency_chain_is_independent_of_row_order(self):
        value=model(1);base=value['model']['missions'][0]
        chain=[dict(copy.deepcopy(base),id=f'mission-{i:04d}',depends_on=[f'mission-{i-1:04d}'] if i else [])
               for i in range(1000)]
        for rows in (chain,list(reversed(chain))):
            value['model']['missions']=rows
            runtime=BoundedAircraftRuntime(compile_model(value))
            self.assertEqual(len(runtime.missions),1000)
        chain[0]['depends_on']=['mission-0999'];value['model']['missions']=chain
        with self.assertRaisesRegex(ValueError,'cyclic'):import_bounded_business(value)

    def reject_core_edit(self,value,edit,message):
        payload=lower_bounded(import_bounded_business(value)).payload;edit(payload)
        core=Document.create(CORE,payload)
        reloaded=Document.from_dict(core.to_dict(),CORE)
        with self.assertRaisesRegex(ValueError,message):compile_bounded(reloaded,operations=operation_contracts())

    def test_persisted_core_cross_table_references_reject_before_dense_alias(self):
        value=self.replacement(True);m=value['model'];m['nodes'].append(dict(id='depot',items=[]))
        m['routes']=[dict(id='transfer',source='store',destination='depot',duration_hours=.5)]
        m['external_events'].append(dict(id='IN',time_hours=1,operation='in_transfer',aircraft=None,node='store',item='incoming',value_hours=0))
        patches=[('missions',0,'process','aircraft','asset-0'),
                 ('missions',0,'depends_on','aircraft',['asset-0']),
                 ('aircraft',0,'stock_node','resources','technician'),
                 ('aircraft',0,'repair_node','aircraft','asset-0'),
                 ('routes',0,'source','aircraft','asset-0'),
                 ('routes',0,'destination','processes','inspection'),
                 ('external_events',0,'aircraft','nodes','store'),
                 ('external_events',1,'node','aircraft','asset-0')]
        for table,index,field,target,symbol in patches:
            with self.subTest(table=table,field=field):
                def edit(p):p['tables'][table][index]['references'][field]={'table':target,'value':symbol}
                self.reject_core_edit(value,edit,'invalid reference table')

    def test_persisted_core_exact_fields_and_reference_shapes_reject(self):
        patches=[lambda p:p['tables']['missions'][0]['attributes'].update(process='inspection'),
                 lambda p:p['tables']['missions'][0]['attributes'].pop('duration_ticks'),
                 lambda p:p['tables']['missions'][0]['references'].pop('process'),
                 lambda p:p['tables']['missions'][0]['references']['process'].update(value=['inspection']),
                 lambda p:p['tables']['missions'][0]['references']['depends_on'].update(value='survey'),
                 lambda p:p['tables']['missions'][0]['references']['process'].update(extra=True),
                 lambda p:p['tables']['missions'][0].update(extra=True),
                 lambda p:p['tables']['missions'][0].update(source_path='/model/aircraft/0'),
                 lambda p:p['tables'].update(unknown=[]),lambda p:p.update(unknown=True)]
        for index,patch in enumerate(patches):
            with self.subTest(patch=index):self.reject_core_edit(model(1),patch,'fields|symbol|reference list|source path')

    def test_persisted_core_resource_demands_are_typed_unique_positive_operands(self):
        invalid=[{'resource':'asset-0','quantity':1},
                 {'resource':{'table':'aircraft','value':'asset-0'},'quantity':1},
                 {'resource':'technician','quantity':1,'table':'aircraft'},
                 {'resource':'technician','quantity':True},{'resource':'technician','quantity':1.0},
                 {'resource':'technician','quantity':0},{'resource':'technician','quantity':-1}]
        for demand in invalid:
            with self.subTest(demand=demand):
                def edit(p):p['tables']['processes'][0]['attributes']['steps'][0]['demands']=[demand]
                self.reject_core_edit(model(1),edit,'symbol|fields|integer operand')
        def duplicate(p):
            demands=p['tables']['processes'][0]['attributes']['steps'][0]['demands'];demands.append(copy.deepcopy(demands[0]))
        self.reject_core_edit(model(1),duplicate,'duplicate demand')

    def test_persisted_core_typed_references_reload_and_execute(self):
        value=model(2,2);m=value['model']
        m['nodes']=[dict(id='store',items=[]),dict(id='depot',items=[])]
        m['routes']=[dict(id='transfer',source='store',destination='depot',duration_hours=.5)]
        m['aircraft'][0].update(stock_node='store',repair_node='depot')
        m['external_events']=[dict(id='IN',time_hours=1,operation='in_transfer',aircraft=None,node='store',item='incoming',value_hours=0)]
        second=copy.deepcopy(m['missions'][0]);second.update(id='next',start_hours=8,notice_hours=7.75,depends_on=['survey'])
        m['missions'].append(second)
        plan=compile_model(value);p=plan.payload
        self.assertEqual(p['tables']['missions'][1]['depends_on'],[0])
        self.assertEqual(p['tables']['aircraft'][0]['repair_node'],1)
        self.assertEqual(p['tables']['routes'][0]['source'],0);self.assertEqual(p['tables']['routes'][0]['destination'],1)
        self.assertEqual(p['tables']['processes'][0]['steps'][0]['demands'],[[0,1]])
        self.assertEqual(p['tables']['external_events'][0]['node'],0)
        result=BoundedAircraftRuntime(plan).run()
        self.assertEqual(hours(result,'mission_started'),[3,8]);self.assertTrue(all(result['invariants'].values()))

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
