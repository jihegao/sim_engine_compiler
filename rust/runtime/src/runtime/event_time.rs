use std::{cmp::Reverse, collections::BinaryHeap};

use anyhow::{Result, bail};

use super::Runtime;

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
enum WakeKind {
    TransportArrival,
    MissionReturn,
    JobCompletion,
    ComponentFailure,
    DayBoundary,
    PreventiveDue,
    MissionPreparation,
    MissionDispatch,
    MissionSuccess,
    DeferredPhase,
    Horizon,
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct ScheduledWake {
    minute: i64,
    phase_rank: u16,
    owner_order: usize,
    sequence: u64,
    kind: WakeKind,
}

struct WakeCalendar {
    queue: BinaryHeap<Reverse<ScheduledWake>>,
    next_sequence: u64,
}

impl WakeCalendar {
    fn new() -> Self {
        Self {
            queue: BinaryHeap::new(),
            next_sequence: 0,
        }
    }

    fn schedule(
        &mut self,
        current_minute: i64,
        horizon: i64,
        minute: i64,
        phase_rank: u16,
        owner_order: usize,
        kind: WakeKind,
    ) {
        if minute <= current_minute || minute > horizon {
            return;
        }
        let sequence = self.next_sequence;
        self.next_sequence = self.next_sequence.saturating_add(1);
        self.queue.push(Reverse(ScheduledWake {
            minute,
            phase_rank,
            owner_order,
            sequence,
            kind,
        }));
    }
}

impl Runtime {
    pub(super) fn run_event_time_until(&mut self, horizon: i64) -> Result<()> {
        while self.running && self.minute < horizon {
            let mut calendar = self.build_wake_calendar(horizon);
            if self.profile_enabled {
                self.profile.event_calendar_rebuilds += 1;
                self.profile.event_candidates_pushed += calendar.queue.len() as u64;
                self.profile.event_max_queue_len = self
                    .profile
                    .event_max_queue_len
                    .max(calendar.queue.len() as u64);
            }
            let Some(Reverse(wake)) = calendar.queue.pop() else {
                bail!(
                    "event-time-v2 calendar is empty at minute {} before horizon {horizon}",
                    self.minute
                );
            };
            if self.profile_enabled {
                self.profile.event_candidates_popped += 1;
            }
            if wake.minute <= self.minute {
                bail!(
                    "event-time-v2 produced non-forward wakeup {} at minute {}",
                    wake.minute,
                    self.minute
                );
            }
            let skipped = wake.minute - self.minute - 1;
            self.advance_continuous_state(skipped)?;
            self.minute = wake.minute;
            if self.profile_enabled {
                self.profile.minute_iterations += 1;
                self.profile.event_wakeups += 1;
                self.profile.event_skipped_minutes += skipped as u64;
            }
            self.execute_minute()?;
        }
        Ok(())
    }

