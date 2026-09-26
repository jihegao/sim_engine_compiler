//! Independent executor for the deliberately bounded `abm-tick-v1` profile.

use std::{
    cmp::Ordering,
    collections::{BTreeMap, BTreeSet},
    num::NonZeroUsize,
    sync::Arc,
    thread,
};

use anyhow::{Context, Result, bail};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Number, Value, json};
use sha2::{Digest, Sha256};

use crate::abm_plan::{
    ABM_PROFILE, AbmPlan, AbmPlanEnvelope, AbmState, Agent, ChildMoveMode, CommitMode, DeathMode,
    LocalRejection, MetricSource, MoveMode, Neighborhood, Operation, Patch, ReadView, Reducer,
    StopTiming, Target, TopologyKind, Traversal, WriteTarget,
};
use crate::plan::ExecutionPlan;

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct AbmRandomRequest {
    pub sequence: u64,
    pub tick: i64,
    pub phase: String,
    pub address: String,
    pub entity_id: String,
    pub distribution: String,
    pub args: Vec<Value>,
    pub value: Value,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct AbmEvent {
    pub sequence: u64,
    pub tick: i64,
    pub phase: String,
    pub kind: String,
    pub entity: String,
    pub details: Value,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct AbmRunResult {
    pub profile: String,
    pub seed: i64,
    pub ticks: u64,
    pub stop_reason: String,
    pub state: AbmState,
    pub events: Vec<AbmEvent>,
    pub random_requests: Vec<AbmRandomRequest>,
    pub metrics: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct AbmBatchSampleResult {
    pub sample_index: i64,
    pub result: AbmRunResult,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbmSampleRequest {
    pub sample_index: i64,
    pub seed: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub random_tape: Option<AbmRandomTape>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbmRandomTape {
    pub schema_version: String,
    pub requests: Vec<AbmRandomTapeEntry>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbmRandomTapeEntry {
    pub tick: i64,
    pub phase: String,
    pub address: String,
    pub entity_id: String,
    pub occurrence: i64,
    pub distribution: String,
    pub args: Vec<Value>,
    pub value: Value,
}

#[derive(Clone, Debug)]
struct RuntimeAgent {
    id: String,
    kind: String,
    x: f64,
    y: f64,
    vars: BTreeMap<String, Value>,
    eligible_tick: i64,
}

#[derive(Clone, Debug)]
struct RuntimeState {
    globals: BTreeMap<String, Value>,
    patches: BTreeMap<String, Patch>,
    patch_at: BTreeMap<(i64, i64), String>,
    agents: BTreeMap<String, RuntimeAgent>,
}

#[derive(Clone, Debug)]
enum Actor {
    Patch(String),
    Agent(String),
    Global,
}

impl Actor {
    fn id(&self) -> &str {
        match self {
            Self::Patch(id) | Self::Agent(id) => id,
            Self::Global => "globals",
        }
    }
}

#[derive(Clone, Debug)]
enum ResolvedTarget {
    Patch(String),
    Agent(String),
    Globals,
}

#[derive(Clone, Debug)]
enum Effect {
    Write {
        target: WriteTarget,
        actor: Actor,
        field: String,
        value: Value,
        kind: &'static str,
    },
    Move {
        entity: String,
        to: (f64, f64),
        heading: Option<Value>,
    },
    BirthMany {
        parent: String,
        children: Vec<RuntimeAgent>,
    },
    Death {
        entity: String,
        killer: Option<String>,
    },
}

struct Runtime<'a> {
    plan: &'a AbmPlan,
    seed: i64,
    state: RuntimeState,
    events: Vec<AbmEvent>,
    random_requests: Vec<AbmRandomRequest>,
    occurrences: BTreeMap<(i64, String, String, String), u64>,
    birth_ordinals: BTreeMap<(i64, String, String, String), u64>,
    random_tape: Option<AbmRandomTape>,
    tape_cursor: usize,
}

#[derive(Clone)]
struct EvalContext<'a> {
    state: &'a RuntimeState,
    actor: Actor,
    outer: Option<Actor>,
    tick: i64,
    phase: &'a str,
}

pub fn run_abm_plan(plan: &AbmPlanEnvelope, seed: i64) -> Result<AbmRunResult> {
    run_abm_plan_with_random_tape(plan, seed, None)
}

pub fn run_abm_plan_with_random_tape(
    plan: &AbmPlanEnvelope,
    seed: i64,
    random_tape: Option<AbmRandomTape>,
) -> Result<AbmRunResult> {
    plan.validate()?;
    Runtime::new(&plan.payload, seed, random_tape)?.run()
}

pub fn run_abm_plan_from_slice(bytes: &[u8], seed: i64) -> Result<AbmRunResult> {
    let plan = AbmPlanEnvelope::from_slice(bytes)?;
    run_abm_plan(&plan, seed)
}

pub fn run_abm_plan_from_slice_with_random_tape(
    bytes: &[u8],
    seed: i64,
    random_tape: Option<AbmRandomTape>,
) -> Result<AbmRunResult> {
    let plan = AbmPlanEnvelope::from_slice(bytes)?;
    run_abm_plan_with_random_tape(&plan, seed, random_tape)
}

pub fn run_abm_batch(
    plan: Arc<AbmPlanEnvelope>,
    requests: &[AbmSampleRequest],
    worker_threads: Option<usize>,
) -> Result<Vec<AbmBatchSampleResult>> {
    if requests.is_empty() {
        bail!("ABM batch request must contain at least one seed");
    }
    if worker_threads == Some(0) {
        bail!("worker_threads must be greater than zero");
    }
    plan.validate()?;
    let unique = requests
        .iter()
        .map(|request| request.sample_index)
        .collect::<BTreeSet<_>>();
    if unique.len() != requests.len() {
        bail!("ABM batch sample_index values must be unique");
    }
    if requests.iter().any(|request| request.sample_index < 0) {
        bail!("ABM batch sample_index values must be non-negative signed i64 values");
    }
    let available = thread::available_parallelism()
        .map(NonZeroUsize::get)
        .unwrap_or(1);
    let worker_threads = worker_threads
        .unwrap_or(available)
        .min(requests.len())
        .max(1);
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(worker_threads)
        .thread_name(|index| format!("abm-sample-{index}"))
        .build()?;
    let outcomes: Vec<Result<AbmBatchSampleResult>> = pool.install(|| {
        requests
            .par_iter()
            .map(|request| {
                Ok(AbmBatchSampleResult {
                    sample_index: request.sample_index,
                    result: run_abm_plan_with_random_tape(
                        &plan,
                        request.seed,
                        request.random_tape.clone(),
                    )?,
                })
            })
            .collect()
    });
    let mut samples = outcomes.into_iter().collect::<Result<Vec<_>>>()?;
    samples.sort_by_key(|sample| sample.sample_index);
    Ok(samples)
}

impl RuntimeState {
    fn from_plan(plan: &AbmPlan) -> Result<Self> {
        let mut patches = BTreeMap::new();
        let mut patch_at = BTreeMap::new();
        for patch in &plan.initial_state.patches {
            patches.insert(patch.id.clone(), patch.clone());
            patch_at.insert((patch.x, patch.y), patch.id.clone());
        }
        let mut agents = BTreeMap::new();
        for agent in &plan.initial_state.agents {
            agents.insert(
                agent.id.clone(),
                RuntimeAgent {
                    id: agent.id.clone(),
                    kind: agent.kind.clone(),
                    x: number(&agent.x, "agent.x")?,
                    y: number(&agent.y, "agent.y")?,
                    vars: agent.vars.clone(),
                    eligible_tick: 0,
                },
            );
        }
        Ok(Self {
            globals: plan.initial_state.globals.clone(),
            patches,
            patch_at,
            agents,
        })
    }

    fn output(&self) -> AbmState {
        AbmState {
            globals: self.globals.clone(),
            patches: self.patches.values().cloned().collect(),
            agents: self
                .agents
                .values()
                .map(|agent| Agent {
                    id: agent.id.clone(),
                    kind: agent.kind.clone(),
                    x: number_value(agent.x),
                    y: number_value(agent.y),
                    vars: agent.vars.clone(),
                })
                .collect(),
        }
    }
}

impl<'a> Runtime<'a> {
    fn new(plan: &'a AbmPlan, seed: i64, random_tape: Option<AbmRandomTape>) -> Result<Self> {
        if let Some(tape) = &random_tape
            && tape.schema_version != "abm-random-tape/v1"
        {
            bail!(
                "invalid_random_tape: unsupported random tape version {:?}",
                tape.schema_version
            );
        }
        if let Some(tape) = &random_tape {
            for (index, request) in tape.requests.iter().enumerate() {
                if request.phase.is_empty()
                    || request.address.is_empty()
                    || request.entity_id.is_empty()
                    || request.occurrence < 0
                    || !matches!(
                        request.distribution.as_str(),
                        "traversal_key" | "uniform" | "integer" | "bernoulli" | "choice"
                    )
                {
                    bail!("invalid_random_tape: invalid request at index {index}");
                }
                if let Err(error) = validate_random_args(&request.distribution, &request.args) {
                    bail!("invalid_random_tape: invalid request at index {index}: {error}");
                }
                validate_random_value(&request.distribution, &request.args, &request.value)?;
            }
        }
        Ok(Self {
            plan,
            seed,
            state: RuntimeState::from_plan(plan)?,
            events: Vec::new(),
            random_requests: Vec::new(),
            occurrences: BTreeMap::new(),
            birth_ordinals: BTreeMap::new(),
            random_tape,
            tape_cursor: 0,
        })
    }

    fn run(mut self) -> Result<AbmRunResult> {
        if let Some(source) = &self.plan.source_semantics {
            for phase in &source.initialization {
                self.run_phase(-1, phase, true)?;
            }
        }
        let initial_stop_phase = if self.plan.source_semantics.is_some() {
            "before_tick"
        } else {
            "initial"
        };
        if let Some(reason) = self.stop_reason(0, initial_stop_phase)? {
            self.emit(0, "stop", "stopped", reason.clone(), json!({}));
            return self.finish(0, format!("condition:{reason}"));
        }
        for tick in 0..self.plan.max_ticks {
            if self
                .plan
                .source_semantics
                .as_ref()
                .is_some_and(|source| source.stop_timing == StopTiming::BeforeTick)
                && tick > 0
            {
                if let Some(reason) = self.stop_reason(i64::try_from(tick)?, "before_tick")? {
                    self.emit(
                        i64::try_from(tick)?,
                        "stop",
                        "stopped",
                        reason.clone(),
                        json!({}),
                    );
                    return self.finish(tick, format!("condition:{reason}"));
                }
            }
            for phase in &self.plan.phases {
                self.run_phase(i64::try_from(tick)?, phase, false)?;
            }
            let completed = tick + 1;
            if self.plan.source_semantics.is_none() {
                let stop_phase = self
                    .plan
                    .phases
                    .last()
                    .map_or("initial", |phase| phase.id.as_str());
                if let Some(reason) = self.stop_reason(i64::try_from(tick)?, stop_phase)? {
                    self.emit(
                        i64::try_from(tick)?,
                        "stop",
                        "stopped",
                        reason.clone(),
                        json!({}),
                    );
                    return self.finish(completed, format!("condition:{reason}"));
                }
            }
        }
        let max_ticks = self.plan.max_ticks;
        self.finish(max_ticks, "max_ticks".to_owned())
    }

    fn finish(mut self, ticks: u64, stop_reason: String) -> Result<AbmRunResult> {
        let metrics = self.evaluate_metrics(ticks)?;
        if let Some(tape) = &self.random_tape
            && self.tape_cursor != tape.requests.len()
        {
            bail!(
                "random_tape_unused: {} unused request(s) starting at index {}",
                tape.requests.len() - self.tape_cursor,
                self.tape_cursor
            );
        }
        Ok(AbmRunResult {
            profile: ABM_PROFILE.to_owned(),
            seed: self.seed,
            ticks,
            stop_reason,
            state: self.state.output(),
            events: self.events,
            random_requests: self.random_requests,
            metrics,
        })
    }

    fn evaluate_metrics(&mut self, ticks: u64) -> Result<BTreeMap<String, Value>> {
        let state = self.state.clone();
        let mut output = BTreeMap::new();
        for metric in &self.plan.metrics {
            if metric.reducer == Reducer::Expression {
                let context = EvalContext {
                    state: &state,
                    actor: Actor::Global,
                    outer: None,
                    tick: i64::try_from(ticks)?,
                    phase: "metrics",
                };
                let value = self
                    .eval(metric.expression.as_ref().unwrap(), &context)
                    .map_err(|error| {
                        if error.to_string() == "division or modulo by zero" {
                            anyhow::anyhow!("metric_zero_denominator: division or modulo by zero")
                        } else {
                            error
                        }
                    })?;
                output.insert(metric.id.clone(), value);
                continue;
            }
            let actors = match metric.source {
                MetricSource::Agents => state
                    .agents
                    .keys()
                    .cloned()
                    .map(Actor::Agent)
                    .collect::<Vec<_>>(),
                MetricSource::Patches => state.patches.keys().cloned().map(Actor::Patch).collect(),
                MetricSource::Globals => vec![Actor::Global],
            };
            let mut values = Vec::new();
            let mut count = 0_i64;
            for actor in actors {
                let context = EvalContext {
                    state: &state,
                    actor,
                    outer: None,
                    tick: i64::try_from(ticks)?,
                    phase: "metrics",
                };
                if let Some(filter) = &metric.r#where
                    && !boolean(&self.eval(filter, &context)?, "metric where")?
                {
                    continue;
                }
                count = count.checked_add(1).context("metric count overflow")?;
                if metric.reducer != Reducer::Count {
                    let field = metric.field.as_deref().unwrap();
                    values.push(read_scope_field(self.plan, &context, "self", field)?);
                }
            }
            let value = match metric.reducer {
                Reducer::Count => Value::Number(Number::from(count)),
                Reducer::Value => values.into_iter().next().unwrap_or(Value::Null),
                Reducer::Sum => reduce_sum(&values)?,
                Reducer::Mean => {
                    if values.is_empty() {
                        Value::Null
                    } else {
                        numeric_binary(
                            "/",
                            &reduce_sum(&values)?,
                            &Value::Number(Number::from(i64::try_from(values.len())?)),
                        )?
                    }
                }
                Reducer::Min | Reducer::Max => {
                    if values.is_empty() {
                        Value::Null
                    } else {
                        let mut selected = values[0].clone();
                        number(&selected, "metric value")?;
                        for candidate in &values[1..] {
                            number(candidate, "metric value")?;
                            let ordering = metric_numeric_order(candidate, &selected)?;
                            if (metric.reducer == Reducer::Min && ordering == Ordering::Less)
                                || (metric.reducer == Reducer::Max && ordering == Ordering::Greater)
                            {
                                selected = candidate.clone();
                            }
                        }
                        selected
                    }
                }
                Reducer::Expression => unreachable!(),
            };
            output.insert(metric.id.clone(), value);
        }
        Ok(output)
    }

    fn stop_reason(&mut self, tick: i64, phase: &str) -> Result<Option<String>> {
        for condition in &self.plan.stop_conditions {
            let state = self.state.clone();
            let context = EvalContext {
                state: &state,
                actor: Actor::Global,
                outer: None,
                tick,
                phase,
            };
            let when = self.eval(&condition.when, &context)?;
            if boolean(&when, "stop condition")? {
                return Ok(Some(condition.id.clone()));
            }
        }
        Ok(None)
    }

    fn run_phase(
        &mut self,
        tick: i64,
        phase: &crate::abm_plan::Phase,
        initialization: bool,
    ) -> Result<()> {
        let phase_start = self.state.clone();
        let mut actors = match phase.target {
            Target::Patches => phase_start
                .patches
                .keys()
                .cloned()
                .map(Actor::Patch)
                .collect::<Vec<_>>(),
            Target::Agents => phase_start
                .agents
                .values()
                .filter(|agent| {
                    (initialization || agent.eligible_tick <= tick)
                        && phase
                            .agent_kind
                            .as_ref()
                            .is_none_or(|kind| kind == &agent.kind)
                })
                .map(|agent| Actor::Agent(agent.id.clone()))
                .collect(),
        };
        if let Some(selector) = &phase.r#where {
            let mut selected = Vec::with_capacity(actors.len());
            for actor in actors {
                let context = EvalContext {
                    state: &phase_start,
                    actor: actor.clone(),
                    outer: None,
                    tick,
                    phase: &phase.id,
                };
                if boolean(&self.eval(selector, &context)?, "phase selector")? {
                    selected.push(actor);
                }
            }
            actors = selected;
        }
        if phase.traversal == Traversal::Random {
            let address = phase.random_address.as_deref().unwrap();
            let mut keyed = Vec::with_capacity(actors.len());
            for actor in actors {
                let key = self.draw(
                    tick,
                    &phase.id,
                    address,
                    actor.id(),
                    "traversal_key",
                    vec![],
                )?;
                keyed.push((number(&key, "traversal key")?, actor));
            }
            keyed.sort_by(|left, right| {
                left.0
                    .partial_cmp(&right.0)
                    .unwrap_or(Ordering::Equal)
                    .then_with(|| left.1.id().cmp(right.1.id()))
            });
            actors = keyed.into_iter().map(|(_, actor)| actor).collect();
        }

        let mut buffered = Vec::new();
        for actor in actors {
            let mut dead = false;
            for operation in &phase.operations {
                if dead {
                    break;
                }
                if matches!(&actor, Actor::Agent(id) if !self.state.agents.contains_key(id)) {
                    break;
                }
                let read_state = match phase.read_view {
                    ReadView::PhaseStart => phase_start.clone(),
                    ReadView::Current => self.state.clone(),
                };
                let context = EvalContext {
                    state: &read_state,
                    actor: actor.clone(),
                    outer: None,
                    tick,
                    phase: &phase.id,
                };
                let effects = self.evaluate_operation(operation, &context)?;
                dead = effects.iter().any(|effect| {
                    matches!(effect, Effect::Death { entity, killer: None } if entity == actor.id())
                });
                for effect in effects {
                    match phase.commit_mode {
                        CommitMode::Immediate => self.commit(tick, &phase.id, effect)?,
                        CommitMode::Buffered => buffered.push(effect),
                    }
                }
            }
        }
        for effect in buffered {
            self.commit(tick, &phase.id, effect)?;
        }
        Ok(())
    }

    fn evaluate_operation(
        &mut self,
        operation: &Operation,
        context: &EvalContext<'_>,
    ) -> Result<Vec<Effect>> {
        let guard = match operation {
            Operation::Set { guard, .. }
            | Operation::Increment { guard, .. }
            | Operation::Move { guard, .. }
            | Operation::Birth { guard, .. }
            | Operation::Death { guard, .. }
            | Operation::Sprout { guard, .. } => guard,
        };
        if let Some(guard) = guard
            && !boolean(&self.eval(guard, context)?, "operation guard")?
        {
            return Ok(vec![]);
        }
        match operation {
            Operation::Set {
                target,
                field,
                value,
                ..
            } => {
                let after = self.eval(value, context)?;
                Ok(vec![Effect::Write {
                    target: *target,
                    actor: context.actor.clone(),
                    field: field.clone(),
                    value: after,
                    kind: "set",
                }])
            }
            Operation::Increment {
                target,
                field,
                value,
                ..
            } => {
                let delta = self.eval(value, context)?;
                Ok(vec![Effect::Write {
                    target: *target,
                    actor: context.actor.clone(),
                    field: field.clone(),
                    value: delta,
                    kind: "increment",
                }])
            }
            Operation::Move {
                mode,
                x,
                y,
                neighborhood,
                address,
                heading_step,
                local_rejection,
                ..
            } => {
                let Actor::Agent(id) = &context.actor else {
                    bail!("ABM move operation requires an agent actor");
                };
                let agent = context
                    .state
                    .agents
                    .get(id)
                    .context("ABM move actor is unavailable in read view")?;
                let from = (agent.x, agent.y);
                let to = match mode {
                    MoveMode::Position => (
                        number(&self.eval(x.as_ref().unwrap(), context)?, "move.x")?,
                        number(&self.eval(y.as_ref().unwrap(), context)?, "move.y")?,
                    ),
                    MoveMode::Offset => (
                        from.0 + number(&self.eval(x.as_ref().unwrap(), context)?, "move.x")?,
                        from.1 + number(&self.eval(y.as_ref().unwrap(), context)?, "move.y")?,
                    ),
                    MoveMode::HeadingStep => {
                        let step = heading_step.as_ref().unwrap();
                        let heading = read_scope_field(self.plan, context, "self", "heading")?;
                        let right_max = self.eval(&step.right_max, context)?;
                        let left_max = self.eval(&step.left_max, context)?;
                        let distance = self.eval(&step.distance, context)?;
                        let right_max = integer(&right_max, "heading_step right_max")?;
                        let left_max = integer(&left_max, "heading_step left_max")?;
                        if right_max <= 0 || left_max <= 0 {
                            bail!("heading_step turn bounds must be positive integers");
                        }
                        let right = integer(
                            &self.draw(
                                context.tick,
                                context.phase,
                                &step.right_address,
                                id,
                                "integer",
                                vec![json!(0), json!(right_max)],
                            )?,
                            "heading_step right",
                        )?;
                        let left = integer(
                            &self.draw(
                                context.tick,
                                context.phase,
                                &step.left_address,
                                id,
                                "integer",
                                vec![json!(0), json!(left_max)],
                            )?,
                            "heading_step left",
                        )?;
                        let heading = (number(&heading, "agent heading")? + right as f64
                            - left as f64)
                            .rem_euclid(360.0);
                        let radians = heading.to_radians();
                        let distance = number(&distance, "heading_step distance")?;
                        let to = (
                            strict_add(from.0, strict_mul(distance, c_sin(radians))),
                            strict_add(from.1, strict_mul(distance, c_cos(radians))),
                        );
                        let to = normalize_position(self.plan, to.0, to.1)?;
                        return Ok(vec![Effect::Move {
                            entity: id.clone(),
                            to,
                            heading: Some(number_value(heading)),
                        }]);
                    }
                    MoveMode::LocalRejection => {
                        return self.local_rejection_move(
                            context,
                            id,
                            local_rejection.as_ref().unwrap(),
                        );
                    }
                    MoveMode::RandomNeighbor
                    | MoveMode::RandomEmpty
                    | MoveMode::RandomGlobalEmpty => {
                        let origin = patch_coordinate(self.plan, from.0, from.1)?;
                        let mut candidates = if *mode == MoveMode::RandomGlobalEmpty {
                            let occupied = context
                                .state
                                .agents
                                .values()
                                .map(|agent| patch_coordinate(self.plan, agent.x, agent.y))
                                .collect::<Result<BTreeSet<_>>>()?;
                            let mut coordinates = context
                                .state
                                .patch_at
                                .keys()
                                .filter(|coordinate| !occupied.contains(coordinate))
                                .copied()
                                .collect::<Vec<_>>();
                            coordinates.sort_by_key(|(x, y)| {
                                (*y, *x, context.state.patch_at[&(*x, *y)].clone())
                            });
                            coordinates
                        } else {
                            neighbor_coordinates(self.plan, origin, neighborhood.unwrap())
                        };
                        if *mode == MoveMode::RandomEmpty {
                            candidates.retain(|coordinate| {
                                !context.state.agents.values().any(|candidate| {
                                    candidate.id != *id
                                        && patch_coordinate(self.plan, candidate.x, candidate.y)
                                            .is_ok_and(|other| other == *coordinate)
                                })
                            });
                        }
                        if candidates.is_empty() {
                            return Ok(vec![]);
                        }
                        let selected = self.draw(
                            context.tick,
                            context.phase,
                            address.as_deref().unwrap(),
                            id,
                            "integer",
                            vec![json!(0), json!(candidates.len())],
                        )?;
                        let (x, y) = candidates[integer(&selected, "move choice")? as usize];
                        (x as f64, y as f64)
                    }
                };
                let to = normalize_position(self.plan, to.0, to.1)?;
                Ok(vec![Effect::Move {
                    entity: id.clone(),
                    to,
                    heading: None,
                }])
            }
            Operation::Birth {
                kind,
                count,
                vars,
                address,
                child_move,
                ..
            } => {
                let count = integer(&self.eval(count, context)?, "birth count")?;
                if count < 0 {
                    bail!("birth count must be non-negative");
                }
                if count == 0 {
                    return Ok(vec![]);
                }
                let (x, y) = actor_position(self.plan, context)?;
                let capacity = usize::try_from(count).context("birth count is too large")?;
                let mut children = Vec::with_capacity(capacity);
                for _ in 0..count {
                    let mut child_vars = BTreeMap::new();
                    for (field, expression) in vars {
                        child_vars.insert(field.clone(), self.eval(expression, context)?);
                    }
                    let mut child_x = x;
                    let mut child_y = y;
                    if let Some(movement) = child_move {
                        let distance = self.eval(&movement.distance, context)?;
                        let heading = match movement.mode {
                            ChildMoveMode::RandomUniform => {
                                let heading_max =
                                    self.eval(movement.heading.as_ref().unwrap(), context)?;
                                let heading_max = number(&heading_max, "child heading range")?;
                                if heading_max <= 0.0 {
                                    bail!("child heading range must be positive");
                                }
                                self.draw(
                                    context.tick,
                                    context.phase,
                                    movement.address.as_deref().unwrap(),
                                    context.actor.id(),
                                    "uniform",
                                    vec![json!(0), number_value(heading_max)],
                                )?
                            }
                            ChildMoveMode::InheritHeading => {
                                read_scope_field(self.plan, context, "self", "heading")?
                            }
                        };
                        let heading_number = number(&heading, "child heading")?;
                        child_vars.insert("heading".to_owned(), heading);
                        let radians = heading_number.to_radians();
                        let distance = number(&distance, "child distance")?;
                        (child_x, child_y) = normalize_position(
                            self.plan,
                            strict_add(x, strict_mul(distance, c_sin(radians))),
                            strict_add(y, strict_mul(distance, c_cos(radians))),
                        )?;
                    }
                    let key = (
                        context.tick,
                        context.phase.to_owned(),
                        context.actor.id().to_owned(),
                        address.clone(),
                    );
                    let ordinal = self.birth_ordinals.entry(key).or_insert(0);
                    let child_id = format!(
                        "{}::{}::{}::{}",
                        context.actor.id(),
                        address,
                        context.tick,
                        *ordinal
                    );
                    *ordinal += 1;
                    children.push(RuntimeAgent {
                        id: child_id,
                        kind: kind.clone(),
                        x: child_x,
                        y: child_y,
                        vars: child_vars.clone(),
                        eligible_tick: context.tick + 1,
                    });
                }
                Ok(vec![Effect::BirthMany {
                    parent: context.actor.id().to_owned(),
                    children,
                }])
            }
            Operation::Death {
                mode,
                agent_kind,
                address,
                ..
            } => {
                let Actor::Agent(id) = &context.actor else {
                    bail!("ABM death operation requires an agent actor");
                };
                if *mode == DeathMode::Self_ {
                    return Ok(vec![Effect::Death {
                        entity: id.clone(),
                        killer: None,
                    }]);
                }
                let coordinate = actor_patch_coordinate(self.plan, context)?;
                let mut candidates = context
                    .state
                    .agents
                    .values()
                    .filter(|candidate| {
                        candidate.id != *id
                            && agent_kind
                                .as_ref()
                                .is_none_or(|kind| kind == &candidate.kind)
                            && patch_coordinate(self.plan, candidate.x, candidate.y)
                                .is_ok_and(|other| other == coordinate)
                    })
                    .map(|candidate| candidate.id.clone())
                    .collect::<Vec<_>>();
                candidates.sort();
                if candidates.is_empty() {
                    return Ok(vec![]);
                }
                let selected = integer(
                    &self.draw(
                        context.tick,
                        context.phase,
                        address.as_deref().unwrap(),
                        id,
                        "integer",
                        vec![json!(0), json!(candidates.len())],
                    )?,
                    "death target",
                )?;
                Ok(vec![Effect::Death {
                    entity: candidates[selected as usize].clone(),
                    killer: Some(id.clone()),
                }])
            }
            Operation::Sprout {
                kind,
                count,
                vars,
                address,
                ..
            } => {
                let Actor::Patch(patch_id) = &context.actor else {
                    bail!("ABM sprout operation requires a patch actor");
                };
                let count = integer(&self.eval(count, context)?, "sprout count")?;
                if count < 0 {
                    bail!("sprout count must be non-negative");
                }
                let (x, y) = actor_position(self.plan, context)?;
                let mut children = Vec::with_capacity(usize::try_from(count)?);
                for _ in 0..count {
                    let mut child_vars = BTreeMap::new();
                    for (field, expression) in vars {
                        child_vars.insert(field.clone(), self.eval(expression, context)?);
                    }
                    let key = (
                        context.tick,
                        context.phase.to_owned(),
                        patch_id.clone(),
                        address.clone(),
                    );
                    let ordinal = self.birth_ordinals.entry(key).or_insert(0);
                    let child_id = format!(
                        "{}::{}::init::{}::{}",
                        patch_id, address, context.phase, *ordinal
                    );
                    *ordinal += 1;
                    children.push(RuntimeAgent {
                        id: child_id,
                        kind: kind.clone(),
                        x,
                        y,
                        vars: child_vars,
                        eligible_tick: 0,
                    });
                }
                Ok(vec![Effect::BirthMany {
                    parent: patch_id.clone(),
                    children,
                }])
            }
        }
    }

    fn local_rejection_move(
        &mut self,
        context: &EvalContext<'_>,
        id: &str,
        local: &LocalRejection,
    ) -> Result<Vec<Effect>> {
        for ordinal in 0..local.attempt_budget {
            let (from, old_heading) = {
                let agent = self
                    .state
                    .agents
                    .get(id)
                    .context("ABM local rejection actor is unavailable")?;
                let heading = agent
                    .vars
                    .get("heading")
                    .context("ABM local rejection requires agent heading")?;
                ((agent.x, agent.y), number(heading, "agent heading")?)
            };
            let turn = number(
                &self.draw(
                    context.tick,
                    context.phase,
                    &local.turn_address,
                    id,
                    "uniform",
                    local.turn_bounds.to_vec(),
                )?,
                "local rejection turn",
            )?;
            let distance = number(
                &self.draw(
                    context.tick,
                    context.phase,
                    &local.distance_address,
                    id,
                    "uniform",
                    local.distance_bounds.to_vec(),
                )?,
                "local rejection distance",
            )?;
            let heading = strict_add(old_heading, turn).rem_euclid(360.0);
            let radians = heading.to_radians();
            let trial = normalize_position(
                self.plan,
                strict_add(from.0, strict_mul(distance, c_sin(radians))),
                strict_add(from.1, strict_mul(distance, c_cos(radians))),
            )?;
            {
                let agent = self
                    .state
                    .agents
                    .get_mut(id)
                    .context("ABM local rejection actor is unavailable")?;
                agent.x = trial.0;
                agent.y = trial.1;
                agent
                    .vars
                    .insert("heading".to_owned(), number_value(heading));
            }
            let patch = patch_coordinate(self.plan, trial.0, trial.1)?;
            let accepted = !self.state.agents.values().any(|candidate| {
                candidate.id != id
                    && patch_coordinate(self.plan, candidate.x, candidate.y)
                        .is_ok_and(|coordinate| coordinate == patch)
            });
            self.emit(
                context.tick,
                context.phase,
                "move_attempt",
                id.to_owned(),
                json!({
                    "ordinal": ordinal,
                    "turn": turn,
                    "distance": distance,
                    "from": [from.0, from.1],
                    "heading_before": old_heading,
                    "heading_after": heading,
                    "trial_position": [trial.0, trial.1],
                    "patch": [patch.0, patch.1],
                    "accepted": accepted,
                }),
            );
            if accepted {
                return Ok(vec![Effect::Move {
                    entity: id.to_owned(),
                    to: (patch.0 as f64, patch.1 as f64),
                    heading: None,
                }]);
            }
        }
        bail!(
            "random_attempt_budget_exhausted: actor {id:?} exhausted {} attempt(s) in phase {:?}",
            local.attempt_budget,
            context.phase
        )
    }

    fn commit(&mut self, tick: i64, phase: &str, effect: Effect) -> Result<()> {
        match effect {
            Effect::Write {
                target,
                actor,
                field,
                value,
                kind,
            } => {
                let Some((resolved, entity)) =
                    resolve_live_target(self.plan, &self.state, &actor, target)?
                else {
                    return Ok(());
                };
                let before = read_target_field_optional(&self.state, &resolved, &field);
                let after = if kind == "set" {
                    value
                } else {
                    numeric_binary("+", before.as_ref().unwrap_or(&Value::Null), &value)?
                };
                write_target_field(&mut self.state, &resolved, &field, after.clone())?;
                self.emit(
                    tick,
                    phase,
                    kind,
                    entity,
                    json!({"target":write_target_name(target),"field":field,"before":before,"after":after}),
                );
            }
            Effect::Move {
                entity,
                to,
                heading,
            } => {
                let agent = self
                    .state
                    .agents
                    .get_mut(&entity)
                    .with_context(|| format!("move target {entity:?} no longer exists"))?;
                let from = (agent.x, agent.y);
                agent.x = to.0;
                agent.y = to.1;
                if let Some(heading) = heading {
                    agent.vars.insert("heading".to_owned(), heading);
                }
                self.emit(
                    tick,
                    phase,
                    "moved",
                    entity,
                    json!({"from":[from.0,from.1],"to":[to.0,to.1]}),
                );
            }
            Effect::BirthMany { parent, children } => {
                for child in children {
                    let id = child.id.clone();
                    if self.state.patches.contains_key(&id) || id == "$global" {
                        bail!("birth generated reserved or duplicate stable entity ID {id:?}");
                    }
                    if self
                        .state
                        .agents
                        .insert(id.clone(), child.clone())
                        .is_some()
                    {
                        bail!("birth generated duplicate stable agent ID {id:?}");
                    }
                    self.emit(
                        tick,
                        phase,
                        "born",
                        id,
                        json!({"parent":parent,"kind":child.kind,"x":child.x,"y":child.y}),
                    );
                }
            }
            Effect::Death { entity, killer } => {
                if self.state.agents.remove(&entity).is_some() {
                    self.emit(
                        tick,
                        phase,
                        "died",
                        entity,
                        killer.map_or_else(|| json!({}), |killer| json!({"by":killer})),
                    );
                }
            }
        }
        Ok(())
    }

    fn emit(&mut self, tick: i64, phase: &str, kind: &str, entity: String, details: Value) {
        self.events.push(AbmEvent {
            sequence: self.events.len() as u64,
            tick,
            phase: phase.to_owned(),
            kind: kind.to_owned(),
            entity,
            details,
        });
    }

    fn eval(&mut self, expression: &Value, context: &EvalContext<'_>) -> Result<Value> {
        let Some(object) = expression.as_object() else {
            return Ok(expression.clone());
        };
        match object["op"].as_str().unwrap() {
            "get" => read_scope_field(
                self.plan,
                context,
                object["scope"].as_str().unwrap(),
                object["field"].as_str().unwrap(),
            ),
            "binary" => {
                let operator = object["operator"].as_str().unwrap();
                let left = self.eval(&object["left"], context)?;
                let right = self.eval(&object["right"], context)?;
                binary(operator, &left, &right)
            }
            "unary" => {
                let value = self.eval(&object["value"], context)?;
                match object["operator"].as_str().unwrap() {
                    "not" => Ok(Value::Bool(!boolean(&value, "not operand")?)),
                    "neg" => {
                        if let Some(value) = value.as_i64() {
                            Ok(Value::Number(Number::from(
                                value.checked_neg().context("integer negation overflow")?,
                            )))
                        } else {
                            Ok(number_value(-number(&value, "neg operand")?))
                        }
                    }
                    _ => unreachable!(),
                }
            }
            "count" => self.eval_count(object, context),
            "random" => {
                let args = object["args"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|argument| self.eval(argument, context))
                    .collect::<Result<Vec<_>>>()?;
                self.draw(
                    context.tick,
                    context.phase,
                    object["address"].as_str().unwrap(),
                    if matches!(context.actor, Actor::Global) {
                        "$global"
                    } else {
                        context.actor.id()
                    },
                    object["distribution"].as_str().unwrap(),
                    args,
                )
            }
            _ => unreachable!("validated expression operation"),
        }
    }

    fn eval_count(
        &mut self,
        object: &Map<String, Value>,
        context: &EvalContext<'_>,
    ) -> Result<Value> {
        let source = object["source"].as_str().unwrap();
        let kind = object["agent_kind"].as_str();
        let candidates =
            count_candidates(self.plan, context, source, kind, &object["neighborhood"])?;
        let mut count = 0_i64;
        for actor in candidates {
            let matches = if object["where"].is_null() {
                true
            } else {
                let candidate = EvalContext {
                    state: context.state,
                    actor,
                    outer: Some(context.actor.clone()),
                    tick: context.tick,
                    phase: context.phase,
                };
                boolean(&self.eval(&object["where"], &candidate)?, "count where")?
            };
            count = count
                .checked_add(i64::from(matches))
                .context("count expression overflow")?;
        }
        Ok(Value::Number(Number::from(count)))
    }

    fn draw(
        &mut self,
        tick: i64,
        phase: &str,
        address: &str,
        entity_id: &str,
        distribution: &str,
        args: Vec<Value>,
    ) -> Result<Value> {
        let key = (
            tick,
            phase.to_owned(),
            address.to_owned(),
            entity_id.to_owned(),
        );
        let occurrence = self.occurrences.entry(key).or_insert(0);
        let current_occurrence = *occurrence;
        *occurrence += 1;
        validate_random_args(distribution, &args)?;
        let value = if let Some(tape) = &self.random_tape {
            let Some(entry) = tape.requests.get(self.tape_cursor) else {
                bail!(
                    "random_tape_missing: request index {} for tick {tick}, phase {phase:?}, address {address:?}, entity {entity_id:?}, occurrence {current_occurrence}",
                    self.tape_cursor
                );
            };
            if entry.tick != tick
                || entry.phase != phase
                || entry.address != address
                || entry.entity_id != entity_id
                || entry.occurrence != i64::try_from(current_occurrence)?
                || entry.distribution != distribution
                || !equal(
                    &Value::Array(entry.args.clone()),
                    &Value::Array(args.clone()),
                )
            {
                bail!(
                    "random_tape_mismatch: request index {} does not match tick {tick}, phase {phase:?}, address {address:?}, entity {entity_id:?}, occurrence {current_occurrence}, distribution {distribution:?}, args {}",
                    self.tape_cursor,
                    Value::Array(args.clone())
                );
            }
            validate_random_value(distribution, &args, &entry.value)?;
            self.tape_cursor += 1;
            entry.value.clone()
        } else {
            let canonical = ExecutionPlan::python_canonical(&json!([
                self.seed,
                tick,
                phase,
                address,
                entity_id,
                current_occurrence
            ]))?;
            let digest = Sha256::digest(canonical.as_bytes());
            let random_bits = u64::from_be_bytes(digest[..8].try_into().unwrap()) >> 11;
            let uniform = random_bits as f64 / 9_007_199_254_740_992.0;
            generated_random_value(distribution, &args, uniform)?
        };
        self.random_requests.push(AbmRandomRequest {
            sequence: self.random_requests.len() as u64,
            tick,
            phase: phase.to_owned(),
            address: address.to_owned(),
            entity_id: entity_id.to_owned(),
            distribution: distribution.to_owned(),
            args,
            value: value.clone(),
        });
        Ok(value)
    }
}

fn validate_random_args(distribution: &str, args: &[Value]) -> Result<()> {
    match distribution {
        "traversal_key" if args.is_empty() => Ok(()),
        "uniform" => {
            if args.len() != 2 {
                bail!("uniform random requires [low, high]");
            }
            let low = number(&args[0], "uniform low")?;
            let high = number(&args[1], "uniform high")?;
            if low >= high {
                bail!("uniform random requires low < high");
            }
            Ok(())
        }
        "integer" => {
            if args.len() != 2 {
                bail!("integer random requires [low, high]");
            }
            let low = integer(&args[0], "integer low")?;
            let high = integer(&args[1], "integer high")?;
            if low >= high || high.checked_sub(low).is_none() {
                bail!("integer random requires low < high");
            }
            Ok(())
        }
        "bernoulli" => {
            if args.len() != 1 {
                bail!("bernoulli random requires [probability]");
            }
            let probability = number(&args[0], "bernoulli probability")?;
            if !(0.0..=1.0).contains(&probability) {
                bail!("bernoulli probability must be in [0, 1]");
            }
            Ok(())
        }
        "choice" => {
            if args.len() != 1 {
                bail!("choice random requires one list argument");
            }
            let choices = args[0]
                .as_array()
                .context("choice argument must be a list")?;
            if choices.is_empty() {
                bail!("choice random requires a non-empty list");
            }
            Ok(())
        }
        _ => bail!("unsupported ABM random distribution {distribution:?}"),
    }
}

fn validate_random_value(distribution: &str, args: &[Value], value: &Value) -> Result<()> {
    let valid = match distribution {
        "traversal_key" => value
            .as_f64()
            .is_some_and(|item| item.is_finite() && (0.0..1.0).contains(&item)),
        "uniform" => {
            let low = number(&args[0], "uniform low")?;
            let high = number(&args[1], "uniform high")?;
            value
                .as_f64()
                .is_some_and(|item| item.is_finite() && item >= low && item < high)
        }
        "integer" => {
            let low = integer(&args[0], "integer low")?;
            let high = integer(&args[1], "integer high")?;
            value
                .as_i64()
                .is_some_and(|item| item >= low && item < high)
        }
        "bernoulli" => value.is_boolean(),
        "choice" => args[0]
            .as_array()
            .unwrap()
            .iter()
            .any(|candidate| equal(candidate, value)),
        _ => unreachable!("random args validated before value"),
    };
    if !valid {
        bail!("random_tape_mismatch: supplied value is outside the requested distribution domain");
    }
    Ok(())
}

fn generated_random_value(distribution: &str, args: &[Value], uniform: f64) -> Result<Value> {
    Ok(match distribution {
        "traversal_key" => number_value(uniform),
        "uniform" => {
            let low = number(&args[0], "uniform low")?;
            let high = number(&args[1], "uniform high")?;
            number_value(low + uniform * (high - low))
        }
        "integer" => {
            let low = integer(&args[0], "integer low")?;
            let high = integer(&args[1], "integer high")?;
            let span = high
                .checked_sub(low)
                .context("integer random range overflow")?;
            let offset = (uniform * span as f64).floor() as i64;
            Value::Number(Number::from(
                low.checked_add(offset)
                    .context("integer random result overflow")?,
            ))
        }
        "bernoulli" => {
            let probability = number(&args[0], "bernoulli probability")?;
            Value::Bool(uniform < probability)
        }
        "choice" => {
            let choices = args[0]
                .as_array()
                .context("choice argument must be a list")?;
            choices[(uniform * choices.len() as f64).floor() as usize].clone()
        }
        _ => unreachable!("random args validated before generation"),
    })
}

fn write_target_name(target: WriteTarget) -> &'static str {
    match target {
        WriteTarget::Self_ => "self",
        WriteTarget::PatchHere => "patch_here",
        WriteTarget::Globals => "globals",
    }
}

fn resolve_live_target(
    plan: &AbmPlan,
    state: &RuntimeState,
    actor: &Actor,
    target: WriteTarget,
) -> Result<Option<(ResolvedTarget, String)>> {
    match target {
        WriteTarget::Globals => Ok(Some((ResolvedTarget::Globals, "$global".to_owned()))),
        WriteTarget::Self_ => match actor {
            Actor::Patch(id) if state.patches.contains_key(id) => {
                Ok(Some((ResolvedTarget::Patch(id.clone()), id.clone())))
            }
            Actor::Agent(id) if state.agents.contains_key(id) => {
                Ok(Some((ResolvedTarget::Agent(id.clone()), id.clone())))
            }
            Actor::Global => Ok(Some((ResolvedTarget::Globals, "$global".to_owned()))),
            _ => Ok(None),
        },
        WriteTarget::PatchHere => {
            let coordinate = match actor {
                Actor::Patch(id) => {
                    let Some(patch) = state.patches.get(id) else {
                        return Ok(None);
                    };
                    (patch.x, patch.y)
                }
                Actor::Agent(id) => {
                    let Some(agent) = state.agents.get(id) else {
                        return Ok(None);
                    };
                    patch_coordinate(plan, agent.x, agent.y)?
                }
                Actor::Global => bail!("global context has no patch_here"),
            };
            let id = state
                .patch_at
                .get(&coordinate)
                .context("patch_here coordinate has no patch")?;
            Ok(Some((ResolvedTarget::Patch(id.clone()), id.clone())))
        }
    }
}

fn read_target_field_optional(
    state: &RuntimeState,
    target: &ResolvedTarget,
    field: &str,
) -> Option<Value> {
    match target {
        ResolvedTarget::Globals => state.globals.get(field),
        ResolvedTarget::Patch(id) => state.patches.get(id).and_then(|item| item.vars.get(field)),
        ResolvedTarget::Agent(id) => state.agents.get(id).and_then(|item| item.vars.get(field)),
    }
    .cloned()
}

fn write_target_field(
    state: &mut RuntimeState,
    target: &ResolvedTarget,
    field: &str,
    value: Value,
) -> Result<()> {
    let values = match target {
        ResolvedTarget::Globals => &mut state.globals,
        ResolvedTarget::Patch(id) => {
            &mut state
                .patches
                .get_mut(id)
                .with_context(|| format!("ABM patch target {id:?} no longer exists"))?
                .vars
        }
        ResolvedTarget::Agent(id) => {
            &mut state
                .agents
                .get_mut(id)
                .with_context(|| format!("ABM agent target {id:?} no longer exists"))?
                .vars
        }
    };
    values.insert(field.to_owned(), value);
    Ok(())
}

fn read_scope_field(
    plan: &AbmPlan,
    context: &EvalContext<'_>,
    scope: &str,
    field: &str,
) -> Result<Value> {
    match scope {
        "globals" => context.state.globals.get(field).cloned(),
        "self" => match &context.actor {
            Actor::Patch(id) => entity_patch_field(context.state.patches.get(id), field),
            Actor::Agent(id) => entity_agent_field(context.state.agents.get(id), field),
            Actor::Global => context.state.globals.get(field).cloned(),
        },
        "outer" => match context
            .outer
            .as_ref()
            .context("outer requires aggregate context")?
        {
            Actor::Patch(id) => entity_patch_field(context.state.patches.get(id), field),
            Actor::Agent(id) => entity_agent_field(context.state.agents.get(id), field),
            Actor::Global => context.state.globals.get(field).cloned(),
        },
        "patch_here" => {
            let coordinate = actor_patch_coordinate(plan, context)?;
            let id = context.state.patch_at.get(&coordinate);
            entity_patch_field(id.and_then(|id| context.state.patches.get(id)), field)
        }
        _ => unreachable!("validated get scope"),
    }
    .with_context(|| format!("ABM field {scope}.{field} does not exist"))
}

fn entity_patch_field(patch: Option<&Patch>, field: &str) -> Option<Value> {
    let patch = patch?;
    match field {
        "id" => Some(Value::String(patch.id.clone())),
        "x" => Some(Value::Number(Number::from(patch.x))),
        "y" => Some(Value::Number(Number::from(patch.y))),
        _ => patch.vars.get(field).cloned(),
    }
}

fn entity_agent_field(agent: Option<&RuntimeAgent>, field: &str) -> Option<Value> {
    let agent = agent?;
    match field {
        "id" => Some(Value::String(agent.id.clone())),
        "kind" => Some(Value::String(agent.kind.clone())),
        "x" => Some(number_value(agent.x)),
        "y" => Some(number_value(agent.y)),
        _ => agent.vars.get(field).cloned(),
    }
}

fn actor_position(plan: &AbmPlan, context: &EvalContext<'_>) -> Result<(f64, f64)> {
    match &context.actor {
        Actor::Patch(id) => {
            let patch = context
                .state
                .patches
                .get(id)
                .context("patch actor not found")?;
            Ok((patch.x as f64, patch.y as f64))
        }
        Actor::Agent(id) => {
            let agent = context
                .state
                .agents
                .get(id)
                .context("agent actor not found")?;
            Ok((agent.x, agent.y))
        }
        Actor::Global => {
            let _ = plan;
            bail!("global context has no position")
        }
    }
}

fn actor_patch_coordinate(plan: &AbmPlan, context: &EvalContext<'_>) -> Result<(i64, i64)> {
    match &context.actor {
        Actor::Patch(id) => {
            let patch = context
                .state
                .patches
                .get(id)
                .context("patch actor not found")?;
            Ok((patch.x, patch.y))
        }
        Actor::Agent(id) => {
            let agent = context
                .state
                .agents
                .get(id)
                .context("agent actor not found")?;
            patch_coordinate(plan, agent.x, agent.y)
        }
        Actor::Global => bail!("global context has no patch_here"),
    }
}

fn patch_coordinate(plan: &AbmPlan, x: f64, y: f64) -> Result<(i64, i64)> {
    let x = (x + 0.5).floor() as i64;
    let y = (y + 0.5).floor() as i64;
    normalize_coordinate(plan, x, y)
}

fn normalize_coordinate(plan: &AbmPlan, x: i64, y: i64) -> Result<(i64, i64)> {
    match plan.topology.kind {
        TopologyKind::Torus => Ok((
            x.rem_euclid(plan.topology.width as i64),
            y.rem_euclid(plan.topology.height as i64),
        )),
        TopologyKind::Finite
            if x >= 0
                && y >= 0
                && x < plan.topology.width as i64
                && y < plan.topology.height as i64 =>
        {
            Ok((x, y))
        }
        TopologyKind::Finite => bail!("ABM coordinate ({x}, {y}) is outside finite topology"),
    }
}

fn normalize_position(plan: &AbmPlan, x: f64, y: f64) -> Result<(f64, f64)> {
    if !x.is_finite() || !y.is_finite() {
        bail!("ABM movement produced non-finite position");
    }
    match plan.topology.kind {
        TopologyKind::Torus => Ok((
            strict_add(
                strict_rem_euclid(strict_add(x, 0.5), plan.topology.width as f64),
                -0.5,
            ),
            strict_add(
                strict_rem_euclid(strict_add(y, 0.5), plan.topology.height as f64),
                -0.5,
            ),
        )),
        TopologyKind::Finite
            if x >= -0.5
                && y >= -0.5
                && x < plan.topology.width as f64 - 0.5
                && y < plan.topology.height as f64 - 0.5 =>
        {
            Ok((x, y))
        }
        TopologyKind::Finite => bail!("ABM movement leaves finite topology"),
    }
}

fn neighbor_coordinates(
    plan: &AbmPlan,
    center: (i64, i64),
    neighborhood: Neighborhood,
) -> Vec<(i64, i64)> {
    let mut result = BTreeSet::new();
    for dy in -1_i64..=1 {
        for dx in -1_i64..=1 {
            if (dx == 0 && dy == 0)
                || (neighborhood == Neighborhood::VonNeumann && dx.abs() + dy.abs() != 1)
            {
                continue;
            }
            if let Ok(coordinate) = normalize_coordinate(plan, center.0 + dx, center.1 + dy)
                && coordinate != center
            {
                result.insert(coordinate);
            }
        }
    }
    let mut result = result.into_iter().collect::<Vec<_>>();
    result.sort_by_key(|coordinate| {
        plan.initial_state
            .patches
            .iter()
            .find(|patch| (patch.x, patch.y) == *coordinate)
            .map(|patch| patch.id.as_str())
            .unwrap_or("")
    });
    result
}

fn count_candidates(
    plan: &AbmPlan,
    context: &EvalContext<'_>,
    source: &str,
    kind: Option<&str>,
    neighborhood: &Value,
) -> Result<Vec<Actor>> {
    match source {
        "agents" => Ok(context
            .state
            .agents
            .values()
            .filter(|agent| kind.is_none_or(|kind| agent.kind == kind))
            .map(|agent| Actor::Agent(agent.id.clone()))
            .collect()),
        "patches" => Ok(context
            .state
            .patches
            .keys()
            .cloned()
            .map(Actor::Patch)
            .collect()),
        "agents_here" => {
            let coordinate = actor_patch_coordinate(plan, context)?;
            Ok(context
                .state
                .agents
                .values()
                .filter(|agent| {
                    kind.is_none_or(|kind| agent.kind == kind)
                        && patch_coordinate(plan, agent.x, agent.y)
                            .is_ok_and(|other| other == coordinate)
                })
                .map(|agent| Actor::Agent(agent.id.clone()))
                .collect())
        }
        "neighbors" => {
            let center = actor_patch_coordinate(plan, context)?;
            let neighborhood = match neighborhood.as_str().unwrap() {
                "moore" => Neighborhood::Moore,
                "von_neumann" => Neighborhood::VonNeumann,
                _ => unreachable!(),
            };
            let coordinates = neighbor_coordinates(plan, center, neighborhood);
            if let Some(kind) = kind {
                let set = coordinates.into_iter().collect::<BTreeSet<_>>();
                Ok(context
                    .state
                    .agents
                    .values()
                    .filter(|agent| {
                        (kind == "*" || agent.kind == kind)
                            && patch_coordinate(plan, agent.x, agent.y)
                                .is_ok_and(|coordinate| set.contains(&coordinate))
                    })
                    .map(|agent| Actor::Agent(agent.id.clone()))
                    .collect())
            } else {
                Ok(coordinates
                    .into_iter()
                    .filter_map(|coordinate| context.state.patch_at.get(&coordinate))
                    .cloned()
                    .map(Actor::Patch)
                    .collect())
            }
        }
        _ => unreachable!(),
    }
}

fn reduce_sum(values: &[Value]) -> Result<Value> {
    let mut total = Value::Number(Number::from(0));
    for value in values {
        total = numeric_binary("+", &total, value)?;
    }
    Ok(total)
}

fn binary(operator: &str, left: &Value, right: &Value) -> Result<Value> {
    match operator {
        "+" | "-" | "*" | "/" | "%" => numeric_binary(operator, left, right),
        "==" => Ok(Value::Bool(equal(left, right))),
        "!=" => Ok(Value::Bool(!equal(left, right))),
        "<" | "<=" | ">" | ">=" => {
            let ordering = numeric_order(left, right)?;
            Ok(Value::Bool(match operator {
                "<" => ordering == Ordering::Less,
                "<=" => ordering != Ordering::Greater,
                ">" => ordering == Ordering::Greater,
                ">=" => ordering != Ordering::Less,
                _ => unreachable!(),
            }))
        }
        "and" => Ok(Value::Bool(
            boolean(left, "and left operand")? && boolean(right, "and right operand")?,
        )),
        "or" => Ok(Value::Bool(
            boolean(left, "or left operand")? || boolean(right, "or right operand")?,
        )),
        _ => unreachable!(),
    }
}

fn numeric_binary(operator: &str, left: &Value, right: &Value) -> Result<Value> {
    if operator != "/"
        && let (Some(left), Some(right)) = (left.as_i64(), right.as_i64())
    {
        let value = match operator {
            "+" => left
                .checked_add(right)
                .context("integer addition overflow")?,
            "-" => left
                .checked_sub(right)
                .context("integer subtraction overflow")?,
            "*" => left
                .checked_mul(right)
                .context("integer multiplication overflow")?,
            "%" => {
                if right == 0 {
                    bail!("modulo by zero");
                }
                if left == i64::MIN && right == -1 {
                    0
                } else {
                    left.rem_euclid(right)
                }
            }
            _ => unreachable!(),
        };
        return Ok(Value::Number(Number::from(value)));
    }
    let left = number(left, "numeric left operand")?;
    let right = number(right, "numeric right operand")?;
    if matches!(operator, "/" | "%") && right == 0.0 {
        bail!("division or modulo by zero");
    }
    let value = match operator {
        "+" => left + right,
        "-" => left - right,
        "*" => left * right,
        "/" => left / right,
        "%" => left - (left / right).floor() * right,
        _ => unreachable!(),
    };
    Ok(number_value(value))
}

fn equal(left: &Value, right: &Value) -> bool {
    match (left, right) {
        (Value::Null, Value::Null) => true,
        (Value::Bool(left), Value::Bool(right)) => left == right,
        (Value::String(left), Value::String(right)) => left == right,
        (Value::Number(left), Value::Number(right)) => equal_number(left, right),
        (Value::Array(left), Value::Array(right)) => {
            left.len() == right.len()
                && left
                    .iter()
                    .zip(right)
                    .all(|(left, right)| equal(left, right))
        }
        (Value::Object(left), Value::Object(right)) => {
            left.len() == right.len()
                && left
                    .iter()
                    .all(|(key, left)| right.get(key).is_some_and(|right| equal(left, right)))
        }
        _ => false,
    }
}

fn equal_number(left: &Number, right: &Number) -> bool {
    match (left.as_i64(), right.as_i64()) {
        (Some(left), Some(right)) => left == right,
        (Some(integer), None) => equal_integer_float(integer, right),
        (None, Some(integer)) => equal_integer_float(integer, left),
        (None, None) => left.as_f64() == right.as_f64(),
    }
}

fn equal_integer_float(integer: i64, float: &Number) -> bool {
    let Some(float) = float.as_f64() else {
        return false;
    };
    float.is_finite()
        && float.fract() == 0.0
        && float >= i64::MIN as f64
        && float < 9_223_372_036_854_775_808.0
        && float as i64 == integer
}

fn numeric_order(left: &Value, right: &Value) -> Result<Ordering> {
    metric_numeric_order(left, right)
}

fn metric_numeric_order(left: &Value, right: &Value) -> Result<Ordering> {
    if left.is_boolean() || right.is_boolean() {
        bail!("metric values must be numeric, not boolean");
    }
    let left = left.as_number().context("metric value must be numeric")?;
    let right = right.as_number().context("metric value must be numeric")?;
    match (left.as_i64(), right.as_i64()) {
        (Some(left), Some(right)) => Ok(left.cmp(&right)),
        (Some(left), None) => integer_float_order(left, right),
        (None, Some(right)) => integer_float_order(right, left).map(Ordering::reverse),
        (None, None) => left
            .as_f64()
            .filter(|value| value.is_finite())
            .zip(right.as_f64().filter(|value| value.is_finite()))
            .and_then(|(left, right)| left.partial_cmp(&right))
            .context("metric values must be finite numbers"),
    }
}

fn integer_float_order(integer: i64, float: &Number) -> Result<Ordering> {
    let float = float
        .as_f64()
        .filter(|value| value.is_finite())
        .context("metric values must be finite numbers")?;
    if float >= 9_223_372_036_854_775_808.0 {
        return Ok(Ordering::Less);
    }
    if float < i64::MIN as f64 {
        return Ok(Ordering::Greater);
    }
    let truncated = float.trunc() as i64;
    let integer_order = integer.cmp(&truncated);
    if integer_order != Ordering::Equal {
        return Ok(integer_order);
    }
    Ok(if float.fract() > 0.0 {
        Ordering::Less
    } else if float.fract() < 0.0 {
        Ordering::Greater
    } else {
        Ordering::Equal
    })
}

fn number(value: &Value, label: &str) -> Result<f64> {
    if value.is_boolean() {
        bail!("{label} must be numeric, not boolean");
    }
    value
        .as_f64()
        .filter(|value| value.is_finite())
        .with_context(|| format!("{label} must be a finite number"))
}

fn integer(value: &Value, label: &str) -> Result<i64> {
    if value.is_boolean() {
        bail!("{label} must be an integer, not boolean");
    }
    value
        .as_i64()
        .with_context(|| format!("{label} must be an integer"))
}

fn boolean(value: &Value, label: &str) -> Result<bool> {
    value
        .as_bool()
        .with_context(|| format!("{label} must be boolean"))
}

fn number_value(value: f64) -> Value {
    Value::Number(Number::from_f64(value).expect("runtime values are finite"))
}

// CPython evaluates these as separate IEEE-754 operations. Keeping the
// boundary out of line prevents an optimized Rust build from contracting the
// multiply/add and changing the frozen cross-backend trajectory by one ULP.
#[inline(never)]
fn strict_mul(left: f64, right: f64) -> f64 {
    left * right
}

#[inline(never)]
fn strict_add(left: f64, right: f64) -> f64 {
    left + right
}

#[inline(never)]
fn strict_rem_euclid(left: f64, right: f64) -> f64 {
    let remainder = left % right;
    if remainder < 0.0 {
        remainder + right.abs()
    } else {
        remainder
    }
}

unsafe extern "C" {
    #[link_name = "sin"]
    fn c_sin_raw(value: f64) -> f64;
    #[link_name = "cos"]
    fn c_cos_raw(value: f64) -> f64;
}

fn c_sin(value: f64) -> f64 {
    // SAFETY: the C math ABI accepts and returns one finite `double`.
    unsafe { c_sin_raw(value) }
}

fn c_cos(value: f64) -> f64 {
    // SAFETY: the C math ABI accepts and returns one finite `double`.
    unsafe { c_cos_raw(value) }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::abm_plan::{ABM_PLAN_VERSION, AbmPlanEnvelope};

    fn plan(payload: Value) -> AbmPlanEnvelope {
        let fingerprint = format!(
            "{:x}",
            Sha256::digest(
                ExecutionPlan::python_canonical(
                    &json!({"version":ABM_PLAN_VERSION,"payload":payload})
                )
                .unwrap()
            )
        );
        AbmPlanEnvelope::from_slice(
            &serde_json::to_vec(&json!({
                "version":ABM_PLAN_VERSION,
                "fingerprint":fingerprint,
                "payload":payload
            }))
            .unwrap(),
        )
        .unwrap()
    }

    fn fire_payload() -> Value {
        json!({
            "model_id":"fire-line",
            "profile":"abm-tick-v1",
            "topology":{"kind":"finite","width":3,"height":1},
            "initial_state":{"globals":{},"patches":[
                {"id":"p0","x":0,"y":0,"vars":{"burning":true}},
                {"id":"p1","x":1,"y":0,"vars":{"burning":false}},
                {"id":"p2","x":2,"y":0,"vars":{"burning":false}}
            ],"agents":[]},
            "phases":[{"id":"spread","target":"patches","agent_kind":null,"read_view":"phase_start","commit_mode":"buffered","traversal":"stable","random_address":null,"operations":[
                {"op":"set","guard":{"op":"binary","operator":"and","left":{"op":"unary","operator":"not","value":{"op":"get","scope":"self","field":"burning"}},"right":{"op":"binary","operator":">","left":{"op":"count","source":"neighbors","agent_kind":null,"neighborhood":"von_neumann","where":{"op":"get","scope":"self","field":"burning"}},"right":0}},"target":"self","field":"burning","value":true}
            ]}],
            "stop_conditions":[],
            "metrics":[{"id":"burning","reducer":"count","source":"patches","field":null,"where":{"op":"get","scope":"self","field":"burning"},"expression":null}],
            "max_ticks":2
        })
    }

    fn source_move_payload() -> Value {
        json!({
            "model_id":"source-batch-isolation",
            "profile":"abm-tick-v1",
            "topology":{"kind":"torus","width":1,"height":1},
            "initial_state":{"globals":{},"patches":[
                {"id":"p0","x":0,"y":0,"vars":{}}
            ],"agents":[
                {"id":"M","kind":"person","x":0,"y":0,"vars":{"heading":0,"happy":false}}
            ]},
            "phases":[{
                "id":"move-unhappy","target":"agents","agent_kind":"person",
                "read_view":"current","commit_mode":"immediate","traversal":"stable",
                "random_address":null,"operations":[{
                    "op":"move","guard":null,"mode":"local_rejection","x":null,"y":null,
                    "neighborhood":null,"address":null,"heading_step":null,
                    "local_rejection":{
                        "turn_address":"schelling.turn","distance_address":"schelling.distance",
                        "turn_bounds":[0,360],"distance_bounds":[0,10],"attempt_budget":2
                    }
                }]
            }],
            "stop_conditions":[],"metrics":[],"max_ticks":1,
            "source_semantics":{
                "schema_version":"abm-source-semantics/v1",
                "initialization":[],"stop_timing":"before_tick"
            }
        })
    }

    fn source_move_tape(turn: f64, distance: f64) -> AbmRandomTape {
        AbmRandomTape {
            schema_version: "abm-random-tape/v1".to_owned(),
            requests: vec![
                AbmRandomTapeEntry {
                    tick: 0,
                    phase: "move-unhappy".to_owned(),
                    address: "schelling.turn".to_owned(),
                    entity_id: "M".to_owned(),
                    occurrence: 0,
                    distribution: "uniform".to_owned(),
                    args: vec![json!(0), json!(360)],
                    value: json!(turn),
                },
                AbmRandomTapeEntry {
                    tick: 0,
                    phase: "move-unhappy".to_owned(),
                    address: "schelling.distance".to_owned(),
                    entity_id: "M".to_owned(),
                    occurrence: 0,
                    distribution: "uniform".to_owned(),
                    args: vec![json!(0), json!(10)],
                    value: json!(distance),
                },
            ],
        }
    }

    #[test]
    fn buffered_phase_start_spreads_one_cell_per_tick() {
        let result = run_abm_plan(&plan(fire_payload()), 7).unwrap();
        assert_eq!(result.ticks, 2);
        assert_eq!(result.metrics["burning"], json!(3));
        assert_eq!(result.events.len(), 2);
        assert_eq!(result.events[0].entity, "p1");
        assert_eq!(result.events[1].entity, "p2");
    }

    #[test]
    fn batch_is_stable_across_worker_counts_and_repeated_seeds() {
        let plan = Arc::new(plan(fire_payload()));
        let requests = [
            AbmSampleRequest {
                sample_index: 7,
                seed: 9,
                random_tape: None,
            },
            AbmSampleRequest {
                sample_index: 2,
                seed: 9,
                random_tape: None,
            },
            AbmSampleRequest {
                sample_index: 8,
                seed: 2,
                random_tape: None,
            },
            AbmSampleRequest {
                sample_index: 1,
                seed: 7,
                random_tape: None,
            },
        ];
        let serial = run_abm_batch(plan.clone(), &requests, Some(1)).unwrap();
        let parallel = run_abm_batch(plan, &requests, Some(4)).unwrap();
        assert_eq!(
            serial.iter().map(|item| &item.result).collect::<Vec<_>>(),
            parallel.iter().map(|item| &item.result).collect::<Vec<_>>()
        );
        assert_eq!(
            serial
                .iter()
                .map(|item| item.sample_index)
                .collect::<Vec<_>>(),
            vec![1, 2, 7, 8]
        );
    }

    #[test]
    fn source_batch_isolates_tapes_and_is_stable_across_order_and_threads() {
        let plan = Arc::new(plan(source_move_payload()));
        let requests = vec![
            AbmSampleRequest {
                sample_index: 7,
                seed: 5,
                random_tape: Some(source_move_tape(0.0, 0.1)),
            },
            AbmSampleRequest {
                sample_index: 0,
                seed: 5,
                random_tape: Some(source_move_tape(90.0, 0.2)),
            },
            AbmSampleRequest {
                sample_index: 3,
                seed: 9,
                random_tape: Some(source_move_tape(180.0, 0.3)),
            },
        ];
        let serial = run_abm_batch(plan.clone(), &requests, Some(1)).unwrap();
        let mut reversed = requests.clone();
        reversed.reverse();
        let parallel = run_abm_batch(plan, &reversed, Some(4)).unwrap();

        assert_eq!(serial, parallel);
        assert_eq!(
            serial
                .iter()
                .map(|sample| sample.sample_index)
                .collect::<Vec<_>>(),
            vec![0, 3, 7]
        );
        assert_eq!(serial[0].result.seed, serial[2].result.seed);
        assert_ne!(
            serial[0].result.random_requests,
            serial[2].result.random_requests
        );
    }

    #[test]
    fn named_randomness_is_invariant_to_initial_agent_order() {
        let mut left = fire_payload();
        left["topology"] = json!({"kind":"torus","width":3,"height":1});
        left["initial_state"]["agents"] = json!([
            {"id":"a","kind":"person","x":0,"y":0,"vars":{"v":0}},
            {"id":"b","kind":"person","x":1,"y":0,"vars":{"v":0}}
        ]);
        left["phases"] = json!([{"id":"randomize","target":"agents","agent_kind":"person","read_view":"current","commit_mode":"immediate","traversal":"random","random_address":"order","operations":[
            {"op":"set","guard":null,"target":"self","field":"v","value":{"op":"random","distribution":"integer","address":"value","args":[0,100]}}
        ]}]);
        let mut right = left.clone();
        right["initial_state"]["agents"]
            .as_array_mut()
            .unwrap()
            .reverse();
        let left = run_abm_plan(&plan(left), 42).unwrap();
        let right = run_abm_plan(&plan(right), 42).unwrap();
        assert_eq!(left.state.agents, right.state.agents);
        assert_eq!(left.random_requests, right.random_requests);
    }

    #[test]
    fn expression_metric_uses_run_seed_completed_tick_and_returns_ledger() {
        let mut payload = fire_payload();
        payload["metrics"] = json!([{
            "id":"sample", "reducer":"expression", "source":"globals",
            "field":null, "where":null,
            "expression":{"op":"random","distribution":"uniform","address":"metric.sample","args":[0.0,1.0]}
        }]);
        let result = run_abm_plan(&plan(payload), 17).unwrap();
        let request = result.random_requests.last().unwrap();
        assert_eq!(request.tick, i64::try_from(result.ticks).unwrap());
        assert_eq!(request.phase, "metrics");
        assert_eq!(request.address, "metric.sample");
        assert_eq!(result.metrics["sample"], request.value);
    }

    #[test]
    fn typed_equality_preserves_i64_and_separates_booleans() {
        assert!(!equal(
            &json!(9_007_199_254_740_992_i64),
            &json!(9_007_199_254_740_993_i64)
        ));
        assert!(!equal(&json!(true), &json!(1)));
        assert!(equal(&json!(7), &json!(7.0)));
        assert!(!equal(
            &json!(9_007_199_254_740_993_i64),
            &json!(9_007_199_254_740_992.0)
        ));
        assert!(equal(
            &json!({"items":[1, true, {"x":2.0}]}),
            &json!({"items":[1.0, true, {"x":2}]})
        ));
    }

    #[test]
    fn mixed_numeric_order_is_lossless_at_i64_boundaries() {
        assert_eq!(
            numeric_order(
                &json!(9_007_199_254_740_993_i64),
                &json!(9_007_199_254_740_992.0)
            )
            .unwrap(),
            Ordering::Greater
        );
        assert_eq!(
            numeric_order(&json!(i64::MAX), &json!(9_223_372_036_854_775_808.0)).unwrap(),
            Ordering::Less
        );
        assert_eq!(
            numeric_order(&json!(i64::MIN), &json!(-9_223_372_036_854_775_808.0)).unwrap(),
            Ordering::Equal
        );
        assert_eq!(
            numeric_order(&json!(-2), &json!(-1.5)).unwrap(),
            Ordering::Less
        );
        assert_eq!(
            numeric_order(&json!(-1), &json!(-1.5)).unwrap(),
            Ordering::Greater
        );
        assert!(numeric_order(&json!(true), &json!(1.0)).is_err());
    }

    #[test]
    fn integer_arithmetic_overflow_is_an_error() {
        assert!(numeric_binary("+", &json!(i64::MAX), &json!(1)).is_err());
        assert_eq!(
            numeric_binary("%", &json!(i64::MIN), &json!(-1)).unwrap(),
            json!(0)
        );
    }

    #[test]
    fn execution_boundary_rejects_mutated_envelope_fingerprint() {
        let mut envelope = plan(fire_payload());
        envelope.payload.max_ticks += 1;
        let error = run_abm_plan(&envelope, 0).unwrap_err();
        assert!(error.to_string().contains("fingerprint mismatch"));
    }
}
