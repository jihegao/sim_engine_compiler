use std::{
    collections::{BTreeMap, BTreeSet, HashMap, HashSet},
    str::FromStr,
    sync::Arc,
    time::Instant,
};

use anyhow::{Result, bail};
use serde::Serialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

use crate::plan::ExecutionPlan;
use crate::rng::PythonRandom;

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ObservationLevel {
    Summary,
    Full,
}

impl FromStr for ObservationLevel {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        match value {
            "summary" => Ok(Self::Summary),
            "full" => Ok(Self::Full),
            other => bail!("unsupported observation level {other:?}; expected summary or full"),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ExecutionPhase {
    TransportArrivals,
    MissionReturns,
    JobProgressAndCompletions,
    Failures,
    OperationsPostflightBeforePreparation,
    PreventiveGeneration,
    PreflightGeneration,
    ResourceDispatch,
    MissionDispatch,
    OperationsPostflightAfterDispatch,
    MissionSuccess,
    DailyReadiness,
    OperationalAvailability,
    Downtime,
    Stop,
    Unsupported(usize),
}

impl ExecutionPhase {
    fn from_name(index: usize, name: &str) -> Self {
        match name {
            "transport_arrivals" => Self::TransportArrivals,
            "mission_returns" => Self::MissionReturns,
            "job_progress_and_completions" => Self::JobProgressAndCompletions,
            "failures" => Self::Failures,
            "operations_postflight_before_preparation" => {
                Self::OperationsPostflightBeforePreparation
            }
            "preventive_generation" => Self::PreventiveGeneration,
            "preflight_generation" => Self::PreflightGeneration,
            "resource_dispatch" => Self::ResourceDispatch,
            "mission_dispatch" => Self::MissionDispatch,
            "operations_postflight_after_dispatch" => Self::OperationsPostflightAfterDispatch,
            "mission_success" => Self::MissionSuccess,
            "daily_readiness" => Self::DailyReadiness,
            "operational_availability" => Self::OperationalAvailability,
            "downtime" => Self::Downtime,
            "stop" => Self::Stop,
            _ => Self::Unsupported(index),
        }
    }

