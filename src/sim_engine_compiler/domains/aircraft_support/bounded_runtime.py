"""Plan-only reference operations for aircraft-bounded-events/v1.

All model variation is in the validated Plan. This module contains no case IDs,
oracle reader, native model call, output schedule, or benchmark dispatch table.
"""
from __future__ import annotations
import copy
from sim_engine_compiler.ir.bounded import TICKS_PER_HOUR, require
from sim_engine_compiler.reference.event_calendar import EventCalendar, CapacityLedger
from sim_engine_compiler.domains.aircraft_support.bounded import OPS, validate_plan


class BoundedAircraftRuntime:
    def __init__(self, plan):
        self.p = validate_plan(plan)
        self.plan = plan
        self.t = self.p['tables']
        self.trace = []
        self.snapshots = []
        self.air = [{'state': 'ready', 'mission': None, 'failed': False, 'flight_ticks': 0,
                     'pm_pending': False, 'installed': a['installed_item'], 'replacement': None,
                     'removed': False, 'fitting': False}
                    for a in self.t['aircraft']]
        self.missions = [{'state': 'scheduled', 'aircraft': [], 'prepared': [], 'aborted': False,
                          'start': None, 'return': None} for _ in self.t['missions']]
        self.jobs = {}
        self.crew = CapacityLedger([r['capacity'] for r in self.t['resources']])
        self.stock = [list(n['items']) for n in self.t['nodes']]
        self.nominal = [len(n['items']) for n in self.t['nodes']]
        self.items = {item: ('stock', i) for i, n in enumerate(self.t['nodes']) for item in n['items']}
        self.items.update({a['installed_item']: ('installed', i) for i, a in enumerate(self.t['aircraft'])
                           if a['installed_item'] is not None})
        self.expected_items = len(self.items)
        self.backorders = {}
        self.repair_durations = [a['repair_ticks'] for a in self.t['aircraft']]
        self.calendar = EventCalendar({op: getattr(self, op) for op in OPS}, self.p['horizon_ticks'])
        self.dispatch_times = set()
        self.job_sequence = 0
        self.record_snapshot()

    @property
    def now(self):
        return self.calendar.now

    def emit(self, kind, **fields):
        self.trace.append({'sequence': len(self.trace), 'time_ticks': self.now,
                           'hour': self.now / TICKS_PER_HOUR, 'kind': kind, **fields})

    def aid(self, a):
        return self.t['aircraft'][a]['id']

    def mid(self, m):
        return self.t['missions'][m]['id']

    def schedule(self, when, op, data):
        self.calendar.schedule(when, OPS[op][0], op, data)

    def wake(self):
        if self.now not in self.dispatch_times:
            self.dispatch_times.add(self.now)
            self.schedule(self.now, 'dispatch', None)

    def run(self):
        for i, m in sorted(enumerate(self.t['missions']), key=lambda x: (x[1]['notice_ticks'], x[1]['priority'], x[0])):
            self.schedule(m['notice_ticks'], 'notify', i)
            self.schedule(m['start_ticks'], 'dispatch', None)
            scalar = self.t['processes'][m['process']]['scalar_ticks']
            early = max(m['notice_ticks'], m['start_ticks'] + m['delay_ticks'] - scalar)
            self.schedule(early, 'early_deadline', i)
            self.schedule(m['start_ticks'] + m['delay_ticks'], 'deadline', i)
        for i, a in enumerate(self.t['aircraft']):
            if a['pm'] and a['pm']['clock'] == 'calendar':
                self.schedule(a['pm']['interval_ticks'], 'pm_due', i)
        for e in self.t['external_events']:
            self.schedule(e['time_ticks'], e['operation'], e)
        self.calendar.run(self.record_snapshot)
        self.record_snapshot()
        invariants = self.check_invariants()
        return {'schema': 'aircraft-bounded-result/v1', 'plan_fingerprint': self.plan.fingerprint,
                'source_inputs_sha256': self.p['canonical_sha256'], 'profile': self.p['semantic_profile'],
                'rng_profile': self.p['rng_profile'], 'random_requests': [], 'seed': 0,
                'trace': self.trace, 'snapshots': self.snapshots,
                'terminal': self.snapshot(), 'mission_states': copy.deepcopy(self.missions),
                'physical_items': {k: list(v) for k, v in sorted(self.items.items())},
                'invariants': invariants, 'events_executed': self.calendar.executed}

    def snapshot(self):
        return {'aircraft': [{'id': self.aid(i), 'state': a['state'], 'assigned': a['mission'] is not None,
                             'ready': a['state'] == 'ready' and a['mission'] is None,
                             'failed': a['failed'], 'installed': a['installed']}
                            for i, a in enumerate(self.air)],
                'resources': [{'id': r['id'], 'capacity': r['capacity'], 'used': self.crew.used[i]}
                              for i, r in enumerate(self.t['resources'])],
                'stock': [{'id': n['id'], 'nominal': self.nominal[i], 'on_hand': len(self.stock[i]),
                           'items': list(self.stock[i])} for i, n in enumerate(self.t['nodes'])],
                'backorders': len(self.backorders),
                'active_jobs': sum(j['status'] in ('waiting', 'working') for j in self.jobs.values())}

    def record_snapshot(self):
        self.check_invariants()
        state = self.snapshot()
        if self.snapshots and self.snapshots[-1]['time_ticks'] == self.now:
            self.snapshots[-1]['state'] = state
        elif not self.snapshots or self.snapshots[-1]['state'] != state:
            self.snapshots.append({'time_ticks': self.now, 'state': state})

    def check_invariants(self):
        require(all(0 <= used <= cap for used, cap in zip(self.crew.used, self.crew.capacities)), 'resource capacity violated')
        reconstructed = [0] * len(self.crew.used)
        for demands in self.crew.leases.values():
            for r, q in demands:
                reconstructed[r] += q
        require(reconstructed == self.crew.used, 'resource ledger imbalance')
        occupied = [a for m in self.missions if m['state'] in ('waiting', 'flying') for a in m['aircraft']]
        require(len(occupied) == len(set(occupied)), 'aircraft double allocated')
        require(len(self.items) == self.expected_items, 'physical item conservation violated')
        for n, stock in enumerate(self.stock):
            require(len(stock) == len(set(stock)), 'duplicate stock identity')
            require(all(self.items[item] == ('stock', n) for item in stock), 'stock location disagrees with item ledger')
        for item, (location, owner) in self.items.items():
            if location == 'stock':
                require(item in self.stock[owner], 'stock item missing from physical store')
            elif location == 'installed':
                require(self.air[owner]['installed'] == item, 'installed item missing from aircraft')
            elif location == 'reserved':
                require(self.air[owner]['replacement'] == item, 'reserved item missing from repair owner')
            else:
                require(location in ('supply', 'repair_transport', 'item_repair'), 'unknown physical item location')
        for a, state in enumerate(self.air):
            if state['installed'] is not None:
                require(self.items[state['installed']] == ('installed', a), 'installed item ownership violated')
        require(all(self.air[a]['mission'] == m for m, ms in enumerate(self.missions)
                    if ms['state'] in ('waiting', 'flying') for a in ms['aircraft']), 'reservation ownership violated')
        return {'resource_capacity': True, 'resource_ledger': True, 'unique_aircraft_reservations': True,
                'physical_item_conservation': True, 'installed_item_ownership': True}

    def notify(self, m):
        self.missions[m]['state'] = 'waiting'
        self.emit('mission_notice', mission=self.mid(m))
        self.wake()

    def dispatch(self, unused):
        self.dispatch_times.discard(self.now)
        # Stable mission priority is applied before per-aircraft FIFO work dispatch.
        order = sorted(range(len(self.missions)), key=lambda m: (self.t['missions'][m]['priority'], m))
        for m in order:
            ms, spec = self.missions[m], self.t['missions'][m]
            if ms['state'] != 'waiting':
                continue
            for kind, needed in spec['requirements'].items():
                have = sum(self.t['aircraft'][a]['type'] == kind for a in ms['aircraft'])
                for a, state in enumerate(self.air):
                    if have == needed:
                        break
                    if (self.t['aircraft'][a]['type'] == kind and state['mission'] is None
                            and state['state'] in ('ready', 'turnround') and not state['failed']):
                        state['mission'] = m
                        ms['aircraft'].append(a)
                        have += 1
                        self.emit('aircraft_allocated', mission=self.mid(m), aircraft=self.aid(a),
                                  preassigned=state['state'] == 'turnround')
            for a in ms['aircraft']:
                key = (m, a)
                if self.air[a]['state'] == 'ready' and key not in self.jobs:
                    self.job_sequence += 1
                    self.jobs[key] = {'status': 'waiting', 'step': 0, 'token': 0, 'lease': None,
                                      'sequence': self.job_sequence, 'requested': set()}
                    self.air[a]['state'] = 'preparing'
                    self.emit('preparation_created', mission=self.mid(m), aircraft=self.aid(a))
        for key, job in sorted(self.jobs.items(), key=lambda kv: kv[1]['sequence']):
            if job['status'] == 'waiting':
                self.start_step(key)
        for m in order:
            self.try_launch(m)
        for a, state in enumerate(self.air):
            if state['pm_pending'] and state['state'] == 'ready' and state['mission'] is None:
                self.begin_pm(a)

    def start_step(self, key):
        m, a = key
        job = self.jobs[key]
        if self.missions[m]['state'] != 'waiting':
            return
        steps = self.t['processes'][self.t['missions'][m]['process']]['steps']
        step = steps[job['step']]
        if step['demands'] and job['step'] not in job['requested']:
            job['requested'].add(job['step'])
            self.emit('resource_request', mission=self.mid(m), aircraft=self.aid(a), step=step['id'],
                      demands=[[self.t['resources'][r]['id'], q] for r, q in step['demands']])
        owner = f'work:{m}:{a}:{job["step"]}:{job["token"]}'
        if not self.crew.acquire(owner, step['demands']):
            return
        job.update(status='working', lease=owner, started=self.now)
        for r, q in step['demands']:
            self.emit('resource_acquired', owner=owner, resource=self.t['resources'][r]['id'], quantity=q)
        self.emit('work_started', mission=self.mid(m), aircraft=self.aid(a), step=step['id'], owner=owner,
                  planned_duration_hours=step['duration_ticks'] / TICKS_PER_HOUR)
        self.schedule(self.now + step['duration_ticks'], 'work_done', (key, job['token'], job['step']))

    def finish_lease(self, job, *, cancelled=False):
        owner = job['lease']
        if owner is None:
            return
        demands = self.crew.release(owner)
        for r, q in demands:
            self.emit('resource_released', owner=owner, resource=self.t['resources'][r]['id'], quantity=q,
                      cancelled=cancelled)
        job['lease'] = None

    def work_done(self, payload):
        key, token, step_index = payload
        job = self.jobs[key]
        if job['status'] != 'working' or token != job['token'] or step_index != job['step']:
            return  # cancelled owner's stale completion token
        m, a = key
        steps = self.t['processes'][self.t['missions'][m]['process']]['steps']
        self.emit('work_finished', mission=self.mid(m), aircraft=self.aid(a), step=steps[step_index]['id'],
                  owner=job['lease'])
        self.finish_lease(job)
        job['step'] += 1
        if job['step'] == len(steps):
            job['status'] = 'done'
            self.missions[m]['prepared'].append(a)
            self.air[a]['state'] = 'prepared'
            self.emit('preparation_finished', mission=self.mid(m), aircraft=self.aid(a))
        else:
            job['status'] = 'waiting'
        self.wake()

    def formation_complete(self, m):
        spec, state = self.t['missions'][m], self.missions[m]
        return all(sum(self.t['aircraft'][a]['type'] == t for a in state['aircraft']) >= n
                   for t, n in spec['requirements'].items())

    def try_launch(self, m):
        state, spec = self.missions[m], self.t['missions'][m]
        if (state['state'] != 'waiting' or self.now < spec['start_ticks'] or
                self.now > spec['start_ticks'] + spec['delay_ticks']):
            return
        if not self.formation_complete(m) or set(state['prepared']) != set(state['aircraft']):
            return
        if any(self.missions[d]['state'] != 'completed' or self.missions[d]['aborted'] for d in spec['depends_on']):
            return
        state.update(state='flying', start=self.now)
        for a in state['aircraft']:
            self.air[a]['state'] = 'flying'
        self.emit('mission_started', mission=self.mid(m), aircraft=[self.aid(a) for a in state['aircraft']])
        self.schedule(self.now + spec['duration_ticks'], 'mission_return', (m, self.now))

    def early_deadline(self, m):
        state, spec = self.missions[m], self.t['missions'][m]
        if state['state'] != 'waiting':
            return
        # Bounded fixed-capacity feasibility gate. Temporary occupancy is not a
        # permanent shortage; resource completion gets to dispatch at this time.
        steps = self.t['processes'][spec['process']]['steps']
        impossible = any(q > self.crew.capacities[r] for s in steps for r, q in s['demands'])
        if not self.formation_complete(m) or impossible:
            self.cancel(m, 'latest_preparation_feasibility')

    def deadline(self, m):
        if self.missions[m]['state'] == 'waiting':
            self.cancel(m, 'latest_launch')

    def cancel(self, m, reason):
        ms = self.missions[m]
        ms['state'] = 'cancelled'
        self.emit('mission_cancelled', mission=self.mid(m), reason=reason)
        for a in ms['aircraft']:
            job = self.jobs.get((m, a))
            if job and job['status'] in ('working', 'waiting'):
                if job['status'] == 'working':
                    self.emit('work_cancelled', mission=self.mid(m), aircraft=self.aid(a), owner=job['lease'])
                self.finish_lease(job, cancelled=True)
                job['token'] += 1
                job['status'] = 'cancelled'
            self.air[a]['mission'] = None
            if self.air[a]['state'] in ('preparing', 'prepared'):
                self.air[a]['state'] = 'ready'
        self.wake()

    def mission_return(self, payload):
        m, start_token = payload
        ms = self.missions[m]
        if ms['state'] != 'flying' or ms['start'] != start_token:
            return
        self.return_mission(m)

    def return_mission(self, m):
        ms = self.missions[m]
        elapsed = self.now - ms['start']
        ms.update(state='completed', return_time=self.now)
        self.emit('mission_returned', mission=self.mid(m), outcome='aborted' if ms['aborted'] else 'successful',
                  aircraft=[self.aid(a) for a in ms['aircraft']], flight_hours=elapsed / TICKS_PER_HOUR)
        for a in ms['aircraft']:
            state, spec = self.air[a], self.t['aircraft'][a]
            state['flight_ticks'] += elapsed
            state['mission'] = None
            state['state'] = 'ready'
            if state['failed']:
                self.begin_repair(a)
            elif spec['pm'] and spec['pm']['clock'] == 'flight' and state['flight_ticks'] >= spec['pm']['interval_ticks']:
                state['pm_pending'] = True
                self.begin_pm(a)
            elif spec['turnround_ticks']:
                state['state'] = 'turnround'
                self.emit('turnround_started', aircraft=self.aid(a))
                self.schedule(self.now + spec['turnround_ticks'], 'turnround_done', a)
        self.wake()

    def turnround_done(self, a):
        require(self.air[a]['state'] == 'turnround', 'invalid turnround completion')
        self.air[a]['state'] = 'ready'
        self.emit('turnround_finished', aircraft=self.aid(a))
        self.wake()

    def fault(self, e):
        a = e['aircraft']
        state = self.air[a]
        require(state['state'] == 'flying' and not state['failed'], 'fault tape does not match flying healthy aircraft')
        state['failed'] = True
        self.missions[state['mission']]['aborted'] = True
        self.emit('external_fault', driver=e['id'], aircraft=self.aid(a), item=state['installed'])

    def damaged_arrival(self, e):
        a = e['aircraft']
        require(self.air[a]['state'] == 'flying' and not self.air[a]['failed'], 'damaged-arrival tape state mismatch')
        m = self.air[a]['mission']
        require(len(self.missions[m]['aircraft']) == 1, 'damaged-arrival response is restricted to a single-aircraft mission')
        self.air[a]['failed'] = True
        self.missions[m]['aborted'] = True
        self.emit('external_damaged_arrival', driver=e['id'], aircraft=self.aid(a))
        self.return_mission(m)

    def set_repair_duration(self, e):
        a = e['aircraft']
        require(self.air[a]['state'] != 'repair', 'in-progress parameter changes are unsupported')
        self.repair_durations[a] = e['value_ticks']
        self.emit('repair_parameter_changed', driver=e['id'], aircraft=self.aid(a),
                  duration_hours=e['value_ticks'] / TICKS_PER_HOUR)

    def begin_repair(self, a):
        spec, state = self.t['aircraft'][a], self.air[a]
        state['state'] = 'repair'
        if spec['repair_mode'] == 'direct':
            self.emit('repair_started', aircraft=self.aid(a), duration_hours=self.repair_durations[a] / TICKS_PER_HOUR)
            self.schedule(self.now + self.repair_durations[a], 'repair_done', a)
        elif spec['repair_mode'] == 'replacement':
            state.update(removed=False, replacement=None, fitting=False)
            self.emit('spare_demand', aircraft=self.aid(a), node=self.t['nodes'][spec['stock_node']]['id'])
            self.request_spare(a)
            self.emit('remove_started', aircraft=self.aid(a), item=state['installed'])
            self.schedule(self.now + spec['remove_ticks'], 'remove_done', a)
        else:
            raise ValueError('repair required without supported policy')

    def repair_done(self, a):
        require(self.air[a]['state'] == 'repair', 'invalid repair completion')
        self.air[a].update(state='ready', failed=False)
        self.emit('repair_finished', aircraft=self.aid(a))
        self.wake()

    def pm_due(self, a):
        self.air[a]['pm_pending'] = True
        self.wake()

    def begin_pm(self, a):
        state, pm = self.air[a], self.t['aircraft'][a]['pm']
        require(state['state'] == 'ready' and state['mission'] is None, 'PM requires free landed aircraft')
        state.update(state='pm', pm_pending=False)
        self.emit('pm_started', aircraft=self.aid(a), pm=pm['id'])
        self.schedule(self.now + pm['duration_ticks'], 'pm_done', a)

    def pm_done(self, a):
        state, pm = self.air[a], self.t['aircraft'][a]['pm']
        require(state['state'] == 'pm', 'invalid PM completion')
        state.update(state='ready', flight_ticks=0)
        self.emit('pm_finished', aircraft=self.aid(a), pm=pm['id'])
        if pm['clock'] == 'calendar':
            self.schedule(self.now + pm['interval_ticks'], 'pm_due', a)
        self.wake()

    def route_delay(self, source, destination):
        if source == destination:
            return 0
        for route in self.t['routes']:
            if (route['source'], route['destination']) == (source, destination):
                return route['duration_ticks']
        raise ValueError('no transport route')

    def request_spare(self, a):
        spec = self.t['aircraft'][a]
        dest = spec['stock_node']
        candidates = [(dest, 0)] + [(r['source'], r['duration_ticks']) for r in self.t['routes'] if r['destination'] == dest]
        for source, delay in candidates:
            if self.stock[source]:
                item = self.stock[source].pop(0)
                self.items[item] = ('supply', a)
                self.emit('spare_issued', aircraft=self.aid(a), item=item,
                          node=self.t['nodes'][source]['id'], on_hand=len(self.stock[source]))
                if delay:
                    self.backorders[a] = self.now
                    self.emit('backorder_started', aircraft=self.aid(a))
                self.schedule(self.now + delay, 'supply_arrival', (a, item))
                return
        self.backorders[a] = self.now
        self.emit('backorder_started', aircraft=self.aid(a))

    def remove_done(self, a):
        state, spec = self.air[a], self.t['aircraft'][a]
        item = state['installed']
        require(item is not None, 'no installed item to remove')
        state.update(installed=None, removed=True)
        self.items[item] = ('repair_transport', spec['repair_node'])
        self.emit('remove_finished', aircraft=self.aid(a), item=item)
        delay = self.route_delay(spec['stock_node'], spec['repair_node'])
        self.schedule(self.now + delay, 'item_repair_start', (a, item))
        self.try_fit(a)

    def item_repair_start(self, payload):
        a, item = payload
        spec = self.t['aircraft'][a]
        self.items[item] = ('item_repair', spec['repair_node'])
        self.emit('item_repair_started', aircraft=self.aid(a), item=item,
                  node=self.t['nodes'][spec['repair_node']]['id'])
        self.schedule(self.now + spec['item_repair_ticks'], 'item_repair_done', (a, item))

    def item_repair_done(self, payload):
        a, item = payload
        node = self.t['aircraft'][a]['repair_node']
        self.items[item] = ('stock', node)
        self.stock[node].append(item)
        self.emit('item_repair_finished', aircraft=self.aid(a), item=item, node=self.t['nodes'][node]['id'],
                  on_hand=len(self.stock[node]))
        self.fulfill_backorders(node, item)

    def fulfill_backorders(self, node, item):
        # Outstanding demands keep their original waiting timestamp. A receipt
        # creates exactly one delivery, including demand-driven remote supply.
        for waiting in list(self.backorders):
            destination = self.t['aircraft'][waiting]['stock_node']
            reachable = destination == node or any(r['source'] == node and r['destination'] == destination for r in self.t['routes'])
            if reachable and self.air[waiting]['replacement'] is None:
                if any(location == ('supply', waiting) for location in self.items.values()):
                    continue
                self.stock[node].remove(item)
                self.items[item] = ('supply', waiting)
                self.emit('spare_issued', aircraft=self.aid(waiting), item=item,
                          node=self.t['nodes'][node]['id'], on_hand=len(self.stock[node]))
                self.schedule(self.now + self.route_delay(node, destination), 'supply_arrival', (waiting, item))
                break

    def supply_arrival(self, payload):
        a, item = payload
        require(self.items[item] == ('supply', a) and self.air[a]['replacement'] is None, 'duplicate spare delivery')
        self.items[item] = ('reserved', a)
        self.air[a]['replacement'] = item
        self.emit('spare_arrived', aircraft=self.aid(a), item=item)
        if a in self.backorders:
            start = self.backorders.pop(a)
            self.emit('backorder_finished', aircraft=self.aid(a), wait_hours=(self.now - start) / TICKS_PER_HOUR)
        self.try_fit(a)

    def try_fit(self, a):
        state, spec = self.air[a], self.t['aircraft'][a]
        if state['removed'] and state['replacement'] is not None and not state['fitting']:
            state['fitting'] = True
            self.emit('fit_started', aircraft=self.aid(a), item=state['replacement'])
            self.schedule(self.now + spec['fit_ticks'], 'fit_done', a)

    def fit_done(self, a):
        state = self.air[a]
        require(state['fitting'] and state['installed'] is None, 'invalid fit completion')
        item = state['replacement']
        self.items[item] = ('installed', a)
        state.update(installed=item, replacement=None, fitting=False, failed=False, state='ready')
        self.emit('fit_finished', aircraft=self.aid(a), item=item)
        self.wake()

    def in_transfer(self, e):
        node, item = e['node'], e['item']
        require(item not in self.items, 'duplicate transferred item')
        self.items[item] = ('stock', node)
        self.stock[node].append(item)
        self.nominal[node] += 1
        self.expected_items += 1
        self.emit('external_stock_arrived', driver=e['id'], node=self.t['nodes'][node]['id'], item=item,
                  nominal=self.nominal[node], on_hand=len(self.stock[node]))
        self.fulfill_backorders(node, item)
