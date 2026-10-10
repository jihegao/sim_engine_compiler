"""Small deterministic calendar and atomic capacity ledger, without domain dispatch."""
from __future__ import annotations
import heapq


class EventCalendar:
    def __init__(self, handlers, horizon, event_budget=100_000):
        if type(horizon) is not int or horizon <= 0 or type(event_budget) is not int or event_budget <= 0:
            raise ValueError('invalid calendar bounds')
        self.handlers = dict(handlers)
        self.horizon = horizon
        self.event_budget = event_budget
        self.now = 0
        self.sequence = 0
        self.heap = []
        self.executed = 0

    def schedule(self, time, phase, operation, payload):
        if operation not in self.handlers:
            raise ValueError(f'unsupported event operation: {operation}')
        if type(time) is not int or time < self.now or type(phase) is not int or phase < 0:
            raise ValueError('invalid or retrograde event time')
        self.sequence += 1
        heapq.heappush(self.heap, (time, phase, self.sequence, operation, payload))

    def run(self, after_time=None):
        while self.heap and self.heap[0][0] <= self.horizon:
            time, phase, sequence, op, payload = heapq.heappop(self.heap)
            self.now = time
            self.executed += 1
            if self.executed > self.event_budget:
                raise ValueError('event budget exceeded (possible zero-time cycle)')
            self.handlers[op](payload)
            if after_time:
                after_time()
        self.now = self.horizon


class CapacityLedger:
    def __init__(self, capacities):
        if any(type(c) is not int or c < 0 for c in capacities):
            raise ValueError('invalid capacity')
        self.capacities = tuple(capacities)
        self.used = [0] * len(capacities)
        self.leases = {}

    def acquire(self, owner, demands):
        if (any(type(r) is not int or not 0 <= r < len(self.used) or type(q) is not int or q <= 0
                for r, q in demands) or len({r for r, q in demands}) != len(demands)):
            raise ValueError('invalid atomic resource demand')
        if owner in self.leases:
            raise ValueError('duplicate resource owner')
        if any(self.used[r] + q > self.capacities[r] for r, q in demands):
            return False
        self.leases[owner] = tuple(demands)
        for r, q in demands:
            self.used[r] += q
        return True

    def release(self, owner):
        if owner not in self.leases:
            raise ValueError('resource lease already released or never held')
        demands = self.leases.pop(owner)
        for r, q in demands:
            self.used[r] -= q
            if not 0 <= self.used[r] <= self.capacities[r]:
                raise ValueError('capacity conservation violated')
        return demands