    fn build_wake_calendar(&self, horizon: i64) -> WakeCalendar {
        let mut calendar = WakeCalendar::new();
        calendar.schedule(self.minute, horizon, horizon, 14, 0, WakeKind::Horizon);
        if self.minute == 0 {
            calendar.schedule(self.minute, horizon, 1, 0, 0, WakeKind::DeferredPhase);
        }

        for (shipment_index, shipment) in self.shipments.iter().enumerate() {
            calendar.schedule(
                self.minute,
                horizon,
                shipment.arrival_minute.max(self.minute.saturating_add(1)),
                0,
                shipment_index,
                WakeKind::TransportArrival,
            );
        }
        for (transit_index, transit) in self.resource_transits.iter().enumerate() {
            calendar.schedule(
                self.minute,
                horizon,
                transit.arrival_minute.max(self.minute.saturating_add(1)),
                0,
                self.shipments.len().saturating_add(transit_index),
                WakeKind::TransportArrival,
            );
        }

        for (aircraft_index, aircraft) in self.aircraft.iter().enumerate() {
            if aircraft.state == "flying" {
                if let Some(return_time) = aircraft.return_time {
                    calendar.schedule(
                        self.minute,
                        horizon,
                        return_time.max(self.minute.saturating_add(1)),
                        1,
                        aircraft_index,
                        WakeKind::MissionReturn,
                    );
                }
                if !aircraft.in_flight_failure {
                    for (slot, failure_minute) in
                        aircraft.instance_failure_minutes_by_slot.iter().enumerate()
                    {
                        if failure_minute.is_some() {
                            continue;
                        }
                        let due = match aircraft.failure_remaining_by_slot[slot] {
                            None => self.minute.saturating_add(1),
                            Some(remaining) if remaining.is_finite() => self
                                .minute
                                .saturating_add(failure_ticks_until_due(remaining)),
                            Some(_) => continue,
                        };
                        calendar.schedule(
                            self.minute,
                            horizon,
                            due,
                            3,
                            aircraft_index
                                .saturating_mul(1_000_000)
                                .saturating_add(slot),
                            WakeKind::ComponentFailure,
                        );
                    }
                }
            }
            if let Some(operations_day) = aircraft.operations_day
                && aircraft.daily_takeoffs > 0
                && !aircraft.postflight_due
            {
                let boundary = operations_day.saturating_add(1).saturating_mul(1440);
                calendar.schedule(
                    self.minute,
                    horizon,
                    boundary,
                    4,
                    aircraft_index,
                    WakeKind::DayBoundary,
                );
            }
        }

        for &job_index in &self.running_job_indexes {
            let due = self
                .minute
                .saturating_add(self.jobs[job_index].remaining.max(1));
            calendar.schedule(
                self.minute,
                horizon,
                due,
                2,
                job_index,
                WakeKind::JobCompletion,
            );
        }

        for (cycle_index, spec) in self.plan.preventive_cycles.iter().enumerate() {
            if spec.calendar_days <= 0 {
                continue;
            }
            let due = self.preventive_cycles[cycle_index]
                .last_preventive_minute
                .saturating_add(spec.calendar_days.saturating_mul(1440));
            calendar.schedule(
                self.minute,
                horizon,
                due,
                5,
                cycle_index,
                WakeKind::PreventiveDue,
            );
        }

        for (mission_index, mission) in self.plan.missions.iter().enumerate() {
            let state = &self.missions[mission_index];
            if matches!(state.status.as_str(), "scheduled" | "delayed") {
                calendar.schedule(
                    self.minute,
                    horizon,
                    mission.preparation_start,
                    6,
                    mission_index,
                    WakeKind::MissionPreparation,
                );
                calendar.schedule(
                    self.minute,
                    horizon,
                    mission.planned_start,
                    8,
                    mission_index,
                    WakeKind::MissionDispatch,
                );
                calendar.schedule(
                    self.minute,
                    horizon,
                    mission.planned_start.saturating_add(mission.cancel_minutes),
                    8,
                    mission_index,
                    WakeKind::MissionDispatch,
                );
            }
            if !state.success_evaluated {
                let start = state.actual_start.unwrap_or(mission.planned_start);
                let offset =
                    (mission.duration_minutes as f64 * mission.success_point).ceil() as i64;
                calendar.schedule(
                    self.minute,
                    horizon,
                    start.saturating_add(offset),
                    10,
                    mission_index,
                    WakeKind::MissionSuccess,
                );
            }
        }

        if self.has_cancelled_reservations()
            || self.waiting_job_requires_next_minute()
            || self.preventive_possible_now()
            || self.preflight_possible_now()
            || self.mission_dispatch_possible_now()
        {
            calendar.schedule(
                self.minute,
                horizon,
                self.minute.saturating_add(1),
                0,
                0,
                WakeKind::DeferredPhase,
            );
        }

        calendar
    }

    fn advance_continuous_state(&mut self, skipped: i64) -> Result<()> {
        if skipped <= 0 {
            return Ok(());
        }
        for _ in 0..skipped {
            for &job_index in &self.running_job_indexes {
                self.jobs[job_index].remaining -= 1;
                if self.profile_enabled {
                    self.profile.event_continuous_job_ticks += 1;
                }
                if self.jobs[job_index].remaining <= 0 {
                    bail!(
                        "event-time-v2 skipped job completion for {:?} before minute {}",
                        self.jobs[job_index].job_id,
                        self.minute.saturating_add(skipped).saturating_add(1)
                    );
                }
            }
            for aircraft_index in 0..self.aircraft.len() {
                if self.aircraft[aircraft_index].state != "flying"
                    || self.aircraft[aircraft_index].in_flight_failure
                {
                    continue;
                }
                for slot in 0..self.aircraft[aircraft_index]
                    .failure_remaining_by_slot
                    .len()
                {
                    if self.aircraft[aircraft_index].instance_failure_minutes_by_slot[slot]
                        .is_some()
                    {
                        continue;
                    }
                    let Some(remaining) =
                        self.aircraft[aircraft_index].failure_remaining_by_slot[slot].as_mut()
                    else {
                        bail!(
                            "event-time-v2 cannot skip a missing failure timer for aircraft {aircraft_index} slot {slot}"
                        );
                    };
                    *remaining -= 1.0;
                    if self.profile_enabled {
                        self.profile.event_continuous_failure_ticks += 1;
                    }
                    if *remaining <= 0.0 {
                        bail!(
                            "event-time-v2 skipped component failure for aircraft {aircraft_index} slot {slot}"
                        );
                    }
                }
            }
        }
        Ok(())
    }

