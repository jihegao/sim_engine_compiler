//! Strict loader for the independent `abm-tick-plan/v1` contract.
//!
//! This module is intentionally separate from the aircraft-support Plan ABI.
//! It validates the complete JSON surface before a runtime sees the plan and
//! rejects fields or capabilities that are not part of the frozen profile.

use std::collections::{BTreeMap, BTreeSet};

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

use crate::plan::ExecutionPlan;

pub const ABM_PLAN_VERSION: &str = "abm-tick-plan/v1";
pub const ABM_PROFILE: &str = "abm-tick-v1";
pub const MAX_GRID_CELLS: i64 = 1_000_000;

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbmPlanEnvelope {
    pub version: String,
    pub fingerprint: String,
    pub payload: AbmPlan,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbmPlan {
    pub model_id: String,
    pub profile: String,
    pub topology: Topology,
    pub initial_state: AbmState,
    pub phases: Vec<Phase>,
    pub stop_conditions: Vec<StopCondition>,
    pub metrics: Vec<Metric>,
    pub max_ticks: u64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Topology {
    pub kind: TopologyKind,
    pub width: u64,
    pub height: u64,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TopologyKind {
    Finite,
    Torus,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AbmState {
    pub globals: BTreeMap<String, Value>,
    pub patches: Vec<Patch>,
    pub agents: Vec<Agent>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Patch {
    pub id: String,
    pub x: i64,
    pub y: i64,
    pub vars: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Agent {
    pub id: String,
    pub kind: String,
    pub x: Value,
    pub y: Value,
    pub vars: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Phase {
    pub id: String,
    pub target: Target,
    pub agent_kind: Option<String>,
    pub read_view: ReadView,
    pub commit_mode: CommitMode,
    pub traversal: Traversal,
    pub random_address: Option<String>,
    pub operations: Vec<Operation>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Target {
    Patches,
    Agents,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReadView {
    PhaseStart,
    Current,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CommitMode {
    Buffered,
    Immediate,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Traversal {
    Stable,
    Random,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields, tag = "op", rename_all = "snake_case")]
pub enum Operation {
    Set {
        guard: Option<Value>,
        target: WriteTarget,
        field: String,
        value: Value,
    },
    Increment {
        guard: Option<Value>,
        target: WriteTarget,
        field: String,
        value: Value,
    },
    Move {
        guard: Option<Value>,
        mode: MoveMode,
        x: Option<Value>,
        y: Option<Value>,
        neighborhood: Option<Neighborhood>,
        address: Option<String>,
        heading_step: Option<HeadingStep>,
    },
    Birth {
        guard: Option<Value>,
        kind: String,
        count: Value,
        vars: BTreeMap<String, Value>,
        address: String,
        child_move: Option<ChildMove>,
    },
    Death {
        guard: Option<Value>,
        mode: DeathMode,
        agent_kind: Option<String>,
        address: Option<String>,
    },
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct HeadingStep {
    pub right_max: Value,
    pub left_max: Value,
    pub distance: Value,
    pub right_address: String,
    pub left_address: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ChildMove {
    pub mode: ChildMoveMode,
    pub heading: Option<Value>,
    pub address: Option<String>,
    pub distance: Value,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ChildMoveMode {
    RandomUniform,
    InheritHeading,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DeathMode {
    #[serde(rename = "self")]
    Self_,
    RandomAgentHere,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WriteTarget {
    #[serde(rename = "self")]
    Self_,
    PatchHere,
    Globals,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MoveMode {
    Position,
    Offset,
    RandomNeighbor,
    RandomEmpty,
    RandomGlobalEmpty,
    HeadingStep,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Neighborhood {
    Moore,
    VonNeumann,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct StopCondition {
    pub id: String,
    pub when: Value,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Metric {
    pub id: String,
    pub reducer: Reducer,
    pub source: MetricSource,
    pub field: Option<String>,
    pub r#where: Option<Value>,
    pub expression: Option<Value>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reducer {
    Count,
    Sum,
    Mean,
    Min,
    Max,
    Value,
    Expression,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MetricSource {
    Agents,
    Patches,
    Globals,
}

impl AbmPlanEnvelope {
    pub fn from_slice(bytes: &[u8]) -> Result<Self> {
        let raw: Value = serde_json::from_slice(bytes).context("ABM Plan must be valid JSON")?;
        let object = raw
            .as_object()
            .context("ABM Plan envelope must be an object")?;
        let expected = BTreeSet::from(["fingerprint", "payload", "version"]);
        let actual = object.keys().map(String::as_str).collect::<BTreeSet<_>>();
        if actual != expected {
            bail!("ABM Plan envelope has unknown or missing fields");
        }
        if raw["version"] != ABM_PLAN_VERSION {
            bail!("unsupported ABM Plan version {:?}", raw["version"]);
        }
        let actual_fingerprint = digest(&json!({
            "version": raw["version"].clone(),
            "payload": raw["payload"].clone(),
        }))?;
        let expected_fingerprint = raw["fingerprint"]
            .as_str()
            .context("ABM Plan fingerprint must be a string")?;
        if expected_fingerprint != actual_fingerprint {
            bail!("ABM Plan fingerprint mismatch");
        }
        let raw_payload = raw["payload"].clone();
        let envelope: Self = serde_json::from_value(raw).context("invalid ABM Plan structure")?;
        if serde_json::to_value(&envelope.payload)? != raw_payload {
            bail!("ABM Plan payload has missing optional-shape fields or non-canonical values");
        }
        envelope.validate()?;
        Ok(envelope)
    }

    pub fn validate(&self) -> Result<()> {
        if self.version != ABM_PLAN_VERSION {
            bail!("unsupported ABM Plan version {:?}", self.version);
        }
        let actual_fingerprint = digest(&json!({
            "version": self.version,
            "payload": self.payload,
        }))?;
        if self.fingerprint != actual_fingerprint {
            bail!("ABM Plan fingerprint mismatch");
        }
        self.payload.validate()
    }
}

impl AbmPlan {
    pub fn validate(&self) -> Result<()> {
        identifier(&self.model_id, "payload.model_id")?;
        if self.profile != ABM_PROFILE {
            bail!("unsupported ABM profile {:?}", self.profile);
        }
        if self.topology.width == 0 || self.topology.height == 0 {
            bail!("ABM topology dimensions must be positive integers");
        }
        if self.topology.width > i64::MAX as u64 || self.topology.height > i64::MAX as u64 {
            bail!("ABM topology dimensions exceed the runtime coordinate range");
        }
        let width = i64::try_from(self.topology.width)?;
        let height = i64::try_from(self.topology.height)?;
        let expected_count = width
            .checked_mul(height)
            .context("ABM topology area exceeds signed i64 contract range")?;
        if expected_count > MAX_GRID_CELLS {
            bail!("ABM grid exceeds executable limit of {MAX_GRID_CELLS} patches");
        }
        if self.max_ticks == 0 {
            bail!("ABM max_ticks must be a positive integer");
        }
        if self.max_ticks > i64::MAX as u64 {
            bail!("ABM max_ticks exceeds signed i64 contract range");
        }

        let mut patch_ids = BTreeSet::new();
        let mut coordinates = BTreeSet::new();
        for patch in &self.initial_state.patches {
            identifier(&patch.id, "payload.initial_state.patches[].id")?;
            if patch.id == "$global" || !patch_ids.insert(patch.id.clone()) {
                bail!("duplicate ABM patch ID {:?}", patch.id);
            }
            if patch.x < 0
                || patch.y < 0
                || patch.x as u64 >= self.topology.width
                || patch.y as u64 >= self.topology.height
                || !coordinates.insert((patch.x, patch.y))
            {
                bail!("duplicate or out-of-bounds ABM patch coordinate");
            }
            validate_json_map(&patch.vars, "payload.initial_state.patches[].vars")?;
        }
        if i64::try_from(coordinates.len())? != expected_count {
            bail!("ABM state requires exactly one patch per grid coordinate");
        }
        validate_json_map(&self.initial_state.globals, "payload.initial_state.globals")?;

        let mut agent_ids = BTreeSet::new();
        for agent in &self.initial_state.agents {
            identifier(&agent.id, "payload.initial_state.agents[].id")?;
            identifier(&agent.kind, "payload.initial_state.agents[].kind")?;
            finite_number(&agent.x, "payload.initial_state.agents[].x")?;
            finite_number(&agent.y, "payload.initial_state.agents[].y")?;
            let x = agent.x.as_f64().unwrap();
            let y = agent.y.as_f64().unwrap();
            if x < -0.5
                || y < -0.5
                || x >= self.topology.width as f64 - 0.5
                || y >= self.topology.height as f64 - 0.5
            {
                bail!("initial ABM agent position is outside canonical topology bounds");
            }
            validate_json_map(&agent.vars, "payload.initial_state.agents[].vars")?;
            if agent.id == "$global"
                || patch_ids.contains(&agent.id)
                || !agent_ids.insert(agent.id.clone())
            {
                bail!("duplicate stable ABM agent business ID {:?}", agent.id);
            }
        }

        let mut phase_ids = BTreeSet::new();
        for phase in &self.phases {
            identifier(&phase.id, "payload.phases[].id")?;
            if !phase_ids.insert(&phase.id) {
                bail!("duplicate ABM phase ID {:?}", phase.id);
            }
            if phase.target == Target::Patches && phase.agent_kind.is_some() {
                bail!("ABM patch phase cannot filter agent kind");
            }
            if let Some(kind) = &phase.agent_kind {
                identifier(kind, "payload.phases[].agent_kind")?;
            }
            match phase.traversal {
                Traversal::Stable if phase.random_address.is_some() => {
                    bail!("stable ABM traversal cannot declare a random address")
                }
                Traversal::Random => identifier(
                    phase.random_address.as_deref().unwrap_or_default(),
                    "payload.phases[].random_address",
                )?,
                Traversal::Stable => {}
            }
            if phase.operations.is_empty() {
                bail!("ABM phase operations must not be empty");
            }
            for operation in &phase.operations {
                operation.validate()?;
                if phase.target == Target::Patches
                    && matches!(
                        operation,
                        Operation::Move { .. } | Operation::Birth { .. } | Operation::Death { .. }
                    )
                {
                    bail!("ABM patch phases cannot contain move, birth, or death operations");
                }
            }
        }

        let mut stop_ids = BTreeSet::new();
        for condition in &self.stop_conditions {
            identifier(&condition.id, "payload.stop_conditions[].id")?;
            if !stop_ids.insert(&condition.id) {
                bail!("duplicate ABM stop condition ID {:?}", condition.id);
            }
            validate_expression(&condition.when)?;
        }
        let mut metric_ids = BTreeSet::new();
        for metric in &self.metrics {
            identifier(&metric.id, "payload.metrics[].id")?;
            if !metric_ids.insert(&metric.id) {
                bail!("duplicate ABM metric ID {:?}", metric.id);
            }
            if !matches!(metric.reducer, Reducer::Count | Reducer::Expression)
                && metric.field.is_none()
            {
                bail!("non-count ABM metric requires a field");
            }
            if metric.reducer == Reducer::Value && metric.source != MetricSource::Globals {
                bail!("ABM value metric is only supported for globals");
            }
            if metric.reducer == Reducer::Expression {
                if metric.source != MetricSource::Globals
                    || metric.field.is_some()
                    || metric.r#where.is_some()
                    || metric.expression.is_none()
                {
                    bail!("ABM expression metric requires globals source and expression only");
                }
                validate_expression(metric.expression.as_ref().unwrap())?;
            } else if metric.expression.is_some() {
                bail!("ABM metric expression only applies to expression reducer");
            }
            if let Some(expression) = &metric.r#where {
                validate_expression(expression)?;
            }
        }
        Ok(())
    }
}

impl Operation {
    fn validate(&self) -> Result<()> {
        match self {
            Self::Set {
                guard,
                field,
                value,
                ..
            }
            | Self::Increment {
                guard,
                field,
                value,
                ..
            } => {
                identifier(field, "operation.field")?;
                validate_optional_expression(guard)?;
                validate_expression(value)?;
            }
            Self::Move {
                guard,
                mode,
                x,
                y,
                neighborhood,
                address,
                heading_step,
            } => {
                validate_optional_expression(guard)?;
                match mode {
                    MoveMode::Position | MoveMode::Offset => {
                        if x.is_none()
                            || y.is_none()
                            || neighborhood.is_some()
                            || address.is_some()
                            || heading_step.is_some()
                        {
                            bail!("position/offset movement requires x and y only");
                        }
                        validate_expression(x.as_ref().unwrap())?;
                        validate_expression(y.as_ref().unwrap())?;
                    }
                    MoveMode::RandomNeighbor | MoveMode::RandomEmpty => {
                        if x.is_some()
                            || y.is_some()
                            || neighborhood.is_none()
                            || address.as_deref().unwrap_or_default().is_empty()
                            || heading_step.is_some()
                        {
                            bail!("random movement requires neighborhood and address only");
                        }
                    }
                    MoveMode::RandomGlobalEmpty => {
                        if x.is_some()
                            || y.is_some()
                            || neighborhood.is_some()
                            || heading_step.is_some()
                            || address.as_deref().unwrap_or_default().is_empty()
                        {
                            bail!("global empty movement requires a random address only");
                        }
                    }
                    MoveMode::HeadingStep => {
                        if x.is_some() || y.is_some() || neighborhood.is_some() || address.is_some()
                        {
                            bail!("heading movement only accepts heading_step");
                        }
                        let step = heading_step
                            .as_ref()
                            .context("heading movement requires heading_step")?;
                        validate_expression(&step.right_max)?;
                        validate_expression(&step.left_max)?;
                        validate_expression(&step.distance)?;
                        identifier(&step.right_address, "operation.heading_step.right_address")?;
                        identifier(&step.left_address, "operation.heading_step.left_address")?;
                    }
                }
            }
            Self::Birth {
                guard,
                kind,
                count,
                vars,
                address,
                child_move,
            } => {
                validate_optional_expression(guard)?;
                identifier(kind, "operation.kind")?;
                identifier(address, "operation.address")?;
                validate_expression(count)?;
                for (field, expression) in vars {
                    identifier(field, "operation.vars field")?;
                    validate_expression(expression)?;
                }
                if let Some(movement) = child_move {
                    validate_expression(&movement.distance)?;
                    match movement.mode {
                        ChildMoveMode::RandomUniform => {
                            validate_expression(
                                movement
                                    .heading
                                    .as_ref()
                                    .context("random_uniform child move requires heading")?,
                            )?;
                            identifier(
                                movement.address.as_deref().unwrap_or_default(),
                                "operation.child_move.address",
                            )?;
                        }
                        ChildMoveMode::InheritHeading
                            if movement.heading.is_some() || movement.address.is_some() =>
                        {
                            bail!("inherit_heading child move requires null heading and address")
                        }
                        ChildMoveMode::InheritHeading => {}
                    }
                }
            }
            Self::Death {
                guard,
                mode,
                agent_kind,
                address,
            } => {
                validate_optional_expression(guard)?;
                match mode {
                    DeathMode::Self_ if agent_kind.is_some() || address.is_some() => {
                        bail!("self death has no target filter or random address")
                    }
                    DeathMode::RandomAgentHere => {
                        if let Some(kind) = agent_kind {
                            identifier(kind, "operation.death.agent_kind")?;
                        }
                        identifier(
                            address.as_deref().unwrap_or_default(),
                            "operation.death.address",
                        )?;
                    }
                    DeathMode::Self_ => {}
                }
            }
        }
        Ok(())
    }
}

fn validate_optional_expression(expression: &Option<Value>) -> Result<()> {
    if let Some(expression) = expression {
        validate_expression(expression)?;
    }
    Ok(())
}

pub fn validate_expression(expression: &Value) -> Result<()> {
    if expression.is_null()
        || expression.is_boolean()
        || expression.is_string()
        || expression.is_number()
        || expression.is_array()
    {
        finite_json(expression)?;
        return Ok(());
    }
    let object = expression
        .as_object()
        .context("ABM expression must be a scalar or object")?;
    let op = object
        .get("op")
        .and_then(Value::as_str)
        .context("unknown ABM expression")?;
    let exact = |fields: &[&str]| -> Result<()> {
        let wanted = fields.iter().copied().collect::<BTreeSet<_>>();
        let actual = object.keys().map(String::as_str).collect::<BTreeSet<_>>();
        if actual != wanted {
            bail!("ABM {op} expression has unknown or missing fields");
        }
        Ok(())
    };
    match op {
        "get" => {
            exact(&["op", "scope", "field"])?;
            match object["scope"].as_str() {
                Some("self" | "outer" | "patch_here" | "globals") => {}
                _ => bail!("unknown ABM get scope"),
            }
            identifier(
                object["field"].as_str().unwrap_or_default(),
                "expression.field",
            )?;
        }
        "binary" => {
            exact(&["op", "operator", "left", "right"])?;
            if !matches!(
                object["operator"].as_str(),
                Some(
                    "+" | "-"
                        | "*"
                        | "/"
                        | "%"
                        | "=="
                        | "!="
                        | "<"
                        | "<="
                        | ">"
                        | ">="
                        | "and"
                        | "or"
                )
            ) {
                bail!("unsupported ABM binary operator");
            }
            validate_expression(&object["left"])?;
            validate_expression(&object["right"])?;
        }
        "unary" => {
            exact(&["op", "operator", "value"])?;
            if !matches!(object["operator"].as_str(), Some("not" | "neg")) {
                bail!("unsupported ABM unary operator");
            }
            validate_expression(&object["value"])?;
        }
        "count" => {
            exact(&["op", "source", "agent_kind", "neighborhood", "where"])?;
            let source = object["source"].as_str();
            if !matches!(
                source,
                Some("agents" | "agents_here" | "patches" | "neighbors")
            ) {
                bail!("unknown ABM count source");
            }
            if !object["agent_kind"].is_null() {
                identifier(
                    object["agent_kind"].as_str().unwrap_or_default(),
                    "expression.agent_kind",
                )?;
            }
            if source == Some("neighbors") {
                if !matches!(
                    object["neighborhood"].as_str(),
                    Some("moore" | "von_neumann")
                ) {
                    bail!("unsupported ABM count neighborhood");
                }
            } else if !object["neighborhood"].is_null() {
                bail!("ABM count neighborhood only applies to neighbors");
            }
            if !object["where"].is_null() {
                validate_expression(&object["where"])?;
            }
        }
        "random" => {
            exact(&["op", "distribution", "address", "args"])?;
            if !matches!(
                object["distribution"].as_str(),
                Some("uniform" | "integer" | "bernoulli" | "choice")
            ) {
                bail!("unsupported ABM random distribution");
            }
            identifier(
                object["address"].as_str().unwrap_or_default(),
                "expression.address",
            )?;
            let arguments = object["args"]
                .as_array()
                .context("ABM random args must be an array")?;
            let expected = match object["distribution"].as_str().unwrap() {
                "uniform" | "integer" => 2,
                "bernoulli" | "choice" => 1,
                _ => unreachable!(),
            };
            if arguments.len() != expected {
                bail!("ABM random distribution has invalid argument count");
            }
            for argument in arguments {
                validate_expression(argument)?;
            }
            if matches!(object["distribution"].as_str(), Some("uniform"))
                && arguments.iter().all(Value::is_number)
            {
                let low = finite_number(&arguments[0], "uniform low")?;
                let high = finite_number(&arguments[1], "uniform high")?;
                if low >= high {
                    bail!("uniform random requires increasing bounds");
                }
            }
            if matches!(object["distribution"].as_str(), Some("integer"))
                && arguments.iter().all(|argument| argument.as_i64().is_some())
            {
                let low = arguments[0].as_i64().unwrap();
                let high = arguments[1].as_i64().unwrap();
                if high <= low || high.checked_sub(low).is_none() {
                    bail!("integer random requires representable increasing bounds");
                }
            }
        }
        _ => bail!("unknown ABM expression operation {op:?}"),
    }
    Ok(())
}

fn identifier(value: &str, path: &str) -> Result<()> {
    if value.is_empty() {
        bail!("{path} must be a non-empty stable business ID");
    }
    Ok(())
}

fn finite_number(value: &Value, path: &str) -> Result<f64> {
    let value = value
        .as_f64()
        .with_context(|| format!("{path} must be a finite number"))?;
    if !value.is_finite() {
        bail!("{path} must be a finite number");
    }
    Ok(value)
}

fn finite_json(value: &Value) -> Result<()> {
    match value {
        Value::Null | Value::Bool(_) | Value::String(_) => Ok(()),
        Value::Number(number) if number.as_u64().is_some() && number.as_i64().is_none() => {
            bail!("ABM integer is outside signed i64 range")
        }
        Value::Number(number) if number.as_f64().is_some_and(f64::is_finite) => Ok(()),
        Value::Number(_) => bail!("ABM value contains a non-finite number"),
        Value::Array(items) => {
            for item in items {
                finite_json(item)?;
            }
            Ok(())
        }
        Value::Object(items) => {
            for item in items.values() {
                finite_json(item)?;
            }
            Ok(())
        }
    }
}

fn validate_json_map(values: &BTreeMap<String, Value>, path: &str) -> Result<()> {
    for value in values.values() {
        finite_json(value).with_context(|| format!("invalid JSON value at {path}"))?;
    }
    Ok(())
}

fn digest(value: &Value) -> Result<String> {
    let canonical = ExecutionPlan::python_canonical(value)?;
    Ok(format!("{:x}", Sha256::digest(canonical.as_bytes())))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_raw() -> Value {
        let payload = json!({
            "model_id": "fire-micro",
            "profile": ABM_PROFILE,
            "topology": {"kind": "finite", "width": 1, "height": 1},
            "initial_state": {
                "globals": {},
                "patches": [{"id": "p0", "x": 0, "y": 0, "vars": {"burning": true}}],
                "agents": []
            },
            "phases": [{
                "id": "spread", "target": "patches", "agent_kind": null,
                "read_view": "phase_start", "commit_mode": "buffered",
                "traversal": "stable", "random_address": null,
                "operations": [{"op": "set", "guard": true, "target": "self", "field": "burning", "value": false}]
            }],
            "stop_conditions": [],
            "metrics": [{"id": "burning", "reducer": "count", "source": "patches", "field": null, "where": {"op": "get", "scope": "self", "field": "burning"}, "expression": null}],
            "max_ticks": 1
        });
        let fingerprint =
            digest(&json!({"version": ABM_PLAN_VERSION, "payload": payload})).unwrap();
        json!({"version": ABM_PLAN_VERSION, "fingerprint": fingerprint, "payload": payload})
    }

    #[test]
    fn loads_valid_checksum_protected_plan() {
        let raw = serde_json::to_vec(&valid_raw()).unwrap();
        let plan = AbmPlanEnvelope::from_slice(&raw).unwrap();
        assert_eq!(plan.payload.model_id, "fire-micro");
    }

    #[test]
    fn rejects_unknown_field_before_execution() {
        let mut raw = valid_raw();
        raw["payload"]["phases"][0]["operations"][0]["surprise"] = json!(true);
        let fingerprint = digest(&json!({
            "version": ABM_PLAN_VERSION,
            "payload": raw["payload"].clone()
        }))
        .unwrap();
        raw["fingerprint"] = json!(fingerprint);
        let error = AbmPlanEnvelope::from_slice(&serde_json::to_vec(&raw).unwrap()).unwrap_err();
        assert!(error.to_string().contains("invalid ABM Plan structure"));
    }

    #[test]
    fn rejects_tampered_fingerprint_before_execution() {
        let mut raw = valid_raw();
        raw["payload"]["max_ticks"] = json!(2);
        let error = AbmPlanEnvelope::from_slice(&serde_json::to_vec(&raw).unwrap()).unwrap_err();
        assert!(error.to_string().contains("fingerprint mismatch"));
    }

    #[test]
    fn rejects_oversized_grid_before_materializing_coordinates() {
        let mut raw = valid_raw();
        raw["payload"]["topology"] = json!({"kind":"finite","width":1_000_001,"height":1});
        raw["payload"]["initial_state"]["patches"] = json!([]);
        raw["fingerprint"] = json!(
            digest(&json!({
                "version": ABM_PLAN_VERSION,
                "payload": raw["payload"].clone()
            }))
            .unwrap()
        );
        let error = AbmPlanEnvelope::from_slice(&serde_json::to_vec(&raw).unwrap()).unwrap_err();
        assert!(error.to_string().contains("executable limit"));
    }
}