    fn name(self) -> Option<&'static str> {
        match self {
            Self::TransportArrivals => Some("transport_arrivals"),
            Self::MissionReturns => Some("mission_returns"),
            Self::JobProgressAndCompletions => Some("job_progress_and_completions"),
            Self::Failures => Some("failures"),
            Self::OperationsPostflightBeforePreparation => {
                Some("operations_postflight_before_preparation")
            }
            Self::PreventiveGeneration => Some("preventive_generation"),
            Self::PreflightGeneration => Some("preflight_generation"),
            Self::ResourceDispatch => Some("resource_dispatch"),
            Self::MissionDispatch => Some("mission_dispatch"),
            Self::OperationsPostflightAfterDispatch => Some("operations_postflight_after_dispatch"),
            Self::MissionSuccess => Some("mission_success"),
            Self::DailyReadiness => Some("daily_readiness"),
            Self::OperationalAvailability => Some("operational_availability"),
            Self::Downtime => Some("downtime"),
            Self::Stop => Some("stop"),
            Self::Unsupported(_) => None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct PhaseProfile {
    pub calls: u64,
    pub elapsed_ns: u64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct RuntimeProfile {
    pub minute_iterations: u64,
    pub execution_ns: u64,
    pub phases: BTreeMap<String, PhaseProfile>,
    pub mission_scan_items: u64,
    pub aircraft_scan_items: u64,
    pub job_scan_items: u64,
    pub resource_dispatch_candidate_visits: u64,
    pub resource_dispatch_guard_evaluations: u64,
    pub resource_dispatch_cache_hits: u64,
    pub job_progress_candidate_visits: u64,
    pub waiting_job_indexes_peak: u64,
    pub running_job_indexes_peak: u64,
    pub component_scan_items: u64,
    pub preventive_scan_items: u64,
    pub shipment_scan_items: u64,
    pub trace_events_attempted: u64,
    pub trace_events_materialized: u64,
    pub trace_event_string_values: u64,
    pub trace_event_build_ns: u64,
    pub rng_requests: u64,
    pub rng_ns: u64,
    pub metrics_build_ns: u64,
    pub terminal_state_build_ns: u64,
    pub plan_spec_clones: u64,
    pub indexed_map_reads: u64,
    pub indexed_map_writes: u64,
}

impl RuntimeProfile {
    fn add_phase(&mut self, phase: &str, elapsed_ns: u64) {
        let item = self.phases.entry(phase.to_owned()).or_default();
        item.calls += 1;
        item.elapsed_ns = item.elapsed_ns.saturating_add(elapsed_ns);
    }
}

fn elapsed_ns(started: Instant) -> u64 {
    started.elapsed().as_nanos().try_into().unwrap_or(u64::MAX)
}

fn count_string_values(value: &Value) -> u64 {
    match value {
        Value::String(_) => 1,
        Value::Array(items) => items.iter().map(count_string_values).sum(),
        Value::Object(items) => items.values().map(count_string_values).sum(),
        _ => 0,
    }
}

#[derive(Clone, Debug)]
struct AircraftState {
    tail_number: String,
    aircraft_type: String,
    model: String,
    state: String,
    current_mission_index: Option<usize>,
    return_time: Option<i64>,
    prepared_mission_indexes: BTreeSet<usize>,
    operations_day: Option<i64>,
    daily_takeoffs: i64,
    operations_plan_group_id: String,
    last_operations_mission_index: Option<usize>,
    prepared_operations_day: Option<i64>,
    postflight_required: bool,
    postflight_due: bool,
    flight_hours: f64,
    takeoff_count: i64,
    landing_count: i64,
    failure_remaining_by_slot: Vec<Option<f64>>,
    component_failure_minutes_by_slot: Vec<Option<i64>>,
    failed_component_index: Option<usize>,
    failed_component_minute: Option<i64>,
    in_flight_failure: bool,
}

#[derive(Clone, Debug)]
struct MissionState {
    status: String,
    actual_start: Option<i64>,
    return_time: Option<i64>,
    assigned_aircraft: Vec<usize>,
    failed_aircraft: Vec<usize>,
    preflight_created: bool,
    delay_minutes: i64,
    success_evaluated: bool,
    success_member_count: usize,
    success_at_minute: Option<i64>,
    succeeded: bool,
}

impl Default for MissionState {
    fn default() -> Self {
        Self {
            status: "scheduled".into(),
            actual_start: None,
            return_time: None,
            assigned_aircraft: vec![],
            failed_aircraft: vec![],
            preflight_created: false,
            delay_minutes: 0,
            success_evaluated: false,
            success_member_count: 0,
            success_at_minute: None,
            succeeded: false,
        }
    }
}

#[derive(Clone, Debug)]
struct JobState {
    job_id: String,
    aircraft_index: usize,
    kind: String,
    activity_index: usize,
    mission_index: Option<usize>,
    state: String,
    step_index: usize,
    remaining: i64,
    started_time: Option<i64>,
    completed_time: Option<i64>,
    reserved_personnel: i64,
    reserved_equipment: i64,
    component_index: Option<usize>,
    preventive_cycle_index: Option<usize>,
    maintenance_method: Option<String>,
    injected_spares: Vec<(String, i64)>,
    requested_spare_steps: HashSet<usize>,
    consumed_spare_steps: HashSet<usize>,
    shortage_signature: Option<Vec<(String, i64, i64)>>,
    spare_reservations: BTreeMap<String, i64>,
}

#[derive(Clone, Debug)]
struct ResourceState {
    personnel_capacity: i64,
    equipment_capacity: i64,
    personnel_in_use: i64,
    equipment_in_use: i64,
    inventory: BTreeMap<String, i64>,
}

#[derive(Clone, Debug)]
struct PreventiveCycleState {
    life_flight_hours: f64,
    life_landing_cycles: i64,
    last_preventive_minute: i64,
}

#[derive(Clone, Debug)]
struct ShipmentState {
    job_id: String,
    step_index: usize,
    product_id: String,
    quantity: i64,
    source_node_index: usize,
    destination_node_index: usize,
    requested_minute: i64,
    arrival_minute: i64,
    route_index: usize,
}

#[derive(Clone, Debug)]
pub(crate) struct PreparedStep {
    index: usize,
    code: String,
    duration_minutes: i64,
    personnel: i64,
    equipment: i64,
    static_spares: Arc<[(String, i64)]>,
}

#[derive(Clone, Debug)]
pub(crate) struct PreparedActivity {
    resource_node_index: usize,
    priority: i64,
    steps: Vec<PreparedStep>,
}

#[derive(Clone, Debug)]
pub(crate) struct PreparedRuntimePlan {
    activities: Vec<PreparedActivity>,
    resource_dispatch_reverse: HashMap<DispatchResourceKey, Vec<DispatchCandidate>>,
}

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
struct DispatchResourceKey {
    kind: String,
    node_index: usize,
    product_id: Option<String>,
}

#[derive(Clone, Debug)]
struct DispatchCandidate {
    activity_index: usize,
    step_index: usize,
    product_filter: Option<String>,
}

#[derive(Clone, Debug)]
enum DispatchBlockReason {
    Shortage,
    Personnel,
    Equipment,
}

#[derive(Clone, Debug)]
struct CachedDispatchBlock {
    activity_index: usize,
    step_index: usize,
    reason: DispatchBlockReason,
}

impl PreparedRuntimePlan {
    pub(crate) fn from_plan(plan: &ExecutionPlan) -> Self {
        let activities = plan
            .activities
            .iter()
            .map(|activity| PreparedActivity {
                resource_node_index: activity.resource_node_index,
                priority: activity.priority,
                steps: activity
                    .steps
                    .iter()
                    .map(|step| {
                        // WorkStepSpec.spares historically becomes a BTreeMap at dispatch:
                        // duplicate product IDs keep the last quantity and keys are sorted.
                        // Freeze exactly that representation once in the prepared layout.
                        let static_spares: Arc<[(String, i64)]> = step
                            .spares
                            .iter()
                            .cloned()
                            .collect::<BTreeMap<_, _>>()
                            .into_iter()
                            .collect::<Vec<_>>()
                            .into();
                        PreparedStep {
                            index: step.index,
                            code: step.code.clone(),
                            duration_minutes: step.duration_minutes,
                            personnel: step.personnel,
                            equipment: step.equipment,
                            static_spares,
                        }
                    })
                    .collect(),
            })
            .collect();
        let mut resource_dispatch_reverse: HashMap<DispatchResourceKey, Vec<DispatchCandidate>> =
            HashMap::new();
        if let Some(index) = &plan.resource_dispatch_index {
            for dependency in &index.dependencies {
                let key = DispatchResourceKey {
                    kind: dependency.key.kind.clone(),
                    node_index: dependency.key.node_index,
                    product_id: dependency.key.product_id.clone(),
                };
                let candidates = resource_dispatch_reverse.entry(key).or_default();
                candidates.extend(dependency.candidates.iter().map(|candidate| {
                    DispatchCandidate {
                        activity_index: candidate.activity_index,
                        step_index: candidate.step_index,
                        product_filter: candidate.product_filter.clone(),
                    }
                }));
            }
        }
        Self {
            activities,
            resource_dispatch_reverse,
        }
    }
}

enum StepRequirements {
    Empty,
    Static(Arc<[(String, i64)]>),
    Dynamic(Vec<(String, i64)>),
}

impl StepRequirements {
    fn as_slice(&self) -> &[(String, i64)] {
        match self {
            Self::Empty => &[],
            Self::Static(items) => items,
            Self::Dynamic(items) => items,
        }
    }

    fn len(&self) -> usize {
        self.as_slice().len()
    }

    fn is_empty(&self) -> bool {
        self.as_slice().is_empty()
    }

    fn iter(&self) -> std::slice::Iter<'_, (String, i64)> {
        self.as_slice().iter()
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct RunResult {
    pub plan_fingerprint: String,
    pub seed: u64,
    pub time: i64,
    pub stop_reason: String,
    pub sample_requests: Vec<Value>,
    pub trace: Vec<Value>,
    pub metrics: Value,
    pub terminal_state: Value,
}

pub struct Runtime {
    plan: Arc<ExecutionPlan>,
    prepared: Arc<PreparedRuntimePlan>,
    execution_phases: Vec<ExecutionPhase>,
    fingerprint: String,
    seed: u64,
    minute: i64,
    phase: String,
    running: bool,
    stop_reason: String,
    observation_level: ObservationLevel,
    profile_enabled: bool,
    profile: RuntimeProfile,
    trace: Vec<Value>,
    sample_requests: Vec<Value>,
    rng: PythonRandom,
    aircraft: Vec<AircraftState>,
    missions: Vec<MissionState>,
    jobs: Vec<JobState>,
    waiting_job_indexes: BTreeSet<usize>,
    waiting_dispatch_jobs: HashMap<(usize, usize), BTreeSet<usize>>,
    running_job_indexes: BTreeSet<usize>,
    dispatch_cache: Vec<Option<CachedDispatchBlock>>,
    resources: Vec<ResourceState>,
    preventive_cycles: Vec<PreventiveCycleState>,
    shipments: Vec<ShipmentState>,
    job_sequence: usize,
    launched_sorties: i64,
    completed_sorties: i64,
    cancelled_sorties: i64,
    delayed_sorties: i64,
    total_departure_delay: i64,
    lru_failures: i64,
    in_flight_failures: i64,
    failed_sorties: i64,
    preventive_maintenance_events: i64,
    spare_demand_total: i64,
    spare_immediately_filled_total: i64,
    spare_consumed_total: i64,
    shortage_events: i64,
    transport_replenishment_events: i64,
    total_transport_delay: i64,
    delayed_missions: HashSet<usize>,
    activity_by_group_phase: HashMap<(String, String), Vec<usize>>,
    children_by_component: HashMap<i64, Vec<usize>>,
    failure_components_by_aircraft: Vec<Vec<usize>>,
}

impl Runtime {
    fn count_scan(&mut self, kind: &str, count: usize) {
        if !self.profile_enabled {
            return;
        }
        let count = count as u64;
        match kind {
            "mission" => self.profile.mission_scan_items += count,
            "aircraft" => self.profile.aircraft_scan_items += count,
            "job" => self.profile.job_scan_items += count,
            "component" => self.profile.component_scan_items += count,
            "preventive" => self.profile.preventive_scan_items += count,
            "shipment" => self.profile.shipment_scan_items += count,
            _ => unreachable!("unsupported scan counter"),
        }
    }

    fn count_map_reads(&mut self, count: usize) {
        if self.profile_enabled {
            self.profile.indexed_map_reads += count as u64;
        }
    }

    fn count_map_writes(&mut self, count: usize) {
        if self.profile_enabled {
            self.profile.indexed_map_writes += count as u64;
        }
    }

    fn invalidate_dispatch_job_cache(&mut self, job_index: usize) {
        if let Some(cache) = self.dispatch_cache.get_mut(job_index) {
            *cache = None;
        }
    }

    fn invalidate_dispatch_resource(
        &mut self,
        kind: &str,
        node_index: usize,
        product_id: Option<&str>,
    ) {
        let key = DispatchResourceKey {
            kind: kind.to_owned(),
            node_index,
            product_id: product_id.map(str::to_owned),
        };
        let Some(candidates) = self.prepared.resource_dispatch_reverse.get(&key).cloned() else {
            return;
        };
        for candidate in candidates {
            let waiting = self
                .waiting_dispatch_jobs
                .get(&(candidate.activity_index, candidate.step_index))
                .cloned()
                .unwrap_or_default();
            for job_index in waiting {
                let product_matches = candidate.product_filter.as_ref().is_none_or(|product| {
                    self.jobs[job_index]
                        .injected_spares
                        .iter()
                        .any(|(injected, quantity)| injected == product && *quantity > 0)
                });
                if product_matches {
                    self.invalidate_dispatch_job_cache(job_index);
                }
            }
        }
    }

    fn cache_dispatch_block(
        &mut self,
        job_index: usize,
        activity_index: usize,
        step_index: usize,
        reason: DispatchBlockReason,
    ) {
        if self.plan.resource_dispatch_index.is_some() {
            self.dispatch_cache[job_index] = Some(CachedDispatchBlock {
                activity_index,
                step_index,
                reason,
            });
        }
    }

    fn update_active_job_peaks(&mut self) {
        if self.profile_enabled {
            self.profile.waiting_job_indexes_peak = self
                .profile
                .waiting_job_indexes_peak
                .max(self.waiting_job_indexes.len() as u64);
            self.profile.running_job_indexes_peak = self
                .profile
                .running_job_indexes_peak
                .max(self.running_job_indexes.len() as u64);
        }
    }

    fn transition_job_state(&mut self, job_index: usize, state: &str) {
        self.invalidate_dispatch_job_cache(job_index);
        match self.jobs[job_index].state.as_str() {
            "waiting" => {
                let removed = self.waiting_job_indexes.remove(&job_index);
                debug_assert!(removed, "waiting job missing from active index");
                let key = (
                    self.jobs[job_index].activity_index,
                    self.jobs[job_index].step_index,
                );
                if let Some(indexes) = self.waiting_dispatch_jobs.get_mut(&key) {
                    indexes.remove(&job_index);
                    if indexes.is_empty() {
                        self.waiting_dispatch_jobs.remove(&key);
                    }
                }
            }
            "running" => {
                let removed = self.running_job_indexes.remove(&job_index);
                debug_assert!(removed, "running job missing from active index");
            }
            _ => {}
        }
        self.jobs[job_index].state.clear();
        self.jobs[job_index].state.push_str(state);
        match state {
            "waiting" => {
                let inserted = self.waiting_job_indexes.insert(job_index);
                debug_assert!(inserted, "waiting job duplicated in active index");
                self.waiting_dispatch_jobs
                    .entry((
                        self.jobs[job_index].activity_index,
                        self.jobs[job_index].step_index,
                    ))
                    .or_default()
                    .insert(job_index);
            }
            "running" => {
                let inserted = self.running_job_indexes.insert(job_index);
                debug_assert!(inserted, "running job duplicated in active index");
            }
            _ => {}
        }
        self.update_active_job_peaks();
        self.debug_assert_active_job_indexes();
    }

    #[cfg(debug_assertions)]
    fn debug_assert_active_job_indexes(&self) {
        let waiting: BTreeSet<_> = self
            .jobs
            .iter()
            .enumerate()
            .filter_map(|(index, job)| (job.state == "waiting").then_some(index))
            .collect();
        let running: BTreeSet<_> = self
            .jobs
            .iter()
            .enumerate()
            .filter_map(|(index, job)| (job.state == "running").then_some(index))
            .collect();
        let mut waiting_dispatch_jobs: HashMap<(usize, usize), BTreeSet<usize>> = HashMap::new();
        for (index, job) in self.jobs.iter().enumerate() {
            if job.state == "waiting" {
                waiting_dispatch_jobs
                    .entry((job.activity_index, job.step_index))
                    .or_default()
                    .insert(index);
            }
        }
        debug_assert_eq!(self.waiting_job_indexes, waiting);
        debug_assert_eq!(self.running_job_indexes, running);
        debug_assert_eq!(self.waiting_dispatch_jobs, waiting_dispatch_jobs);
    }

    #[cfg(not(debug_assertions))]
    fn debug_assert_active_job_indexes(&self) {}

    pub fn new(plan: ExecutionPlan, fingerprint: String, seed: u64) -> Result<Self> {
        Self::new_with_observation(plan, fingerprint, seed, ObservationLevel::Full)
    }

    pub fn new_with_observation(
        plan: ExecutionPlan,
        fingerprint: String,
        seed: u64,
        observation_level: ObservationLevel,
    ) -> Result<Self> {
        Self::from_shared_with_observation(Arc::new(plan), fingerprint, seed, observation_level)
    }

    pub fn from_shared(plan: Arc<ExecutionPlan>, fingerprint: String, seed: u64) -> Result<Self> {
        Self::from_shared_with_observation(plan, fingerprint, seed, ObservationLevel::Full)
    }

    pub fn from_shared_with_observation(
        plan: Arc<ExecutionPlan>,
        fingerprint: String,
        seed: u64,
        observation_level: ObservationLevel,
    ) -> Result<Self> {
        let prepared = Arc::new(PreparedRuntimePlan::from_plan(&plan));
        Self::from_shared_prepared_config(
            plan,
            prepared,
            fingerprint,
            seed,
            observation_level,
            false,
        )
    }

    pub fn from_shared_profiled(
        plan: Arc<ExecutionPlan>,
        fingerprint: String,
        seed: u64,
        observation_level: ObservationLevel,
    ) -> Result<Self> {
        let prepared = Arc::new(PreparedRuntimePlan::from_plan(&plan));
        Self::from_shared_prepared_config(
            plan,
            prepared,
            fingerprint,
            seed,
            observation_level,
            true,
        )
    }

    pub(crate) fn from_shared_prepared_with_observation(
        plan: Arc<ExecutionPlan>,
        prepared: Arc<PreparedRuntimePlan>,
        fingerprint: String,
        seed: u64,
        observation_level: ObservationLevel,
    ) -> Result<Self> {
        Self::from_shared_prepared_config(
            plan,
            prepared,
            fingerprint,
            seed,
            observation_level,
            false,
        )
    }

    fn from_shared_prepared_config(
        plan: Arc<ExecutionPlan>,
        prepared: Arc<PreparedRuntimePlan>,
        fingerprint: String,
        seed: u64,
        observation_level: ObservationLevel,
        profile_enabled: bool,
    ) -> Result<Self> {
        plan.validate()?;
        let failure_components_by_aircraft: Vec<Vec<usize>> = (0..plan.aircraft.len())
            .map(|aircraft_index| {
                plan.components
                    .iter()
                    .filter(|component| {
                        component.failure_rate_per_hour > 0.0
                            && component.aircraft_indexes.contains(&aircraft_index)
                    })
                    .map(|item| item.index)
                    .collect()
            })
            .collect();
        let aircraft = plan
            .aircraft
            .iter()
            .enumerate()
            .map(|(aircraft_index, item)| AircraftState {
                tail_number: item.tail_number.clone(),
                aircraft_type: item.aircraft_type.clone(),
                model: item.model.clone(),
                state: item.initial_state.clone(),
                current_mission_index: None,
                return_time: None,
                prepared_mission_indexes: BTreeSet::new(),
                operations_day: None,
                daily_takeoffs: 0,
                operations_plan_group_id: String::new(),
                last_operations_mission_index: None,
                prepared_operations_day: None,
                postflight_required: false,
                postflight_due: false,
                flight_hours: item.initial_flight_hours,
                takeoff_count: item.initial_cycles,
                landing_count: item.initial_cycles,
                failure_remaining_by_slot: vec![
                    None;
                    failure_components_by_aircraft[aircraft_index].len()
                ],
                component_failure_minutes_by_slot: vec![
                    None;
                    failure_components_by_aircraft
                        [aircraft_index]
                        .len()
                ],
                failed_component_index: None,
                failed_component_minute: None,
                in_flight_failure: false,
            })
            .collect();
        let resources = plan
            .resource_nodes
            .iter()
            .map(|item| ResourceState {
                personnel_capacity: item.personnel_capacity,
                equipment_capacity: item.equipment_capacity,
                personnel_in_use: 0,
                equipment_in_use: 0,
                inventory: item.inventory.iter().cloned().collect(),
            })
            .collect();
        let preventive_cycles = plan
            .preventive_cycles
            .iter()
            .map(|item| PreventiveCycleState {
                life_flight_hours: item.initial_flight_hours,
                life_landing_cycles: item.initial_landing_cycles,
                last_preventive_minute: -item.initial_calendar_days * 1440,
            })
            .collect();
        let mut activity_by_group_phase: HashMap<(String, String), Vec<usize>> = HashMap::new();
        for activity in &plan.activities {
            if !activity.phase.is_empty() {
                activity_by_group_phase
                    .entry((activity.plan_group_id.clone(), activity.phase.clone()))
                    .or_default()
                    .push(activity.index);
            }
        }
        let mut children_by_component: HashMap<i64, Vec<usize>> = HashMap::new();
        for component in &plan.components {
            children_by_component
                .entry(component.parent_index)
                .or_default()
                .push(component.index);
        }
        let execution_phases = plan
            .phases
            .iter()
            .enumerate()
            .map(|(index, name)| ExecutionPhase::from_name(index, name))
            .collect();
        let mission_count = plan.missions.len();
        let mut runtime = Self {
            plan,
            prepared,
            execution_phases,
            fingerprint,
            seed,
            minute: 0,
            phase: "initialize".into(),
            running: true,
            stop_reason: String::new(),
            observation_level,
            profile_enabled,
            profile: RuntimeProfile::default(),
            trace: vec![],
            sample_requests: vec![],
            rng: PythonRandom::from_u64(seed),
            aircraft,
            missions: vec![MissionState::default(); mission_count],
            jobs: vec![],
            waiting_job_indexes: BTreeSet::new(),
            waiting_dispatch_jobs: HashMap::new(),
            running_job_indexes: BTreeSet::new(),
            dispatch_cache: vec![],
            resources,
            preventive_cycles,
            shipments: vec![],
            job_sequence: 0,
            launched_sorties: 0,
            completed_sorties: 0,
            cancelled_sorties: 0,
            delayed_sorties: 0,
            total_departure_delay: 0,
            lru_failures: 0,
            in_flight_failures: 0,
            failed_sorties: 0,
            preventive_maintenance_events: 0,
            spare_demand_total: 0,
            spare_immediately_filled_total: 0,
            spare_consumed_total: 0,
            shortage_events: 0,
            transport_replenishment_events: 0,
            total_transport_delay: 0,
            delayed_missions: HashSet::new(),
            activity_by_group_phase,
            children_by_component,
            failure_components_by_aircraft,
        };
        runtime.initialize_failure_timers();
        Ok(runtime)
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn sample_failure_minutes(
        &mut self,
        component_index: usize,
        aircraft_index: usize,
        reason: &str,
    ) -> f64 {
        if self.profile_enabled {
            self.profile.plan_spec_clones += 1;
        }
        let component = self.plan.components[component_index].clone();
        let mut minimum = f64::INFINITY;
        for quantity_index in 0..component.quantity {
            let started = Instant::now();
            let value = if component.failure_rate_per_hour > 0.0 {
                self.rng.expovariate(component.failure_rate_per_hour) * 60.0
            } else {
                f64::INFINITY
            };
            if self.profile_enabled {
                self.profile.rng_requests += 1;
                self.profile.rng_ns = self.profile.rng_ns.saturating_add(elapsed_ns(started));
            }
            self.sample_requests.push(json!({
                "sequence": self.sample_requests.len() + 1, "time": self.minute, "phase": self.phase,
                "stream": "legacy-sequential-v1", "distribution": "exponential",
                "entity": self.aircraft[aircraft_index].tail_number,
                "component_id": component.component_id, "quantity_index": quantity_index,
                "rate_per_hour": component.failure_rate_per_hour, "value_minutes": value,
                "reason": reason, "source_path": component.source_path,
            }));
            minimum = minimum.min(value);
        }
        minimum
    }

    fn initialize_failure_timers(&mut self) {
        for aircraft_index in 0..self.aircraft.len() {
            for component_index in 0..self.plan.components.len() {
                if self.plan.components[component_index].failure_rate_per_hour <= 0.0 {
                    continue;
                }
                let sampled =
                    self.sample_failure_minutes(component_index, aircraft_index, "initialize");
                if let Some(component_slot) = self.failure_components_by_aircraft[aircraft_index]
                    .iter()
                    .position(|item| *item == component_index)
                {
                    self.aircraft[aircraft_index].failure_remaining_by_slot[component_slot] =
                        Some(sampled);
                }
            }
        }
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn emit<F>(
        &mut self,
        kind: &str,
        rule_id: &str,
        entity: String,
        details: F,
        source_path: Option<String>,
    ) where
        F: FnOnce() -> Value,
    {
        if self.profile_enabled {
            self.profile.trace_events_attempted += 1;
        }
        if self.observation_level == ObservationLevel::Summary {
            return;
        }
        let started = Instant::now();
        let details = details();
        let source = source_path
            .or_else(|| {
                details
                    .get("activity_id")
                    .and_then(Value::as_str)
                    .and_then(|id| {
                        self.plan
                            .activities
                            .iter()
                            .find(|item| item.activity_id == id)
                            .map(|item| item.source_path.clone())
                    })
            })
            .or_else(|| {
                details
                    .get("mission_id")
                    .and_then(Value::as_str)
                    .and_then(|id| {
                        self.plan
                            .missions
                            .iter()
                            .find(|item| item.mission_id == id)
                            .map(|item| item.source_path.clone())
                    })
            })
            .or_else(|| {
                self.plan
                    .missions
                    .iter()
                    .find(|item| item.mission_id == entity)
                    .map(|item| item.source_path.clone())
            });
        let event = json!({
            "sequence": self.trace.len() + 1, "time": self.minute, "phase": self.phase,
            "kind": kind, "rule_id": rule_id, "entity": entity, "source_path": source,
            "details": details,
        });
        if self.profile_enabled {
            self.profile.trace_events_materialized += 1;
            self.profile.trace_event_string_values += count_string_values(&event);
            self.profile.trace_event_build_ns = self
                .profile
                .trace_event_build_ns
                .saturating_add(elapsed_ns(started));
        }
        self.trace.push(event);
    }

    fn mission_id(&self, index: Option<usize>) -> Value {
        index
            .map(|item| Value::String(self.plan.missions[item].mission_id.clone()))
            .unwrap_or(Value::Null)
    }

    fn matches_type(&self, aircraft_index: usize, required_aircraft_type: &str) -> bool {
        let required = tokens(required_aircraft_type);
        if required.is_empty() {
            return true;
        }
        let aircraft = &self.aircraft[aircraft_index];
        !required.is_disjoint(
            &tokens(&aircraft.aircraft_type)
                .union(&tokens(&aircraft.model))
                .cloned()
                .collect(),
        )
    }

    fn activity_for(&self, group_id: &str, phase: &str, aircraft_index: usize) -> Result<usize> {
        let aircraft = &self.aircraft[aircraft_index];
        let aircraft_tokens: HashSet<_> = tokens(&aircraft.aircraft_type)
            .union(&tokens(&aircraft.model))
            .cloned()
            .collect();
        let candidates: Vec<_> = self
            .activity_by_group_phase
            .get(&(group_id.to_string(), phase.to_string()))
            .into_iter()
            .flatten()
            .filter(|index| {
                let required = tokens(&self.plan.activities[**index].aircraft_model);
                required.is_empty() || !required.is_disjoint(&aircraft_tokens)
            })
            .copied()
            .collect();
        if candidates.len() != 1 {
            bail!(
                "operations group {:?} requires exactly one compatible {} activity",
                group_id,
                phase
            );
        }
        Ok(candidates[0])
    }

    fn preparation_activity(
        &mut self,
        mission_index: usize,
        aircraft_index: usize,
    ) -> Result<usize> {
        let mission = &self.plan.missions[mission_index];
        let day = self.minute.max(mission.planned_start) / 1440;
        let phase = if self.aircraft[aircraft_index].operations_day == Some(day)
            && self.aircraft[aircraft_index].daily_takeoffs != 0
        {
            "relaunch"
        } else {
            "preflight"
        };
        self.aircraft[aircraft_index].prepared_operations_day = Some(day);
        self.activity_for(&mission.operations_plan_group_id, phase, aircraft_index)
    }

    fn create_job(
        &mut self,
        aircraft_index: usize,
        activity_index: usize,
        kind: &str,
        mission_index: Option<usize>,
        component_index: Option<usize>,
        preventive_cycle_index: Option<usize>,
    ) -> Result<()> {
        self.job_sequence += 1;
        let job_id = format!("job-{:04}", self.job_sequence);
        let maintenance_method = if matches!(kind, "repair" | "preventive") {
            Some(self.maintenance_method(activity_index, kind, &job_id))
        } else {
            None
        };
        let prepared_activity = &self.prepared.activities[activity_index];
        let activity_is_empty = prepared_activity.steps.is_empty();
        let mut injected_spares = vec![];
        if kind == "repair"
            && maintenance_method.as_deref() == Some("replacement")
            && !prepared_activity.steps.is_empty()
            && !prepared_activity
                .steps
                .iter()
                .any(|step| !step.static_spares.is_empty())
            && let Some(component_index) = component_index
        {
            let component = &self.plan.components[component_index];
            if component.product_type.trim().eq_ignore_ascii_case("LRU")
                && !component.product_id.is_empty()
            {
                injected_spares.push((component.product_id.clone(), 1));
            }
        }
        self.jobs.push(JobState {
            job_id: job_id.clone(),
            aircraft_index,
            kind: kind.into(),
            activity_index,
            mission_index,
            state: "waiting".into(),
            step_index: 0,
            remaining: 0,
            started_time: None,
            completed_time: None,
            reserved_personnel: 0,
            reserved_equipment: 0,
            component_index,
            preventive_cycle_index,
            maintenance_method,
            injected_spares,
            requested_spare_steps: HashSet::new(),
            consumed_spare_steps: HashSet::new(),
            shortage_signature: None,
            spare_reservations: BTreeMap::new(),
        });
        let job_index = self.jobs.len() - 1;
        debug_assert_eq!(job_index, self.dispatch_cache.len());
        self.dispatch_cache.push(None);
        let inserted = self.waiting_job_indexes.insert(job_index);
        debug_assert!(inserted, "new waiting job duplicated in active index");
        self.waiting_dispatch_jobs
            .entry((activity_index, 0))
            .or_default()
            .insert(job_index);
        self.update_active_job_peaks();
        self.debug_assert_active_job_indexes();
        let tail_number = self.aircraft[aircraft_index].tail_number.clone();
        let mission_id = self.mission_id(mission_index);
        let activity_id = self.plan.activities[activity_index].activity_id.clone();
        let operations_phase = self.plan.activities[activity_index].phase.clone();
        self.emit(
            "operations_phase_created",
            "daily-v1.create-operation",
            job_id,
            || {
                json!({"tail_number": tail_number,
                "mission_id": mission_id, "activity_id": activity_id,
                "operations_phase": operations_phase})
            },
            None,
        );
        if activity_is_empty {
            self.transition_job_state(job_index, "completed");
            self.jobs[job_index].started_time = Some(self.minute);
            self.jobs[job_index].completed_time = Some(self.minute);
            self.complete_job(job_index)?;
        }
        Ok(())
    }

    fn maintenance_method(&mut self, activity_index: usize, kind: &str, job_id: &str) -> String {
        let activity = &self.plan.activities[activity_index];
        let methods = if activity.maintenance_methods.is_empty() {
            vec!["non_replacement".to_string()]
        } else {
            activity.maintenance_methods.clone()
        };
        let mut ratio = activity.replacement_ratio;
        if methods == ["replacement"] {
            ratio = 1.0;
        } else if !methods.iter().any(|item| item == "replacement") {
            ratio = 0.0;
        }
        let occurrence = 1 + self
            .jobs
            .iter()
            .filter(|job| job.kind == kind && job.maintenance_method.is_some())
            .count();
        let stream_key = format!("{}|maintenance-method|{}|{}", self.seed, kind, occurrence);
        let digest = Sha256::digest(stream_key.as_bytes());
        let mut rng = PythonRandom::from_be_bytes(&digest[..16]);
        let started = Instant::now();
        let roll = rng.random();
        if self.profile_enabled {
            self.profile.rng_requests += 1;
            self.profile.rng_ns = self.profile.rng_ns.saturating_add(elapsed_ns(started));
        }
        let method = if methods.iter().any(|item| item == "replacement") && roll < ratio {
            "replacement"
        } else {
            "non_replacement"
        }
        .to_string();
        self.emit(
            "maintenance_method_selected",
            "maintenance.select-method",
            job_id.to_string(),
            || {
                json!({"maintenance_kind": kind, "maintenance_method": method,
                "replacement_ratio": ratio, "decision_roll": roll,
                "rng_stream": hex_prefix(&digest, 8), "maintenance_occurrence": occurrence})
            },
            Some(activity.source_path.clone()),
        );
        method
    }

    fn complete_job(&mut self, job_index: usize) -> Result<()> {
        let snapshot = self.jobs[job_index].clone();
        if self.profile_enabled {
            self.profile.plan_spec_clones += 1;
        }
        let activity = self.plan.activities[snapshot.activity_index].clone();
        let aircraft_index = snapshot.aircraft_index;
        let tail_number = self.aircraft[aircraft_index].tail_number.clone();
        let mission_id = self.mission_id(snapshot.mission_index);
        self.emit(
            "operations_phase_completed",
            "daily-v1.complete-operation",
            snapshot.job_id.clone(),
            || {
                json!({"tail_number": tail_number,
                "mission_id": mission_id,
                "activity_id": activity.activity_id, "operations_phase": activity.phase})
            },
            None,
        );
        match snapshot.kind.as_str() {
            "preflight" => {
                if let Some(mission_index) = snapshot.mission_index {
                    self.aircraft[aircraft_index]
                        .prepared_mission_indexes
                        .insert(mission_index);
                    self.aircraft[aircraft_index].current_mission_index = Some(mission_index);
                    self.aircraft[aircraft_index].state = "mission_ready".into();
                    let mission_id = self.mission_id(Some(mission_index));
                    self.emit(
                        "preflight_completed",
                        "mission.preflight-complete",
                        self.aircraft[aircraft_index].tail_number.clone(),
                        || json!({"mission_id": mission_id}),
                        None,
                    );
                }
            }
            "postflight" => {
                self.aircraft[aircraft_index].state = "available".into();
                self.aircraft[aircraft_index].postflight_required = false;
                self.aircraft[aircraft_index].postflight_due = false;
                self.emit(
                    "postflight_completed",
                    "daily-v1.postflight-complete",
                    self.aircraft[aircraft_index].tail_number.clone(),
                    || json!({}),
                    None,
                );
            }
            "repair" => {
                self.aircraft[aircraft_index].state = "available".into();
                if let Some(component_index) = snapshot.component_index {
                    let sampled = self.sample_failure_minutes(
                        component_index,
                        aircraft_index,
                        "repair_completed",
                    );
                    let component_slot = self.failure_components_by_aircraft[aircraft_index]
                        .iter()
                        .position(|item| *item == component_index)
                        .ok_or_else(|| {
                            anyhow::anyhow!(
                                "component {:?} has no failure slot for aircraft {:?}",
                                self.plan.components[component_index].component_id,
                                self.aircraft[aircraft_index].tail_number
                            )
                        })?;
                    self.aircraft[aircraft_index].failure_remaining_by_slot[component_slot] =
                        Some(sampled);
                }
                self.aircraft[aircraft_index].failed_component_index = None;
                self.aircraft[aircraft_index].failed_component_minute = None;
                self.aircraft[aircraft_index]
                    .component_failure_minutes_by_slot
                    .fill(None);
                self.aircraft[aircraft_index].in_flight_failure = false;
                let component_id = snapshot
                    .component_index
                    .map(|index| self.plan.components[index].component_id.clone());
                self.emit(
                    "repair_completed",
                    "maintenance.repair-complete",
                    self.aircraft[aircraft_index].tail_number.clone(),
                    || json!({"component_id": component_id}),
                    None,
                );
            }
            "preventive" => {
                if let Some(cycle_index) = snapshot.preventive_cycle_index {
                    if self.profile_enabled {
                        self.profile.plan_spec_clones += 1;
                    }
                    let spec = self.plan.preventive_cycles[cycle_index].clone();
                    if spec.flight_hours > 0.0 {
                        self.preventive_cycles[cycle_index].life_flight_hours = 0.0;
                    }
                    if spec.landing_cycles > 0 {
                        self.preventive_cycles[cycle_index].life_landing_cycles = 0;
                    }
                    self.preventive_cycles[cycle_index].last_preventive_minute = self.minute;
                    self.aircraft[aircraft_index].state = "available".into();
                    let first_cycle = self
                        .plan
                        .preventive_cycles
                        .iter()
                        .position(|item| item.aircraft_index == aircraft_index);
                    if first_cycle == Some(cycle_index) {
                        self.aircraft[aircraft_index].flight_hours = 0.0;
                        self.aircraft[aircraft_index].takeoff_count = 0;
                        self.aircraft[aircraft_index].landing_count = 0;
                    }
                    self.emit(
                        "preventive_completed",
                        "maintenance.preventive-complete",
                        self.aircraft[aircraft_index].tail_number.clone(),
                        || json!({"activity_id": activity.activity_id}),
                        None,
                    );
                }
            }
            _ => {}
        }
        Ok(())
    }

    fn active_preflight_aircraft(&self, mission_index: usize) -> HashSet<usize> {
        self.jobs
            .iter()
            .filter(|job| {
                job.kind == "preflight"
                    && job.mission_index == Some(mission_index)
                    && matches!(job.state.as_str(), "waiting" | "running")
            })
            .map(|job| job.aircraft_index)
            .collect()
    }

    fn ready_for_mission(&self, aircraft_index: usize, mission_index: usize) -> bool {
        let aircraft = &self.aircraft[aircraft_index];
        if !aircraft.prepared_mission_indexes.contains(&mission_index) {
            return false;
        }
        if aircraft.state == "mission_ready" {
            return aircraft.current_mission_index == Some(mission_index);
        }
        aircraft.state == "available"
            && (aircraft.current_mission_index.is_none()
                || aircraft.current_mission_index == Some(mission_index))
    }

    fn commissioned_count(&self, mission_index: usize) -> usize {
        let mission = &self.plan.missions[mission_index];
        let mut result = self.active_preflight_aircraft(mission_index);
        result.extend((0..self.aircraft.len()).filter(|index| {
            self.ready_for_mission(*index, mission_index)
                && self.matches_type(*index, &mission.required_aircraft_type)
        }));
        result.len()
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_mission_returns(&mut self) -> Result<()> {
        self.count_scan("aircraft", self.aircraft.len());
        for aircraft_index in 0..self.aircraft.len() {
            if self.aircraft[aircraft_index].state == "flying"
                && self.aircraft[aircraft_index]
                    .return_time
                    .is_some_and(|time| time <= self.minute)
            {
                self.return_aircraft(aircraft_index, false)?;
            }
        }
        Ok(())
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_transport_arrivals(&mut self) {
        self.count_scan("job", self.jobs.len());
        self.count_scan("shipment", self.shipments.len());
        for job_index in 0..self.jobs.len() {
            if self.jobs[job_index].state != "cancelled"
                || self.jobs[job_index].spare_reservations.is_empty()
            {
                continue;
            }
            let node_index =
                self.plan.activities[self.jobs[job_index].activity_index].resource_node_index;
            let returned: Vec<_> = self.jobs[job_index]
                .spare_reservations
                .iter()
                .map(|(product_id, quantity)| (product_id.clone(), *quantity))
                .collect();
            let reservations = std::mem::take(&mut self.jobs[job_index].spare_reservations);
            self.count_map_writes(reservations.len());
            for (product_id, quantity) in reservations {
                *self.resources[node_index]
                    .inventory
                    .entry(product_id.clone())
                    .or_default() += quantity;
                self.invalidate_dispatch_resource("inventory", node_index, Some(&product_id));
            }
            self.emit(
                "organization_spare_reservation_returned",
                "inventory.return-cancelled-reservation",
                self.jobs[job_index].job_id.clone(),
                || json!({
                    "products": returned.into_iter().map(|(product_id, quantity)|
                        json!({"product_id": product_id, "quantity": quantity})).collect::<Vec<_>>(),
                    "node_index": node_index,
                }),
                None,
            );
        }
        let mut arrived = Vec::new();
        self.shipments.retain(|item| {
            if item.arrival_minute <= self.minute {
                arrived.push(item.clone());
                false
            } else {
                true
            }
        });
        for shipment in arrived {
            let job_index = self
                .jobs
                .iter()
                .position(|item| item.job_id == shipment.job_id);
            let reserved = job_index.is_some_and(|index| {
                self.jobs[index].state == "waiting"
                    && self.jobs[index].step_index == shipment.step_index
            });
            if let Some(index) = job_index.filter(|_| reserved) {
                *self.jobs[index]
                    .spare_reservations
                    .entry(shipment.product_id.clone())
                    .or_default() += shipment.quantity;
                self.invalidate_dispatch_job_cache(index);
            } else {
                *self.resources[shipment.destination_node_index]
                    .inventory
                    .entry(shipment.product_id.clone())
                    .or_default() += shipment.quantity;
                self.invalidate_dispatch_resource(
                    "inventory",
                    shipment.destination_node_index,
                    Some(&shipment.product_id),
                );
            }
            self.count_map_writes(1);
            if self.profile_enabled {
                self.profile.plan_spec_clones += 1;
            }
            let route = self.plan.supply_routes[shipment.route_index].clone();
            self.total_transport_delay += shipment.arrival_minute - shipment.requested_minute;
            let trace_shipment = shipment.clone();
            let trace_route = route.clone();
            self.emit(
                "transport_arrived",
                "inventory.transport-arrival",
                shipment.job_id.clone(),
                || json!({"job_id": trace_shipment.job_id, "step_index": trace_shipment.step_index,
                    "product_id": trace_shipment.product_id, "quantity": trace_shipment.quantity,
                    "source_node_index": trace_shipment.source_node_index,
                    "destination_node_index": trace_shipment.destination_node_index,
                    "supply_mode": trace_route.supply_mode, "relation_id": trace_route.relation_id,
                    "reserved_for_job": reserved, "requested_minute": trace_shipment.requested_minute,
                    "arrival_minute": trace_shipment.arrival_minute}),
                Some(route.source_path.clone()),
            );
            self.emit(
                "organization_transport_arrived",
                "organization.transport-arrival",
                shipment.job_id.clone(),
                || {
                    json!({"job_id": shipment.job_id, "step_index": shipment.step_index,
                    "product_id": shipment.product_id, "quantity": shipment.quantity,
                    "source_node_index": shipment.source_node_index,
                    "destination_node_index": shipment.destination_node_index,
                    "supply_mode": route.supply_mode, "relation_id": route.relation_id,
                    "reserved_for_job": reserved, "requested_minute": shipment.requested_minute,
                    "arrival_minute": shipment.arrival_minute})
                },
                Some(route.source_path),
            );
        }
    }

    fn dispatch_remote_spares(
        &mut self,
        job_index: usize,
        activity_index: usize,
        requirements: &[(String, i64)],
    ) {
        let destination_index = self.plan.activities[activity_index].resource_node_index;
        self.count_map_reads(requirements.len() * 2);
        for (product_id, needed) in requirements {
            let available = self.resources[destination_index]
                .inventory
                .get(product_id)
                .copied()
                .unwrap_or(0)
                + self.jobs[job_index]
                    .spare_reservations
                    .get(product_id)
                    .copied()
                    .unwrap_or(0);
            let shortage = (*needed - available).max(0);
            let already = self.shipments.iter().any(|item| {
                item.job_id == self.jobs[job_index].job_id
                    && item.step_index == self.jobs[job_index].step_index
                    && item.product_id == *product_id
            });
            if shortage <= 0 || already {
                continue;
            }
            for route_index in 0..self.plan.supply_routes.len() {
                if self.profile_enabled {
                    self.profile.plan_spec_clones += 1;
                }
                let route = self.plan.supply_routes[route_index].clone();
                if route.destination_node_index != destination_index
                    || (!route.product_id.is_empty() && route.product_id != *product_id)
                {
                    continue;
                }
                let stock = self.resources[route.source_node_index]
                    .inventory
                    .get(product_id)
                    .copied()
                    .unwrap_or(0);
                self.count_map_reads(1);
                let moved = shortage.min(route.capacity).min(stock);
                if moved <= 0 {
                    continue;
                }
                *self.resources[route.source_node_index]
                    .inventory
                    .entry(product_id.clone())
                    .or_default() -= moved;
                self.count_map_writes(1);
                self.invalidate_dispatch_resource(
                    "inventory",
                    route.source_node_index,
                    Some(product_id),
                );
                let shipment = ShipmentState {
                    job_id: self.jobs[job_index].job_id.clone(),
                    step_index: self.jobs[job_index].step_index,
                    product_id: product_id.clone(),
                    quantity: moved,
                    source_node_index: route.source_node_index,
                    destination_node_index: destination_index,
                    requested_minute: self.minute,
                    arrival_minute: self.minute + route.transport_minutes.max(1),
                    route_index: route.index,
                };
                self.shipments.push(shipment.clone());
                self.transport_replenishment_events += 1;
                let trace_shipment = shipment.clone();
                let trace_route = route.clone();
                self.emit(
                    "organization_supply_selected",
                    "organization.select-supplier",
                    shipment.job_id.clone(),
                    || json!({"job_id": trace_shipment.job_id, "step_index": trace_shipment.step_index,
                        "product_id": trace_shipment.product_id, "quantity": trace_shipment.quantity,
                        "source_node_index": trace_shipment.source_node_index,
                        "destination_node_index": trace_shipment.destination_node_index,
                        "arrival_minute": trace_shipment.arrival_minute,
                        "supply_mode": trace_route.supply_mode, "relation_id": trace_route.relation_id}),
                    Some(route.source_path.clone()),
                );
                self.emit(
                    "organization_transport_dispatched",
                    "organization.dispatch-transport",
                    shipment.job_id.clone(),
                    || {
                        json!({"job_id": shipment.job_id, "step_index": shipment.step_index,
                        "product_id": shipment.product_id, "quantity": shipment.quantity,
                        "source_node_index": shipment.source_node_index,
                        "destination_node_index": shipment.destination_node_index,
                        "arrival_minute": shipment.arrival_minute,
                        "supply_mode": route.supply_mode, "relation_id": route.relation_id})
                    },
                    Some(route.source_path),
                );
                break;
            }
        }
    }

    fn return_aircraft(&mut self, aircraft_index: usize, early_return: bool) -> Result<()> {
        let mission_index = self.aircraft[aircraft_index].current_mission_index;
        self.aircraft[aircraft_index].postflight_required = true;
        let mission_start = mission_index
            .map(|index| {
                self.missions[index]
                    .actual_start
                    .unwrap_or(self.plan.missions[index].planned_start)
            })
            .unwrap_or(self.minute);
        let end_minute = if early_return {
            self.minute
        } else {
            self.aircraft[aircraft_index]
                .return_time
                .unwrap_or(self.minute)
        };
        let flight_hours = ((end_minute - mission_start) as f64 / 60.0).max(0.0);
        self.aircraft[aircraft_index].flight_hours += flight_hours;
        self.aircraft[aircraft_index].landing_count += 1;
        for (cycle_index, spec) in self.plan.preventive_cycles.iter().enumerate() {
            if spec.aircraft_index == aircraft_index {
                self.preventive_cycles[cycle_index].life_flight_hours += flight_hours;
                self.preventive_cycles[cycle_index].life_landing_cycles += 1;
            }
        }
        let failed_on_return = self.aircraft[aircraft_index].in_flight_failure
            || self.aircraft[aircraft_index]
                .component_failure_minutes_by_slot
                .iter()
                .any(Option::is_some);
        if failed_on_return {
            self.aircraft[aircraft_index].state = "maintenance".into();
            if self.aircraft[aircraft_index].in_flight_failure {
                self.failed_sorties += 1;
            }
            let component_index = self.aircraft[aircraft_index]
                .failed_component_index
                .unwrap_or_else(|| {
                    self.failure_components_by_aircraft[aircraft_index]
                        .iter()
                        .copied()
                        .zip(
                            self.aircraft[aircraft_index]
                                .component_failure_minutes_by_slot
                                .iter(),
                        )
                        .filter_map(|(component_index, minute)| {
                            minute.map(|minute| (component_index, minute))
                        })
                        .min_by_key(|(component_index, minute)| (*minute, *component_index))
                        .unwrap()
                        .0
                });
            if self.profile_enabled {
                self.profile.plan_spec_clones += 1;
            }
            let component = self.plan.components[component_index].clone();
            if component.repair_activity_index < 0 {
                bail!(
                    "no repair activity for component {:?}",
                    component.component_id
                );
            }
            self.create_job(
                aircraft_index,
                component.repair_activity_index as usize,
                "repair",
                mission_index,
                Some(component_index),
                None,
            )?;
            if let Some(mission_index) =
                mission_index.filter(|_| self.aircraft[aircraft_index].in_flight_failure)
            {
                if !self.missions[mission_index]
                    .failed_aircraft
                    .contains(&aircraft_index)
                {
                    self.missions[mission_index]
                        .failed_aircraft
                        .push(aircraft_index);
                }
                let active = self.missions[mission_index]
                    .assigned_aircraft
                    .iter()
                    .filter(|item| !self.missions[mission_index].failed_aircraft.contains(item))
                    .count();
                if active < self.plan.missions[mission_index].min_required_aircraft {
                    self.missions[mission_index].status = "failed".into();
                    self.missions[mission_index].return_time = Some(self.minute);
                }
            }
            let mission_id = self.mission_id(mission_index);
            self.emit(
                if early_return {
                    "mission_failed_returned"
                } else {
                    "mission_returned_with_component_failure"
                },
                "failure.return-and-create-repair",
                self.aircraft[aircraft_index].tail_number.clone(),
                || json!({"mission_id": mission_id, "component_id": component.component_id}),
                None,
            );
        } else {
            self.completed_sorties += 1;
            self.aircraft[aircraft_index].state = "available".into();
        }
        self.aircraft[aircraft_index].current_mission_index = None;
        self.aircraft[aircraft_index].return_time = None;
        if let Some(mission_index) = mission_index {
            let active = self.aircraft.iter().any(|item| {
                item.state == "flying" && item.current_mission_index == Some(mission_index)
            });
            if self.missions[mission_index].status == "launched" && !active {
                self.missions[mission_index].status = "completed".into();
            }
        }
        if !failed_on_return {
            let mission_id = self.mission_id(mission_index);
            self.emit(
                "mission_returned",
                "mission.normal-return",
                self.aircraft[aircraft_index].tail_number.clone(),
                || json!({"mission_id": mission_id}),
                None,
            );
        }
        Ok(())
    }

    fn release_resources(
        &mut self,
        job_index: usize,
        node_index: usize,
        step_index: usize,
    ) -> Result<()> {
        self.resources[node_index].personnel_in_use -= self.jobs[job_index].reserved_personnel;
        self.resources[node_index].equipment_in_use -= self.jobs[job_index].reserved_equipment;
        if self.resources[node_index].personnel_in_use < 0
            || self.resources[node_index].equipment_in_use < 0
        {
            bail!("resource ledger became negative");
        }
        let reserved_personnel = self.jobs[job_index].reserved_personnel;
        let reserved_equipment = self.jobs[job_index].reserved_equipment;
        let personnel_in_use = self.resources[node_index].personnel_in_use;
        let equipment_in_use = self.resources[node_index].equipment_in_use;
        if reserved_personnel != 0 {
            self.invalidate_dispatch_resource("personnel_capacity", node_index, None);
        }
        if reserved_equipment != 0 {
            self.invalidate_dispatch_resource("equipment_capacity", node_index, None);
        }
        self.emit(
            "resources_released",
            "resource.release",
            self.jobs[job_index].job_id.clone(),
            || {
                json!({"node_index": node_index, "step_index": step_index,
                "personnel": reserved_personnel,
                "equipment": reserved_equipment,
                "personnel_in_use": personnel_in_use,
                "equipment_in_use": equipment_in_use})
            },
            None,
        );
        self.jobs[job_index].reserved_personnel = 0;
        self.jobs[job_index].reserved_equipment = 0;
        Ok(())
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_job_progress(&mut self) -> Result<()> {
        self.count_scan("job", self.jobs.len());
        self.debug_assert_active_job_indexes();
        let running: Vec<_> = self.running_job_indexes.iter().copied().collect();
        if self.profile_enabled {
            self.profile.job_progress_candidate_visits += running.len() as u64;
        }
        for job_index in running {
            self.jobs[job_index].remaining -= 1;
            if self.jobs[job_index].remaining > 0 {
                continue;
            }
            let activity_index = self.jobs[job_index].activity_index;
            let step_position = self.jobs[job_index].step_index;
            let activity = &self.prepared.activities[activity_index];
            let step = &activity.steps[step_position];
            let node_index = activity.resource_node_index;
            let step_index = step.index;
            let step_code = step.code.clone();
            let step_count = activity.steps.len();
            self.release_resources(job_index, node_index, step_index)?;
            self.emit(
                "operations_step_completed",
                "work.serial-step-complete",
                self.jobs[job_index].job_id.clone(),
                || json!({"step_index": step_index, "activity_code": step_code}),
                None,
            );
            self.jobs[job_index].step_index += 1;
            if self.jobs[job_index].step_index >= step_count {
                self.transition_job_state(job_index, "completed");
                self.jobs[job_index].completed_time = Some(self.minute);
                self.complete_job(job_index)?;
            } else {
                self.transition_job_state(job_index, "waiting");
                self.jobs[job_index].remaining = 0;
            }
        }
        Ok(())
    }

    fn failure_reaches_root(&self, aircraft_index: usize) -> bool {
        let mut failed: HashSet<usize> = self.failure_components_by_aircraft[aircraft_index]
            .iter()
            .copied()
            .zip(
                self.aircraft[aircraft_index]
                    .component_failure_minutes_by_slot
                    .iter(),
            )
            .filter_map(|(component_index, minute)| minute.map(|_| component_index))
            .collect();
        loop {
            let mut changed = false;
            for component in self.plan.components.iter().rev() {
                if failed.contains(&component.index)
                    || !component.aircraft_indexes.contains(&aircraft_index)
                {
                    continue;
                }
                let count = self
                    .children_by_component
                    .get(&(component.index as i64))
                    .into_iter()
                    .flatten()
                    .filter(|child| failed.contains(child))
                    .count();
                if count > 0 && count >= component.failure_threshold {
                    failed.insert(component.index);
                    changed = true;
                }
            }
            if !changed {
                break;
            }
        }
        self.plan.components.iter().any(|component| {
            failed.contains(&component.index)
                && component.parent_index < 0
                && component.aircraft_indexes.contains(&aircraft_index)
        })
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_failures(&mut self) -> Result<()> {
        if self.plan.components.is_empty() {
            return Ok(());
        }
        self.count_scan("aircraft", self.aircraft.len());
        for aircraft_index in 0..self.aircraft.len() {
            if self.aircraft[aircraft_index].state != "flying"
                || self.aircraft[aircraft_index].in_flight_failure
            {
                continue;
            }
            let component_count = self.failure_components_by_aircraft[aircraft_index].len();
            self.count_scan("component", component_count);
            for component_slot in 0..component_count {
                let component_index =
                    self.failure_components_by_aircraft[aircraft_index][component_slot];
                if self.aircraft[aircraft_index].component_failure_minutes_by_slot[component_slot]
                    .is_some()
                {
                    continue;
                }
                let mut remaining =
                    match self.aircraft[aircraft_index].failure_remaining_by_slot[component_slot] {
                        Some(remaining) => remaining,
                        None => self.sample_failure_minutes(
                            component_index,
                            aircraft_index,
                            "missing_timer",
                        ),
                    };
                remaining -= 1.0;
                self.aircraft[aircraft_index].failure_remaining_by_slot[component_slot] =
                    Some(remaining);
                if remaining > 0.0 {
                    continue;
                }
                self.aircraft[aircraft_index].component_failure_minutes_by_slot[component_slot] =
                    Some(self.minute);
                self.lru_failures += 1;
                if self.profile_enabled {
                    self.profile.plan_spec_clones += 1;
                }
                let component = self.plan.components[component_index].clone();
                self.emit(
                    "component_failed",
                    "failure.flight-exposure-countdown",
                    self.aircraft[aircraft_index].tail_number.clone(),
                    || json!({"component_id": component.component_id}),
                    Some(component.source_path.clone()),
                );
                if self.failure_reaches_root(aircraft_index) {
                    self.aircraft[aircraft_index].failed_component_index = Some(component_index);
                    self.aircraft[aircraft_index].failed_component_minute = Some(self.minute);
                    self.aircraft[aircraft_index].in_flight_failure = true;
                    self.in_flight_failures += 1;
                    self.emit(
                        "aircraft_failed",
                        "failure.tree-root-propagation",
                        self.aircraft[aircraft_index].tail_number.clone(),
                        || json!({"component_id": component.component_id}),
                        Some(component.source_path),
                    );
                    self.return_aircraft(aircraft_index, true)?;
                    break;
                }
            }
        }
        Ok(())
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_generate_preventive(&mut self) -> Result<()> {
        self.count_scan("job", self.jobs.len());
        self.count_scan("aircraft", self.aircraft.len());
        let active: HashSet<_> = self
            .jobs
            .iter()
            .filter(|job| {
                job.kind == "preventive" && matches!(job.state.as_str(), "waiting" | "running")
            })
            .map(|job| job.aircraft_index)
            .collect();
        for aircraft_index in 0..self.aircraft.len() {
            if active.contains(&aircraft_index) {
                continue;
            }
            let mut due: Option<(usize, Vec<&str>)> = None;
            self.count_scan("preventive", self.plan.preventive_cycles.len());
            for (cycle_index, spec) in self.plan.preventive_cycles.iter().enumerate() {
                if spec.aircraft_index != aircraft_index {
                    continue;
                }
                let cycle = &self.preventive_cycles[cycle_index];
                let mut dimensions = vec![];
                if spec.calendar_days > 0
                    && self.minute >= cycle.last_preventive_minute + spec.calendar_days * 1440
                {
                    dimensions.push("calendar_days");
                }
                if spec.flight_hours > 0.0 && cycle.life_flight_hours >= spec.flight_hours {
                    dimensions.push("flight_hours");
                }
                if spec.landing_cycles > 0 && cycle.life_landing_cycles >= spec.landing_cycles {
                    dimensions.push("takeoff_landing_cycles");
                }
                if !dimensions.is_empty() {
                    due = Some((cycle_index, dimensions));
                    break;
                }
            }
            let Some((cycle_index, dimensions)) = due else {
                continue;
            };
            if self.aircraft[aircraft_index].state != "available" {
                continue;
            }
            if self.profile_enabled {
                self.profile.plan_spec_clones += 1;
            }
            let spec = self.plan.preventive_cycles[cycle_index].clone();
            self.aircraft[aircraft_index].state = "maintenance".into();
            self.preventive_maintenance_events += 1;
            self.create_job(
                aircraft_index,
                spec.activity_index,
                "preventive",
                None,
                None,
                Some(cycle_index),
            )?;
            let activity_id = self.plan.activities[spec.activity_index]
                .activity_id
                .clone();
            self.emit(
                "preventive_created",
                "maintenance.preventive-due",
                self.aircraft[aircraft_index].tail_number.clone(),
                || {
                    json!({"activity_id": activity_id,
                    "due_dimensions": dimensions})
                },
                Some(spec.source_path),
            );
        }
        Ok(())
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_create_preflight(&mut self) -> Result<()> {
        self.count_scan("mission", self.plan.missions.len());
        for mission_index in 0..self.plan.missions.len() {
            let preparation_start = self.plan.missions[mission_index].preparation_start;
            let required_aircraft = self.plan.missions[mission_index].required_aircraft;
            if !matches!(
                self.missions[mission_index].status.as_str(),
                "scheduled" | "delayed"
            ) || self.minute < preparation_start
            {
                continue;
            }
            let commissioned = self.commissioned_count(mission_index);
            if commissioned >= required_aircraft {
                self.missions[mission_index].preflight_created = true;
                continue;
            }
            let active = self.active_preflight_aircraft(mission_index);
            let available: Vec<_> = {
                let required_aircraft_type =
                    &self.plan.missions[mission_index].required_aircraft_type;
                (0..self.aircraft.len())
                    .filter(|index| {
                        self.aircraft[*index].state == "available"
                            && !self.aircraft[*index].postflight_due
                            && self.matches_type(*index, required_aircraft_type)
                            && self.aircraft[*index].prepared_mission_indexes.is_empty()
                            && !active.contains(index)
                    })
                    .collect()
            };
            let mut created = 0;
            for aircraft_index in available
                .into_iter()
                .take(required_aircraft.saturating_sub(commissioned))
            {
                self.aircraft[aircraft_index].state = "pre_support".into();
                self.aircraft[aircraft_index].current_mission_index = Some(mission_index);
                let activity_index = self.preparation_activity(mission_index, aircraft_index)?;
                self.create_job(
                    aircraft_index,
                    activity_index,
                    "preflight",
                    Some(mission_index),
                    None,
                    None,
                )?;
                created += 1;
            }
            self.missions[mission_index].preflight_created =
                self.commissioned_count(mission_index) >= required_aircraft;
            if created > 0 {
                self.emit(
                    "preflight_created",
                    "mission.commission-preflight",
                    self.plan.missions[mission_index].mission_id.clone(),
                    || json!({"created": created}),
                    None,
                );
            }
        }
        Ok(())
    }

    fn step_requirements(
        &self,
        job_index: usize,
        static_spares: Arc<[(String, i64)]>,
        step_count: usize,
    ) -> StepRequirements {
        if self.jobs[job_index].maintenance_method.as_deref() == Some("non_replacement")
            && matches!(self.jobs[job_index].kind.as_str(), "repair" | "preventive")
        {
            return StepRequirements::Empty;
        }
        if self.jobs[job_index].step_index + 1 == step_count
            && !self.jobs[job_index].injected_spares.is_empty()
        {
            let mut requirements: BTreeMap<_, _> = static_spares.iter().cloned().collect();
            for (product_id, quantity) in &self.jobs[job_index].injected_spares {
                *requirements.entry(product_id.clone()).or_default() += quantity;
            }
            return StepRequirements::Dynamic(requirements.into_iter().collect());
        }
        StepRequirements::Static(static_spares)
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_start_waiting_jobs(&mut self) -> Result<()> {
        self.count_scan("job", self.jobs.len());
        self.debug_assert_active_job_indexes();
        let mut waiting: Vec<_> = self.waiting_job_indexes.iter().copied().collect();
        if self.profile_enabled {
            self.profile.resource_dispatch_candidate_visits += waiting.len() as u64;
        }
        waiting.sort_by_key(|index| {
            (
                self.prepared.activities[self.jobs[*index].activity_index].priority,
                self.jobs[*index].started_time.unwrap_or(self.minute),
                self.jobs[*index].job_id.clone(),
            )
        });
        for job_index in waiting {
            let activity_index = self.jobs[job_index].activity_index;
            let step_index = self.jobs[job_index].step_index;
            let prepared_activity = &self.prepared.activities[activity_index];
            let step_count = prepared_activity.steps.len();
            if step_index >= step_count {
                self.transition_job_state(job_index, "completed");
                self.complete_job(job_index)?;
                continue;
            }
            let step = &prepared_activity.steps[step_index];
            let node_index = prepared_activity.resource_node_index;
            let step_spec_index = step.index;
            let step_code = step.code.clone();
            let duration_minutes = step.duration_minutes;
            let personnel = step.personnel;
            let equipment = step.equipment;
            let static_spares = step.static_spares.clone();
            let cached_block = self
                .dispatch_cache
                .get(job_index)
                .and_then(Option::as_ref)
                .filter(|cached| {
                    cached.activity_index == activity_index && cached.step_index == step_index
                })
                .cloned();
            if let Some(cached) = cached_block {
                if self.profile_enabled {
                    self.profile.resource_dispatch_cache_hits += 1;
                }
                match cached.reason {
                    DispatchBlockReason::Shortage => {}
                    DispatchBlockReason::Personnel => self.emit(
                        "personnel_delay",
                        "resource.personnel-capacity",
                        self.jobs[job_index].job_id.clone(),
                        || json!({"step_index": step_spec_index}),
                        None,
                    ),
                    DispatchBlockReason::Equipment => self.emit(
                        "equipment_shortage",
                        "resource.equipment-capacity",
                        self.jobs[job_index].job_id.clone(),
                        || json!({"step_index": step_spec_index}),
                        None,
                    ),
                }
                continue;
            }
            if self.profile_enabled {
                self.profile.resource_dispatch_guard_evaluations += 1;
            }
            let requirements = self.step_requirements(job_index, static_spares, step_count);
            self.dispatch_remote_spares(job_index, activity_index, requirements.as_slice());
            self.count_map_reads(requirements.len() * 2);
            let immediately_available = requirements.iter().all(|(product_id, quantity)| {
                self.resources[node_index]
                    .inventory
                    .get(product_id)
                    .copied()
                    .unwrap_or(0)
                    + self.jobs[job_index]
                        .spare_reservations
                        .get(product_id)
                        .copied()
                        .unwrap_or(0)
                    >= *quantity
            });
            if !requirements.is_empty()
                && !self.jobs[job_index]
                    .requested_spare_steps
                    .contains(&self.jobs[job_index].step_index)
            {
                let step_index = self.jobs[job_index].step_index;
                self.jobs[job_index]
                    .requested_spare_steps
                    .insert(step_index);
                for (product_id, quantity) in requirements.iter() {
                    self.spare_demand_total += quantity;
                    if immediately_available {
                        self.spare_immediately_filled_total += quantity;
                    }
                    let step_index = self.jobs[job_index].step_index;
                    self.emit("spare_request", "inventory.request-once", self.jobs[job_index].job_id.clone(),
                        || json!({"step_index": step_index, "product_id": product_id,
                            "demand_quantity": quantity,
                            "immediately_filled_quantity": if immediately_available { *quantity } else { 0 },
                            "node_index": node_index}), None);
                }
            }
            let shortages: Vec<_> = requirements
                .iter()
                .filter_map(|(product_id, quantity)| {
                    let available = self.resources[node_index]
                        .inventory
                        .get(product_id)
                        .copied()
                        .unwrap_or(0)
                        + self.jobs[job_index]
                            .spare_reservations
                            .get(product_id)
                            .copied()
                            .unwrap_or(0);
                    (available < *quantity).then(|| (product_id.clone(), *quantity, available))
                })
                .collect();
            self.count_map_reads(requirements.len() * 2);
            if !shortages.is_empty() {
                if self.jobs[job_index].shortage_signature.as_ref() != Some(&shortages) {
                    self.jobs[job_index].shortage_signature = Some(shortages.clone());
                    for (product_id, quantity, available) in shortages {
                        self.shortage_events += 1;
                        let step_index = self.jobs[job_index].step_index;
                        self.emit(
                            "spare_shortage",
                            "inventory.local-shortage",
                            self.jobs[job_index].job_id.clone(),
                            || {
                                json!({"step_index": step_index, "product_id": product_id,
                                "required_quantity": quantity, "available_quantity": available,
                                "node_index": node_index})
                            },
                            None,
                        );
                    }
                }
                self.cache_dispatch_block(
                    job_index,
                    activity_index,
                    step_index,
                    DispatchBlockReason::Shortage,
                );
                continue;
            }
            self.jobs[job_index].shortage_signature = None;
            if self.resources[node_index].personnel_in_use + personnel
                > self.resources[node_index].personnel_capacity
            {
                self.cache_dispatch_block(
                    job_index,
                    activity_index,
                    step_index,
                    DispatchBlockReason::Personnel,
                );
                self.emit(
                    "personnel_delay",
                    "resource.personnel-capacity",
                    self.jobs[job_index].job_id.clone(),
                    || json!({"step_index": step_spec_index}),
                    None,
                );
                continue;
            }
            if self.resources[node_index].equipment_in_use + equipment
                > self.resources[node_index].equipment_capacity
            {
                self.cache_dispatch_block(
                    job_index,
                    activity_index,
                    step_index,
                    DispatchBlockReason::Equipment,
                );
                self.emit(
                    "equipment_shortage",
                    "resource.equipment-capacity",
                    self.jobs[job_index].job_id.clone(),
                    || json!({"step_index": step_spec_index}),
                    None,
                );
                continue;
            }
            self.resources[node_index].personnel_in_use += personnel;
            self.resources[node_index].equipment_in_use += equipment;
            if personnel != 0 {
                self.invalidate_dispatch_resource("personnel_capacity", node_index, None);
            }
            if equipment != 0 {
                self.invalidate_dispatch_resource("equipment_capacity", node_index, None);
            }
            if !requirements.is_empty()
                && !self.jobs[job_index]
                    .consumed_spare_steps
                    .contains(&self.jobs[job_index].step_index)
            {
                let step_index = self.jobs[job_index].step_index;
                self.jobs[job_index].consumed_spare_steps.insert(step_index);
                for (product_id, quantity) in requirements.iter() {
                    self.count_map_reads(1);
                    let reserved = self.jobs[job_index]
                        .spare_reservations
                        .get(product_id)
                        .copied()
                        .unwrap_or(0)
                        .min(*quantity);
                    if reserved > 0 {
                        let remaining =
                            self.jobs[job_index].spare_reservations[product_id] - reserved;
                        if remaining > 0 {
                            self.jobs[job_index]
                                .spare_reservations
                                .insert(product_id.clone(), remaining);
                        } else {
                            self.jobs[job_index].spare_reservations.remove(product_id);
                        }
                        self.count_map_writes(1);
                    }
                    let shared = quantity - reserved;
                    if shared > 0 {
                        *self.resources[node_index]
                            .inventory
                            .entry(product_id.clone())
                            .or_default() -= shared;
                        self.count_map_writes(1);
                        self.invalidate_dispatch_resource(
                            "inventory",
                            node_index,
                            Some(product_id),
                        );
                    }
                    self.spare_consumed_total += quantity;
                    let step_index = self.jobs[job_index].step_index;
                    let maintenance_method = self.jobs[job_index].maintenance_method.clone();
                    self.emit(
                        "spare_consumed",
                        "inventory.consume-at-job-start",
                        self.jobs[job_index].job_id.clone(),
                        || {
                            json!({"step_index": step_index, "product_id": product_id,
                            "quantity": quantity, "node_index": node_index,
                            "maintenance_method": maintenance_method})
                        },
                        None,
                    );
                }
            }
            self.jobs[job_index].reserved_personnel = personnel;
            self.jobs[job_index].reserved_equipment = equipment;
            self.transition_job_state(job_index, "running");
            if self.jobs[job_index].started_time.is_none() {
                self.jobs[job_index].started_time = Some(self.minute);
            }
            self.jobs[job_index].remaining = duration_minutes;
            if self.jobs[job_index].kind == "repair"
                && self.jobs[job_index].component_index.is_some()
                && self.jobs[job_index].step_index + 1 == step_count
            {
                let duration = self.plan.components[self.jobs[job_index].component_index.unwrap()]
                    .repair_duration_minutes;
                if duration > 0 {
                    self.jobs[job_index].remaining = duration;
                }
            }
            let personnel_in_use = self.resources[node_index].personnel_in_use;
            let equipment_in_use = self.resources[node_index].equipment_in_use;
            self.emit("resources_reserved", "resource.reserve-atomic", self.jobs[job_index].job_id.clone(),
                || json!({"node_index": node_index, "step_index": step_spec_index, "personnel": personnel,
                    "equipment": equipment, "personnel_in_use": personnel_in_use,
                    "equipment_in_use": equipment_in_use}), None);
            self.emit(
                "operations_step_started",
                "work.stable-topological-serial",
                self.jobs[job_index].job_id.clone(),
                || json!({"step_index": step_spec_index, "activity_code": step_code}),
                None,
            );
        }
        Ok(())
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_dispatch_missions(&mut self) -> Result<()> {
        self.count_scan("mission", self.plan.missions.len());
        for mission_index in 0..self.plan.missions.len() {
            let planned_start = self.plan.missions[mission_index].planned_start;
            let required_aircraft = self.plan.missions[mission_index].required_aircraft;
            let duration_minutes = self.plan.missions[mission_index].duration_minutes;
            let cancel_minutes = self.plan.missions[mission_index].cancel_minutes;
            if !matches!(
                self.missions[mission_index].status.as_str(),
                "scheduled" | "delayed"
            ) || self.minute < planned_start
            {
                continue;
            }
            let candidates: Vec<_> = {
                let required_aircraft_type =
                    &self.plan.missions[mission_index].required_aircraft_type;
                (0..self.aircraft.len())
                    .filter(|index| {
                        self.ready_for_mission(*index, mission_index)
                            && self.matches_type(*index, required_aircraft_type)
                    })
                    .collect()
            };
            self.count_scan("aircraft", self.aircraft.len());
            if candidates.len() >= required_aircraft {
                let assigned = candidates[..required_aircraft].to_vec();
                let operations_plan_group_id = self.plan.missions[mission_index]
                    .operations_plan_group_id
                    .clone();
                for aircraft_index in &assigned {
                    let aircraft = &mut self.aircraft[*aircraft_index];
                    aircraft.state = "flying".into();
                    aircraft.current_mission_index = Some(mission_index);
                    aircraft.prepared_mission_indexes.remove(&mission_index);
                    aircraft.return_time = Some(self.minute + duration_minutes);
                    let day = self.minute / 1440;
                    if aircraft.operations_day != Some(day) {
                        aircraft.operations_day = Some(day);
                        aircraft.daily_takeoffs = 0;
                    }
                    aircraft.daily_takeoffs += 1;
                    aircraft.takeoff_count += 1;
                    aircraft.operations_plan_group_id = operations_plan_group_id.clone();
                    aircraft.last_operations_mission_index = Some(mission_index);
                    aircraft.prepared_operations_day = None;
                }
                let state = &mut self.missions[mission_index];
                state.status = "launched".into();
                state.actual_start = Some(self.minute);
                state.return_time = Some(self.minute + duration_minutes);
                state.assigned_aircraft = assigned.clone();
                state.delay_minutes = (self.minute - planned_start).max(0);
                self.launched_sorties += assigned.len() as i64;
                self.total_departure_delay += state.delay_minutes;
                if state.delay_minutes != 0 && self.delayed_missions.insert(mission_index) {
                    self.delayed_sorties += assigned.len() as i64;
                }
                let assigned_tail_numbers = assigned
                    .iter()
                    .map(|index| self.aircraft[*index].tail_number.clone())
                    .collect::<Vec<_>>();
                self.emit(
                    "mission_launched",
                    "mission.dispatch-ready-aircraft",
                    self.plan.missions[mission_index].mission_id.clone(),
                    || json!({"aircraft": assigned_tail_numbers}),
                    None,
                );
            } else if self.minute - planned_start >= cancel_minutes {
                self.missions[mission_index].status = "cancelled".into();
                self.cancelled_sorties += required_aircraft as i64;
                self.total_departure_delay += cancel_minutes;
                self.cancel_mission_preflight(mission_index)?;
                self.emit(
                    "mission_cancelled",
                    "mission.cancel-insufficient-ready-aircraft",
                    self.plan.missions[mission_index].mission_id.clone(),
                    || json!({}),
                    None,
                );
            } else {
                self.missions[mission_index].status = "delayed".into();
                if self.delayed_missions.insert(mission_index) {
                    self.delayed_sorties += required_aircraft as i64;
                }
            }
        }
        Ok(())
    }

    fn cancel_mission_preflight(&mut self, mission_index: usize) -> Result<()> {
        let targets: Vec<_> = (0..self.jobs.len())
            .filter(|index| {
                self.jobs[*index].kind == "preflight"
                    && self.jobs[*index].mission_index == Some(mission_index)
                    && matches!(self.jobs[*index].state.as_str(), "waiting" | "running")
            })
            .collect();
        for job_index in targets {
            if self.jobs[job_index].state == "running" {
                let activity_index = self.jobs[job_index].activity_index;
                let step_position = self.jobs[job_index].step_index;
                let activity = &self.prepared.activities[activity_index];
                self.release_resources(
                    job_index,
                    activity.resource_node_index,
                    activity.steps[step_position].index,
                )?;
            }
            self.transition_job_state(job_index, "cancelled");
            self.jobs[job_index].remaining = 0;
        }
        for aircraft in &mut self.aircraft {
            if aircraft.current_mission_index == Some(mission_index)
                && matches!(aircraft.state.as_str(), "pre_support" | "mission_ready")
            {
                aircraft.state = "available".into();
                aircraft.current_mission_index = None;
                aircraft.prepared_operations_day = None;
            }
            aircraft.prepared_mission_indexes.remove(&mission_index);
        }
        Ok(())
    }

    fn has_remaining_operations_mission(&self, aircraft_index: usize) -> bool {
        let aircraft = &self.aircraft[aircraft_index];
        for (mission_index, mission) in self.plan.missions.iter().enumerate() {
            if !matches!(
                self.missions[mission_index].status.as_str(),
                "scheduled" | "delayed"
            ) {
                continue;
            }
            if self.minute.max(mission.planned_start) / 1440
                != aircraft.operations_day.unwrap_or(-1)
            {
                continue;
            }
            if self.minute > mission.planned_start + mission.cancel_minutes
                || !self.matches_type(aircraft_index, &mission.required_aircraft_type)
            {
                continue;
            }
            if aircraft.current_mission_index == Some(mission_index)
                || self.commissioned_count(mission_index) < mission.required_aircraft
            {
                return true;
            }
        }
        false
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_coordinate_postflight(&mut self, cutoff: bool) -> Result<()> {
        self.count_scan("aircraft", self.aircraft.len());
        let day = self.minute / 1440;
        for aircraft_index in 0..self.aircraft.len() {
            let operations_day = self.aircraft[aircraft_index].operations_day;
            if operations_day.is_none() || self.aircraft[aircraft_index].daily_takeoffs == 0 {
                continue;
            }
            if (day > operations_day.unwrap() || cutoff)
                && (self.aircraft[aircraft_index].postflight_required
                    || self.aircraft[aircraft_index].state == "flying")
            {
                self.aircraft[aircraft_index].postflight_due = true;
            }
            if !self.aircraft[aircraft_index].postflight_required {
                continue;
            }
            if !self.has_remaining_operations_mission(aircraft_index) {
                self.aircraft[aircraft_index].postflight_due = true;
            }
            if !self.aircraft[aircraft_index].postflight_due
                || matches!(
                    self.aircraft[aircraft_index].state.as_str(),
                    "flying" | "maintenance" | "preventive" | "post_support"
                )
            {
                continue;
            }
            self.aircraft[aircraft_index].state = "post_support".into();
            let group = self.aircraft[aircraft_index]
                .operations_plan_group_id
                .clone();
            let activity_index = self.activity_for(&group, "postflight", aircraft_index)?;
            let mission_index = self.aircraft[aircraft_index].last_operations_mission_index;
            self.create_job(
                aircraft_index,
                activity_index,
                "postflight",
                mission_index,
                None,
                None,
            )?;
        }
        Ok(())
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn phase_mission_success(&mut self) {
        self.count_scan("mission", self.plan.missions.len());
        for mission_index in 0..self.plan.missions.len() {
            let mission = &self.plan.missions[mission_index];
            let start = self.missions[mission_index]
                .actual_start
                .unwrap_or(mission.planned_start);
            let success_minute =
                start + (mission.duration_minutes as f64 * mission.success_point).ceil() as i64;
            let min_required_aircraft = mission.min_required_aircraft;
            if self.missions[mission_index].success_evaluated || success_minute > self.minute {
                continue;
            }
            let count = self.missions[mission_index]
                .assigned_aircraft
                .iter()
                .collect::<HashSet<_>>()
                .difference(
                    &self.missions[mission_index]
                        .failed_aircraft
                        .iter()
                        .collect(),
                )
                .count();
            let succeeded = count >= min_required_aircraft;
            self.missions[mission_index].success_member_count = count;
            self.missions[mission_index].success_at_minute = Some(self.minute);
            self.missions[mission_index].success_evaluated = true;
            self.missions[mission_index].succeeded = succeeded;
            self.emit(
                if succeeded {
                    "mission_success_point_succeeded"
                } else {
                    "mission_success_point_failed"
                },
                "mission.evaluate-success-point",
                self.plan.missions[mission_index].mission_id.clone(),
                || json!({"members": count}),
                None,
            );
        }
    }

    fn execute_minute(&mut self) -> Result<()> {
        for phase_index in 0..self.execution_phases.len() {
            let phase = self.execution_phases[phase_index];
            let Some(phase_name) = phase.name() else {
                let ExecutionPhase::Unsupported(source_index) = phase else {
                    unreachable!("known execution phase must have a name")
                };
                let unsupported = self.plan.phases[source_index].clone();
                self.phase.clone_from(&unsupported);
                bail!("unsupported phase {:?}", unsupported);
            };
            self.phase.clear();
            self.phase.push_str(phase_name);
            let started = self.profile_enabled.then(Instant::now);
            match phase {
                ExecutionPhase::TransportArrivals => self.phase_transport_arrivals(),
                ExecutionPhase::MissionReturns => self.phase_mission_returns()?,
                ExecutionPhase::JobProgressAndCompletions => self.phase_job_progress()?,
                ExecutionPhase::Failures => self.phase_failures()?,
                ExecutionPhase::OperationsPostflightBeforePreparation => {
                    self.phase_coordinate_postflight(false)?
                }
                ExecutionPhase::PreventiveGeneration => self.phase_generate_preventive()?,
                ExecutionPhase::PreflightGeneration => self.phase_create_preflight()?,
                ExecutionPhase::ResourceDispatch => self.phase_start_waiting_jobs()?,
                ExecutionPhase::MissionDispatch => self.phase_dispatch_missions()?,
                ExecutionPhase::OperationsPostflightAfterDispatch => {
                    self.phase_coordinate_postflight(false)?
                }
                ExecutionPhase::MissionSuccess => self.phase_mission_success(),
                ExecutionPhase::DailyReadiness
                | ExecutionPhase::OperationalAvailability
                | ExecutionPhase::Downtime => {}
                ExecutionPhase::Stop => {
                    if self.minute >= self.plan.duration_minutes {
                        self.phase_coordinate_postflight(true)?;
                        self.stop_reason = "duration".into();
                        self.running = false;
                        self.emit(
                            "simulation_stopped",
                            "stop.duration",
                            "simulation".into(),
                            || json!({}),
                            None,
                        );
                    }
                }
                ExecutionPhase::Unsupported(_) => {
                    unreachable!("unsupported execution phase handled before dispatch")
                }
            };
            if let Some(started) = started {
                self.profile.add_phase(phase_name, elapsed_ns(started));
            }
        }
        Ok(())
    }

    pub fn run(self, until: Option<i64>) -> Result<RunResult> {
        self.run_internal(until).map(|(result, _)| result)
    }

    pub fn run_profiled(mut self, until: Option<i64>) -> Result<(RunResult, RuntimeProfile)> {
        self.profile_enabled = true;
        self.run_internal(until)
    }

    fn run_internal(mut self, until: Option<i64>) -> Result<(RunResult, RuntimeProfile)> {
        let horizon = until
            .unwrap_or(self.plan.duration_minutes)
            .min(self.plan.duration_minutes);
        let execution_started = Instant::now();
        while self.running && self.minute < horizon {
            self.minute += 1;
            if self.profile_enabled {
                self.profile.minute_iterations += 1;
            }
            self.execute_minute()?;
        }
        if self.profile_enabled {
            self.profile.execution_ns = elapsed_ns(execution_started);
        }
        if horizon < self.plan.duration_minutes && self.running {
            self.stop_reason = "requested_until".into();
        }
        let metrics_started = Instant::now();
        let metrics = self.metrics();
        if self.profile_enabled {
            self.profile.metrics_build_ns = elapsed_ns(metrics_started);
        }
        let terminal_state_started = Instant::now();
        let terminal_state = self.terminal_state();
        if self.profile_enabled {
            self.profile.terminal_state_build_ns = elapsed_ns(terminal_state_started);
        }
        let result = RunResult {
            plan_fingerprint: self.fingerprint,
            seed: self.seed,
            time: self.minute,
            stop_reason: self.stop_reason,
            sample_requests: self.sample_requests,
            trace: self.trace,
            metrics,
            terminal_state,
        };
        Ok((result, self.profile))
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn metrics(&self) -> Value {
        let executable: Vec<_> = self
            .plan
            .missions
            .iter()
            .enumerate()
            .filter(|(_, mission)| mission.planned_start <= self.minute)
            .map(|(index, _)| index)
            .collect();
        let planned_sorties: usize = executable
            .iter()
            .map(|index| self.plan.missions[*index].required_aircraft)
            .sum();
        let successful = executable
            .iter()
            .filter(|index| self.missions[**index].succeeded)
            .count();
        let postflight_count = self
            .aircraft
            .iter()
            .filter(|item| item.postflight_required)
            .count();
        let failed_count = self
            .aircraft
            .iter()
            .filter(|item| {
                item.component_failure_minutes_by_slot
                    .iter()
                    .any(Option::is_some)
            })
            .count();
        let repairing_count = (0..self.aircraft.len())
            .filter(|aircraft_index| {
                self.jobs.iter().any(|job| {
                    job.aircraft_index == *aircraft_index
                        && job.kind == "repair"
                        && matches!(job.state.as_str(), "waiting" | "running")
                })
            })
            .count();
        let spare_stock_total: i64 = self
            .resources
            .iter()
            .flat_map(|item| item.inventory.values())
            .sum();
        json!({
            "planned_sorties": planned_sorties, "planned_mission_waves": executable.len(),
            "successful_mission_waves": successful,
            "mission_success_rate": successful as f64 / executable.len().max(1) as f64,
            "launched_sorties": self.launched_sorties, "completed_sorties": self.completed_sorties,
            "cancelled_sorties": self.cancelled_sorties, "delayed_sorties": self.delayed_sorties,
            "postflight_count": postflight_count,
            "avg_departure_delay": self.total_departure_delay as f64 / (self.launched_sorties + self.cancelled_sorties).max(1) as f64,
            "elapsed_minutes": self.minute, "stop_reason": self.stop_reason,
            "lru_failures": self.lru_failures, "in_flight_failures": self.in_flight_failures,
            "failed_sorties": self.failed_sorties, "preventive_maintenance_events": self.preventive_maintenance_events,
            "failed_count": failed_count, "repairing_count": repairing_count,
            "spare_stock_total": spare_stock_total, "spare_demand_total": self.spare_demand_total,
            "spare_immediately_filled_total": self.spare_immediately_filled_total,
            "spare_fill_rate": self.spare_immediately_filled_total as f64 / self.spare_demand_total.max(1) as f64,
            "spare_consumed_total": self.spare_consumed_total, "shortage_events": self.shortage_events,
            "transport_in_transit_count": self.shipments.len(),
            "transport_replenishment_events": self.transport_replenishment_events,
            "total_transport_delay_minutes": self.total_transport_delay,
            "mean_transport_delay": self.total_transport_delay as f64 / (60 * self.transport_replenishment_events.max(1)) as f64,
        })
    }

    #[cfg_attr(feature = "profiling", inline(never))]
    fn terminal_state(&self) -> Value {
        let aircraft: Vec<_> = self.aircraft.iter().enumerate().map(|(aircraft_index, item)| {
            let failures: BTreeMap<_, _> = self.failure_components_by_aircraft[aircraft_index]
                .iter()
                .zip(item.component_failure_minutes_by_slot.iter())
                .filter_map(|(component_index, minute)| minute.map(|minute| {
                    (self.plan.components[*component_index].component_id.clone(), minute)
                }))
                .collect();
            json!({
                "tail_number": item.tail_number, "state": item.state,
                "current_mission_id": self.mission_id(item.current_mission_index),
                "prepared_mission_ids": item.prepared_mission_indexes.iter()
                    .map(|index| self.plan.missions[*index].mission_id.clone()).collect::<Vec<_>>(),
                "operations_day": item.operations_day, "daily_takeoffs": item.daily_takeoffs,
                "postflight_required": item.postflight_required, "postflight_due": item.postflight_due,
                "flight_hours": item.flight_hours, "takeoff_count": item.takeoff_count,
                "landing_count": item.landing_count,
                "failed_component_id": item.failed_component_index.map(|index| self.plan.components[index].component_id.clone()),
                "component_failure_minutes": failures, "in_flight_failure": item.in_flight_failure,
            })
        }).collect();
        let missions: Vec<_> = self
            .missions
            .iter()
            .enumerate()
            .map(|(index, item)| {
                json!({
                    "mission_id": self.plan.missions[index].mission_id, "status": item.status,
                    "actual_start": item.actual_start,
                    "assigned_tail_numbers": item.assigned_aircraft.iter().map(|aircraft_index|
                        self.aircraft[*aircraft_index].tail_number.clone()).collect::<Vec<_>>(),
                    "success_evaluated": item.success_evaluated, "succeeded": item.succeeded,
                })
            })
            .collect();
        let jobs: Vec<_> = self.jobs.iter().map(|item| json!({
            "job_id": item.job_id, "kind": item.kind,
            "aircraft": self.aircraft[item.aircraft_index].tail_number,
            "mission_id": self.mission_id(item.mission_index),
            "activity_id": self.plan.activities[item.activity_index].activity_id,
            "state": item.state, "step_index": item.step_index,
            "started_time": item.started_time, "completed_time": item.completed_time,
            "component_id": item.component_index.map(|index| self.plan.components[index].component_id.clone()),
            "maintenance_method": item.maintenance_method,
        })).collect();
        let resources: Vec<_> = self.resources.iter().enumerate().map(|(index, item)| json!({
            "node_id": self.plan.resource_nodes[index].node_id,
            "personnel_in_use": item.personnel_in_use, "equipment_in_use": item.equipment_in_use,
            "inventory": item.inventory,
        })).collect();
        json!({"aircraft": aircraft, "missions": missions, "jobs": jobs, "resources": resources})
    }
}

fn tokens(value: &str) -> HashSet<String> {
    let text = value.trim().to_lowercase();
    if text.is_empty() {
        return HashSet::new();
    }
    [
        text.clone(),
        text.chars().filter(|item| item.is_alphanumeric()).collect(),
    ]
    .into_iter()
    .collect()
}

fn hex_prefix(bytes: &[u8], count: usize) -> String {
    bytes
        .iter()
        .take(count)
        .map(|item| format!("{item:02x}"))
        .collect()
}

#[cfg(test)]
mod phase_tests {
    use super::*;

    fn synthetic_plan() -> ExecutionPlan {
        let bytes = include_bytes!("../../../tests/fixtures/synthetic/b1-execution-plan.json");
        ExecutionPlan::from_slice(bytes).unwrap().0
    }

    fn failure_plan() -> ExecutionPlan {
        let bytes = include_bytes!(
            "../../../tests/fixtures/synthetic/b2-failure-repair-execution-plan.json"
        );
        ExecutionPlan::from_slice(bytes).unwrap().0
    }

    #[test]
    fn unknown_phase_still_fails_when_executed() {
        let mut plan = synthetic_plan();
        plan.phases = vec!["unknown_phase".into()];
        let error = Runtime::new(plan, "test-fingerprint".into(), 0)
            .unwrap()
            .run(Some(1))
            .unwrap_err();

        assert_eq!(error.to_string(), "unsupported phase \"unknown_phase\"");
    }

    #[test]
    fn duplicate_phase_names_are_not_deduplicated() {
        let mut plan = synthetic_plan();
        plan.phases = vec!["daily_readiness".into(), "daily_readiness".into()];
        let runtime = Runtime::from_shared_profiled(
            Arc::new(plan),
            "test-fingerprint".into(),
            0,
            ObservationLevel::Summary,
        )
        .unwrap();
        let (_, profile) = runtime.run_profiled(Some(1)).unwrap();

        assert_eq!(profile.phases["daily_readiness"].calls, 2);
    }

    #[test]
    fn sparse_failure_slots_preserve_draw_before_applicability_order() {
        let mut plan = failure_plan();
        plan.components[1].quantity = 2;
        let mut second_aircraft = plan.aircraft[0].clone();
        second_aircraft.index = 1;
        second_aircraft.tail_number = "F35-02".into();
        plan.aircraft.push(second_aircraft);
        plan.components[1].aircraft_indexes.push(1);
        let mut first_aircraft_only = plan.components[1].clone();
        first_aircraft_only.index = 2;
        first_aircraft_only.component_id = "first-aircraft-only".into();
        first_aircraft_only.aircraft_indexes = vec![0];
        plan.components.push(first_aircraft_only);

        let mut runtime = Runtime::new(plan, "test-fingerprint".into(), 0).unwrap();

        assert_eq!(
            runtime.failure_components_by_aircraft,
            vec![vec![1, 2], vec![1]]
        );
        assert_eq!(runtime.aircraft[0].failure_remaining_by_slot.len(), 2);
        assert!(runtime.aircraft[0].failure_remaining_by_slot[0].is_some());
        assert_eq!(runtime.aircraft[1].failure_remaining_by_slot.len(), 1);
        let second_aircraft_shared_timer = runtime.aircraft[1].failure_remaining_by_slot[0];
        runtime.aircraft[0].failure_remaining_by_slot[0] = Some(-1.0);
        assert_eq!(
            runtime.aircraft[1].failure_remaining_by_slot[0],
            second_aircraft_shared_timer
        );
        let requests: Vec<_> = runtime
            .sample_requests
            .iter()
            .map(|request| {
                (
                    request["entity"].as_str().unwrap(),
                    request["component_id"].as_str().unwrap(),
                    request["quantity_index"].as_u64().unwrap(),
                    request["reason"].as_str().unwrap(),
                )
            })
            .collect();
        assert_eq!(
            requests,
            vec![
                ("F35-01", "radar-lru", 0, "initialize"),
                ("F35-01", "radar-lru", 1, "initialize"),
                ("F35-01", "first-aircraft-only", 0, "initialize"),
                ("F35-01", "first-aircraft-only", 1, "initialize"),
                ("F35-02", "radar-lru", 0, "initialize"),
                ("F35-02", "radar-lru", 1, "initialize"),
                ("F35-02", "first-aircraft-only", 0, "initialize"),
                ("F35-02", "first-aircraft-only", 1, "initialize"),
            ]
        );
    }

    #[test]
    fn failure_countdown_uses_slots_and_preserves_terminal_business_keys() {
        let mut runtime = Runtime::from_shared_profiled(
            Arc::new(failure_plan()),
            "test-fingerprint".into(),
            0,
            ObservationLevel::Full,
        )
        .unwrap();
        runtime.minute = 5;
        runtime.phase = "failures".into();
        runtime.aircraft[0].state = "flying".into();
        runtime.aircraft[0].failure_remaining_by_slot[0] = Some(0.5);

        runtime.phase_failures().unwrap();

        assert_eq!(
            runtime.aircraft[0].component_failure_minutes_by_slot,
            vec![Some(5)]
        );
        assert_eq!(runtime.aircraft[0].failed_component_index, Some(1));
        assert_eq!(runtime.profile.indexed_map_reads, 0);
        assert_eq!(runtime.profile.indexed_map_writes, 0);
        assert_eq!(
            runtime.terminal_state()["aircraft"][0]["component_failure_minutes"]["radar-lru"],
            5
        );
    }

    #[test]
    fn missing_failure_timer_resamples_before_countdown() {
        let mut plan = failure_plan();
        plan.components[1].failure_rate_per_hour = 1e-12;
        let mut runtime = Runtime::new(plan, "test-fingerprint".into(), 0).unwrap();
        runtime.minute = 5;
        runtime.phase = "failures".into();
        runtime.aircraft[0].state = "flying".into();
        runtime.aircraft[0].failure_remaining_by_slot[0] = None;
        let initial_request_count = runtime.sample_requests.len();

        runtime.phase_failures().unwrap();

        assert_eq!(runtime.sample_requests.len(), initial_request_count + 1);
        let request = runtime.sample_requests.last().unwrap();
        assert_eq!(request["reason"], "missing_timer");
        let sampled = request["value_minutes"].as_f64().unwrap();
        assert_eq!(
            runtime.aircraft[0].failure_remaining_by_slot[0],
            Some(sampled - 1.0)
        );
        assert_eq!(
            runtime.aircraft[0].component_failure_minutes_by_slot,
            vec![None]
        );
    }

    #[test]
    fn active_job_indexes_ignore_history_and_preserve_phase_order() {
        let mut plan = synthetic_plan();
        plan.resource_nodes[0].personnel_capacity = 10;
        plan.resource_nodes[0].equipment_capacity = 10;
        let mut urgent_activity = plan.activities[0].clone();
        urgent_activity.index = plan.activities.len();
        urgent_activity.activity_id = "urgent-preflight".into();
        urgent_activity.priority = 0;
        plan.activities.push(urgent_activity);
        let urgent_activity_index = plan.activities.len() - 1;
        let mut runtime = Runtime::from_shared_profiled(
            Arc::new(plan),
            "test-fingerprint".into(),
            0,
            ObservationLevel::Full,
        )
        .unwrap();
        runtime.minute = 10;
        runtime.phase = "resource_dispatch".into();

        for _ in 0..16 {
            runtime
                .create_job(0, 1, "historical", None, None, None)
                .unwrap();
        }
        assert!(runtime.waiting_job_indexes.is_empty());
        assert!(runtime.running_job_indexes.is_empty());

        let first_waiting = runtime.jobs.len();
        runtime.create_job(0, 0, "test", None, None, None).unwrap();
        runtime.jobs[first_waiting].job_id = "zz-tied-job".into();
        let previously_started = runtime.jobs.len();
        runtime.create_job(0, 0, "test", None, None, None).unwrap();
        runtime.jobs[previously_started].started_time = Some(5);
        let urgent_waiting = runtime.jobs.len();
        runtime
            .create_job(0, urgent_activity_index, "test", None, None, None)
            .unwrap();
        let tied_waiting = runtime.jobs.len();
        runtime.create_job(0, 0, "test", None, None, None).unwrap();
        runtime.jobs[tied_waiting].job_id = "aa-tied-job".into();
        let active_job_ids = [
            first_waiting,
            previously_started,
            urgent_waiting,
            tied_waiting,
        ]
        .map(|index| runtime.jobs[index].job_id.clone());

        runtime.phase_start_waiting_jobs().unwrap();

        let started: Vec<_> = runtime
            .trace
            .iter()
            .filter(|item| item["kind"] == "operations_step_started")
            .map(|item| item["entity"].as_str().unwrap())
            .collect();
        assert_eq!(
            started,
            vec![
                active_job_ids[2].as_str(),
                active_job_ids[1].as_str(),
                active_job_ids[3].as_str(),
                active_job_ids[0].as_str(),
            ]
        );
        assert_eq!(runtime.profile.resource_dispatch_candidate_visits, 4);
        assert_eq!(runtime.profile.waiting_job_indexes_peak, 4);
        assert_eq!(runtime.profile.job_scan_items, runtime.jobs.len() as u64);
        assert!(runtime.waiting_job_indexes.is_empty());
        assert_eq!(
            runtime.running_job_indexes,
            BTreeSet::from([
                first_waiting,
                previously_started,
                urgent_waiting,
                tied_waiting,
            ])
        );
        assert_eq!(runtime.profile.running_job_indexes_peak, 4);

        for job_index in [
            first_waiting,
            previously_started,
            urgent_waiting,
            tied_waiting,
        ] {
            runtime.jobs[job_index].remaining = 1;
        }
        runtime.phase = "job_progress_and_completions".into();
        runtime.phase_job_progress().unwrap();

        let completed: Vec<_> = runtime
            .trace
            .iter()
            .filter(|item| item["kind"] == "operations_step_completed")
            .map(|item| item["entity"].as_str().unwrap())
            .collect();
        assert_eq!(
            completed,
            vec![
                active_job_ids[0].as_str(),
                active_job_ids[1].as_str(),
                active_job_ids[2].as_str(),
                active_job_ids[3].as_str(),
            ]
        );
        assert_eq!(runtime.profile.job_progress_candidate_visits, 4);
        assert_eq!(
            runtime.profile.job_scan_items,
            2 * runtime.jobs.len() as u64
        );
        assert!(runtime.waiting_job_indexes.is_empty());
        assert!(runtime.running_job_indexes.is_empty());
    }

    #[test]
    fn prepared_steps_preserve_spare_deduplication_and_dynamic_injection() {
        let mut plan = synthetic_plan();
        plan.activities[0].steps[0].spares = vec![
            ("z-part".into(), 1),
            ("a-part".into(), 2),
            ("z-part".into(), 3),
        ];
        let mut runtime = Runtime::new(plan, "test-fingerprint".into(), 0).unwrap();
        let static_spares = runtime.prepared.activities[0].steps[0]
            .static_spares
            .clone();
        assert_eq!(
            static_spares.as_ref(),
            &[("a-part".into(), 2), ("z-part".into(), 3)]
        );

        runtime.create_job(0, 0, "test", None, None, None).unwrap();
        let job_index = runtime.jobs.len() - 1;
        runtime.jobs[job_index].injected_spares = vec![("z-part".into(), 4), ("b-part".into(), 5)];
        let requirements = runtime.step_requirements(job_index, static_spares.clone(), 1);
        assert_eq!(
            requirements.as_slice(),
            &[
                ("a-part".into(), 2),
                ("b-part".into(), 5),
                ("z-part".into(), 7),
            ]
        );

        runtime.jobs[job_index].kind = "repair".into();
        runtime.jobs[job_index].maintenance_method = Some("non_replacement".into());
        assert!(
            runtime
                .step_requirements(job_index, static_spares, 1)
                .is_empty()
        );
    }

    #[test]
    fn completed_step_is_visible_to_same_minute_dispatch_and_zero_duration_waits_for_progress() {
        let mut plan = synthetic_plan();
        let mut second_step = plan.activities[0].steps[0].clone();
        second_step.index = 1;
        second_step.code = "PRE-2".into();
        second_step.duration_minutes = 0;
        plan.activities[0].steps[0].duration_minutes = 1;
        plan.activities[0].steps.push(second_step);
        let mut runtime = Runtime::from_shared_profiled(
            Arc::new(plan),
            "test-fingerprint".into(),
            0,
            ObservationLevel::Summary,
        )
        .unwrap();
        runtime.minute = 1;
        runtime.create_job(0, 0, "test", None, None, None).unwrap();
        let job_index = runtime.jobs.len() - 1;
        runtime.phase_start_waiting_jobs().unwrap();
        assert_eq!(runtime.jobs[job_index].state, "running");

        runtime.minute = 2;
        runtime.phase_job_progress().unwrap();
        assert_eq!(runtime.jobs[job_index].state, "waiting");
        assert_eq!(runtime.jobs[job_index].step_index, 1);
        runtime.phase_start_waiting_jobs().unwrap();
        assert_eq!(runtime.jobs[job_index].state, "running");
        assert_eq!(runtime.jobs[job_index].remaining, 0);

        runtime.minute = 3;
        runtime.phase_job_progress().unwrap();
        assert_eq!(runtime.jobs[job_index].state, "completed");
        assert_eq!(runtime.jobs[job_index].completed_time, Some(3));
        assert_eq!(runtime.profile.resource_dispatch_candidate_visits, 2);
        assert_eq!(runtime.profile.job_progress_candidate_visits, 2);
    }

    #[test]
    fn cancellation_removes_active_jobs_releases_resources_and_defers_reservation_return() {
        let mut runtime = Runtime::from_shared_profiled(
            Arc::new(synthetic_plan()),
            "test-fingerprint".into(),
            0,
            ObservationLevel::Summary,
        )
        .unwrap();
        runtime.minute = 10;
        for _ in 0..2 {
            runtime
                .create_job(0, 0, "preflight", Some(0), None, None)
                .unwrap();
        }
        runtime.phase_start_waiting_jobs().unwrap();
        let active: Vec<_> = runtime
            .waiting_job_indexes
            .union(&runtime.running_job_indexes)
            .copied()
            .collect();
        assert_eq!(active.len(), 2);
        runtime.jobs[active[0]]
            .spare_reservations
            .insert("reserved-part".into(), 2);
        runtime.jobs[active[1]]
            .spare_reservations
            .insert("reserved-part".into(), 3);

        runtime.cancel_mission_preflight(0).unwrap();

        assert!(runtime.waiting_job_indexes.is_empty());
        assert!(runtime.running_job_indexes.is_empty());
        assert_eq!(runtime.resources[0].personnel_in_use, 0);
        assert_eq!(runtime.resources[0].equipment_in_use, 0);
        assert_eq!(runtime.resources[0].inventory.get("reserved-part"), None);
        assert_eq!(
            runtime
                .jobs
                .iter()
                .map(|job| job.state.as_str())
                .collect::<Vec<_>>(),
            vec!["cancelled", "cancelled"]
        );

        runtime.minute += 1;
        runtime.phase_transport_arrivals();
        assert_eq!(
            runtime.resources[0].inventory.get("reserved-part"),
            Some(&5)
        );
        assert!(
            runtime
                .jobs
                .iter()
                .all(|job| job.spare_reservations.is_empty())
        );
    }
}