    fn has_cancelled_reservations(&self) -> bool {
        self.jobs
            .iter()
            .any(|job| job.state == "cancelled" && !job.spare_reservations.is_empty())
    }

    fn waiting_job_requires_next_minute(&self) -> bool {
        self.waiting_job_indexes.iter().any(|&job_index| {
            let job = &self.jobs[job_index];
            if !job.remote_resources_pending.is_empty() {
                return false;
            }
            let activity = &self.prepared.activities[job.activity_index];
            let Some(step) = activity.steps.get(job.step_index) else {
                return true;
            };
            // Jobs created after resource_dispatch, or advanced to a new step after that
            // phase, have not yet had a chance to request remote inventory. They must wake
            // the next minute even when the destination currently has a shortage.
            if !job.requested_spare_steps.contains(&job.step_index) {
                return true;
            }
            let requirements =
                self.step_requirements(job_index, step.static_spares.clone(), activity.steps.len());
            requirements.iter().all(|(product_id, quantity)| {
                self.resources[activity.resource_node_index]
                    .inventory
                    .get(product_id)
                    .copied()
                    .unwrap_or(0)
                    + job.spare_reservations.get(product_id).copied().unwrap_or(0)
                    >= *quantity
            })
        })
    }

    fn preventive_possible_now(&self) -> bool {
        self.aircraft
            .iter()
            .enumerate()
            .any(|(aircraft_index, aircraft)| {
                if aircraft.state != "available" {
                    return false;
                }
                let active = self.jobs.iter().any(|job| {
                    job.aircraft_index == aircraft_index
                        && job.kind == "preventive"
                        && matches!(job.state.as_str(), "waiting" | "running")
                });
                !active
                    && self
                        .plan
                        .preventive_cycles
                        .iter()
                        .enumerate()
                        .any(|(cycle_index, spec)| {
                            if spec.aircraft_index != aircraft_index {
                                return false;
                            }
                            let cycle = &self.preventive_cycles[cycle_index];
                            (spec.calendar_days > 0
                                && self.minute
                                    >= cycle.last_preventive_minute
                                        + spec.calendar_days.saturating_mul(1440))
                                || (spec.flight_hours > 0.0
                                    && cycle.life_flight_hours >= spec.flight_hours)
                                || (spec.landing_cycles > 0
                                    && cycle.life_landing_cycles >= spec.landing_cycles)
                        })
            })
    }

    fn preflight_possible_now(&self) -> bool {
        self.plan
            .missions
            .iter()
            .enumerate()
            .any(|(mission_index, mission)| {
                if !matches!(
                    self.missions[mission_index].status.as_str(),
                    "scheduled" | "delayed"
                ) || self.minute < mission.preparation_start
                    || self.commissioned_count(mission_index) >= mission.required_aircraft
                {
                    return false;
                }
                let active = self.active_preflight_aircraft(mission_index);
                self.aircraft
                    .iter()
                    .enumerate()
                    .any(|(aircraft_index, aircraft)| {
                        aircraft.state == "available"
                            && !aircraft.postflight_due
                            && self.matches_type(aircraft_index, &mission.required_aircraft_type)
                            && aircraft.prepared_mission_indexes.is_empty()
                            && !active.contains(&aircraft_index)
                    })
            })
    }

    fn mission_dispatch_possible_now(&self) -> bool {
        self.plan
            .missions
            .iter()
            .enumerate()
            .any(|(mission_index, mission)| {
                matches!(
                    self.missions[mission_index].status.as_str(),
                    "scheduled" | "delayed"
                ) && self.minute >= mission.planned_start
                    && (0..self.aircraft.len())
                        .filter(|&aircraft_index| {
                            self.ready_for_mission(aircraft_index, mission_index)
                                && self
                                    .matches_type(aircraft_index, &mission.required_aircraft_type)
                        })
                        .count()
                        >= mission.required_aircraft
            })
    }
}

fn failure_ticks_until_due(remaining: f64) -> i64 {
    if remaining <= 1.0 {
        1
    } else if remaining >= i64::MAX as f64 {
        i64::MAX
    } else {
        (remaining.ceil() as i64).max(1)
    }
}

#[cfg(test)]
mod tests {
    use super::failure_ticks_until_due;

    #[test]
    fn failure_deadline_matches_repeated_minute_countdown() {
        for remaining in [0.1, 1.0, 1.1, 5.581_821, 120.0, 120.25] {
            let mut repeated = remaining;
            let mut ticks = 0;
            while repeated > 0.0 {
                repeated -= 1.0;
                ticks += 1;
            }
            assert_eq!(failure_ticks_until_due(remaining), ticks);
        }
    }
}
