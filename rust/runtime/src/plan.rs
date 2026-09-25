use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub const PLAN_VERSION: &str = "aircraft-support-plan/v1alpha2";
pub const EVENT_TIME_V2_PHASES: [&str; 15] = [
    "transport_arrivals",
    "mission_returns",
    "job_progress_and_completions",
    "failures",
    "operations_postflight_before_preparation",
    "preventive_generation",
    "preflight_generation",
    "resource_dispatch",
    "mission_dispatch",
    "operations_postflight_after_dispatch",
    "mission_success",
    "daily_readiness",
    "operational_availability",
    "downtime",
    "stop",
];

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AircraftSpec {
    pub index: usize,
    pub tail_number: String,
    pub aircraft_type: String,
    pub model: String,
    pub initial_state: String,
    #[serde(default)]
    pub airport: String,
    #[serde(default)]
    pub airport_id: String,
    #[serde(default)]
    pub initial_calendar_days: i64,
    #[serde(default)]
    pub initial_flight_hours: f64,
    #[serde(default)]
    pub initial_cycles: i64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct MissionSpec {
    pub index: usize,
    pub mission_id: String,
    pub name: String,
    pub planned_start: i64,
    pub preparation_start: i64,
    pub duration_minutes: i64,
    pub required_aircraft: usize,
    pub min_required_aircraft: usize,
    pub priority: i64,
    pub cancel_minutes: i64,
    pub success_point: f64,
    pub required_aircraft_type: String,
    pub operations_plan_group_id: String,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct WorkStepSpec {
    pub index: usize,
    pub code: String,
    pub duration_minutes: i64,
    pub personnel: i64,
    pub equipment: i64,
    #[serde(default)]
    pub spares: Vec<(String, i64)>,
    #[serde(default)]
    pub predecessors: Vec<usize>,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ActivitySpec {
    pub index: usize,
    pub activity_id: String,
    pub name: String,
    pub phase: String,
    pub plan_group_id: String,
    pub aircraft_model: String,
    pub resource_node_index: usize,
    pub priority: i64,
    pub kind: String,
    pub equipment_component_index: i64,
    #[serde(default)]
    pub maintenance_methods: Vec<String>,
    #[serde(default)]
    pub replacement_ratio: f64,
    #[serde(default)]
    pub steps: Vec<WorkStepSpec>,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ResourceNodeSpec {
    pub index: usize,
    pub node_id: String,
    pub personnel_capacity: i64,
    pub equipment_capacity: i64,
    #[serde(default)]
    pub inventory: Vec<(String, i64)>,
    pub organization_node_id: String,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ComponentSpec {
    pub index: usize,
    pub component_id: String,
    pub name: String,
    pub parent_index: i64,
    #[serde(default)]
    pub aircraft_indexes: Vec<usize>,
    pub product_id: String,
    pub product_type: String,
    pub quantity: usize,
    pub failure_rate_per_hour: f64,
    pub failure_threshold: usize,
    pub repair_activity_index: i64,
    pub repair_duration_minutes: i64,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct PreventiveCycleSpec {
    pub index: usize,
    pub aircraft_index: usize,
    pub activity_index: usize,
    pub calendar_days: i64,
    pub flight_hours: f64,
    pub landing_cycles: i64,
    pub initial_calendar_days: i64,
    pub initial_flight_hours: f64,
    pub initial_landing_cycles: i64,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct SupplyRouteSpec {
    pub index: usize,
    pub route_id: String,
    pub source_node_index: usize,
    pub destination_node_index: usize,
    pub product_id: String,
    pub capacity: i64,
    pub transport_minutes: i64,
    pub supply_mode: String,
    pub relation_id: String,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ResourceDispatchCandidate {
    pub activity_index: usize,
    pub step_index: usize,
    pub activity_id: String,
    pub step_code: String,
    pub source_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub product_filter: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ResourceDispatchKey {
    pub kind: String,
    pub node_index: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub product_id: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ResourceDispatchDependency {
    pub key: ResourceDispatchKey,
    pub candidates: Vec<ResourceDispatchCandidate>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ResourceDispatchIndex {
    pub schema_version: String,
    pub mlir_version: String,
    pub pass_name: String,
    pub base_plan_fingerprint: String,
    pub candidate_rule_count: usize,
    pub dependencies: Vec<ResourceDispatchDependency>,
    pub checksum: String,
}

type DispatchCandidateKey = (usize, usize, String, String, String, Option<String>);
type DispatchDependencyKey = (String, usize, Option<String>);

fn dispatch_candidate_key(candidate: &ResourceDispatchCandidate) -> DispatchCandidateKey {
    (
        candidate.activity_index,
        candidate.step_index,
        candidate.activity_id.clone(),
        candidate.step_code.clone(),
        candidate.source_path.clone(),
        candidate.product_filter.clone(),
    )
}

fn add_expected_candidate(
    expected: &mut BTreeMap<DispatchDependencyKey, BTreeSet<DispatchCandidateKey>>,
    kind: &str,
    node: usize,
    product: Option<String>,
    candidate: DispatchCandidateKey,
) {
    expected
        .entry((kind.to_owned(), node, product))
        .or_default()
        .insert(candidate);
}

fn add_expected_inventory(
    expected: &mut BTreeMap<DispatchDependencyKey, BTreeSet<DispatchCandidateKey>>,
    routes: &[SupplyRouteSpec],
    node: usize,
    product: &str,
    candidate: DispatchCandidateKey,
) {
    add_expected_candidate(
        expected,
        "inventory",
        node,
        Some(product.to_owned()),
        candidate.clone(),
    );
    for route in routes {
        if route.destination_node_index == node
            && (route.product_id.is_empty() || route.product_id == product)
        {
            add_expected_candidate(
                expected,
                "inventory",
                route.source_node_index,
                Some(product.to_owned()),
                candidate.clone(),
            );
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ExecutionPlan {
    pub plan_version: String,
    pub domain: String,
    pub semantic_profile: String,
    pub work_policy: String,
    pub rng_profile: String,
    pub source_inputs_sha256: String,
    pub duration_minutes: i64,
    #[serde(default)]
    pub natural_completion_enabled: bool,
    pub phases: Vec<String>,
    #[serde(default)]
    pub aircraft: Vec<AircraftSpec>,
    #[serde(default)]
    pub missions: Vec<MissionSpec>,
    #[serde(default)]
    pub activities: Vec<ActivitySpec>,
    #[serde(default)]
    pub resource_nodes: Vec<ResourceNodeSpec>,
    #[serde(default)]
    pub components: Vec<ComponentSpec>,
    #[serde(default)]
    pub preventive_cycles: Vec<PreventiveCycleSpec>,
    #[serde(default)]
    pub supply_routes: Vec<SupplyRouteSpec>,
    #[serde(default)]
    pub unsupported_features: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub resource_dispatch_index: Option<ResourceDispatchIndex>,
}

impl ExecutionPlan {
    pub fn from_slice(bytes: &[u8]) -> Result<(Self, Value)> {
        let raw: Value = serde_json::from_slice(bytes)?;
        let plan: Self = serde_json::from_value(raw.clone())?;
        plan.validate()?;
        Ok((plan, raw))
    }

    pub fn validate(&self) -> Result<()> {
        if self.plan_version != PLAN_VERSION {
            bail!("unsupported plan version {:?}", self.plan_version);
        }
        if !matches!(
            self.semantic_profile.as_str(),
            "legacy-minute-v1" | "event-time-v2"
        ) {
            bail!("unsupported time profile {:?}", self.semantic_profile);
        }
        if self.semantic_profile == "event-time-v2"
            && !self
                .phases
                .iter()
                .map(String::as_str)
                .eq(EVENT_TIME_V2_PHASES)
        {
            bail!(
                "event-time-v2 requires the canonical legacy phase order; got {:?}",
                self.phases
            );
        }
        if self.work_policy != "stable-topological-serial" {
            bail!("unsupported work policy {:?}", self.work_policy);
        }
        if self.rng_profile != "legacy-sequential-v1" {
            bail!("unsupported RNG profile {:?}", self.rng_profile);
        }
        if !self.unsupported_features.is_empty() {
            bail!(
                "unsupported plan capabilities: {}",
                self.unsupported_features.join(", ")
            );
        }
        self.validate_resource_dispatch_index()?;
        for (position, aircraft) in self.aircraft.iter().enumerate() {
            if aircraft.index != position {
                bail!(
                    "aircraft index {:?} does not match position {position}",
                    aircraft.index
                );
            }
        }
        for (position, mission) in self.missions.iter().enumerate() {
            if mission.index != position {
                bail!(
                    "mission index {:?} does not match position {position}",
                    mission.index
                );
            }
        }
        for (position, activity) in self.activities.iter().enumerate() {
            if activity.index != position {
                bail!(
                    "activity index {:?} does not match position {position}",
                    activity.index
                );
            }
            if activity.resource_node_index >= self.resource_nodes.len() {
                bail!(
                    "activity {:?} references invalid resource node index {:?}",
                    activity.activity_id,
                    activity.resource_node_index
                );
            }
            if activity.equipment_component_index < -1
                || activity.equipment_component_index >= self.components.len() as i64
            {
                bail!(
                    "activity {:?} references invalid equipment component index {:?}",
                    activity.activity_id,
                    activity.equipment_component_index
                );
            }
            for (step_position, step) in activity.steps.iter().enumerate() {
                if step.index != step_position {
                    bail!(
                        "activity {:?} step index {:?} does not match position {step_position}",
                        activity.activity_id,
                        step.index
                    );
                }
            }
        }
        for (position, node) in self.resource_nodes.iter().enumerate() {
            if node.index != position {
                bail!(
                    "resource node index {:?} does not match position {position}",
                    node.index
                );
            }
        }
        for (position, component) in self.components.iter().enumerate() {
            if component.index != position {
                bail!(
                    "component index {:?} does not match position {position}",
                    component.index
                );
            }
            if component.parent_index < -1 || component.parent_index >= self.components.len() as i64
            {
                bail!(
                    "component {:?} references invalid parent index {:?}",
                    component.component_id,
                    component.parent_index
                );
            }
            if component.repair_activity_index < -1
                || component.repair_activity_index >= self.activities.len() as i64
            {
                bail!(
                    "component {:?} references invalid repair activity index {:?}",
                    component.component_id,
                    component.repair_activity_index
                );
            }
            if let Some(aircraft_index) = component
                .aircraft_indexes
                .iter()
                .find(|aircraft_index| **aircraft_index >= self.aircraft.len())
            {
                bail!(
                    "component {:?} references invalid aircraft index {:?}",
                    component.component_id,
                    aircraft_index
                );
            }
        }
        for (position, cycle) in self.preventive_cycles.iter().enumerate() {
            if cycle.index != position {
                bail!(
                    "preventive cycle index {:?} does not match position {position}",
                    cycle.index
                );
            }
            if cycle.aircraft_index >= self.aircraft.len() {
                bail!(
                    "preventive cycle {position} references invalid aircraft index {:?}",
                    cycle.aircraft_index
                );
            }
            if cycle.activity_index >= self.activities.len() {
                bail!(
                    "preventive cycle {position} references invalid activity index {:?}",
                    cycle.activity_index
                );
            }
        }
        for (position, route) in self.supply_routes.iter().enumerate() {
            if route.index != position {
                bail!(
                    "supply route index {:?} does not match position {position}",
                    route.index
                );
            }
            if route.source_node_index >= self.resource_nodes.len()
                || route.destination_node_index >= self.resource_nodes.len()
            {
                bail!(
                    "supply route {:?} references invalid node indexes {:?} -> {:?}",
                    route.route_id,
                    route.source_node_index,
                    route.destination_node_index
                );
            }
        }
        Ok(())
    }

    pub fn fingerprint(raw: &Value) -> Result<String> {
        let mut semantic_plan = raw.clone();
        if let Some(object) = semantic_plan.as_object_mut() {
            object.remove("resource_dispatch_index");
        }
        let encoded = Self::python_canonical(&semantic_plan)?;
        Ok(format!("{:x}", Sha256::digest(encoded)))
    }

    fn validate_resource_dispatch_index(&self) -> Result<()> {
        let Some(index) = &self.resource_dispatch_index else {
            return Ok(());
        };
        if !matches!(
            index.schema_version.as_str(),
            "resource-dispatch-index/v1" | "resource-dispatch-index/v2"
        ) || index.pass_name != "sim-build-resource-dependency-index"
            || index.mlir_version != "23.1.1"
        {
            bail!("unsupported resource dispatch index contract");
        }
        let mut semantic_plan = serde_json::to_value(self)?;
        semantic_plan
            .as_object_mut()
            .expect("serialized execution plan is an object")
            .remove("resource_dispatch_index");
        let base_fingerprint = Self::fingerprint(&semantic_plan)?;
        if index.base_plan_fingerprint != base_fingerprint {
            bail!("resource dispatch index was compiled for a different base plan");
        }
        let mut checksum_value = serde_json::to_value(index)?;
        checksum_value
            .as_object_mut()
            .expect("serialized resource dispatch index is an object")
            .remove("checksum");
        let checksum_body = Self::python_canonical(&checksum_value)?;
        let checksum = format!("{:x}", Sha256::digest(checksum_body));
        if index.checksum != checksum {
            bail!("resource dispatch index checksum mismatch");
        }

        let mut actual: BTreeMap<DispatchDependencyKey, BTreeSet<DispatchCandidateKey>> =
            BTreeMap::new();
        let mut actual_count = 0usize;
        for dependency in &index.dependencies {
            let key = &dependency.key;
            if key.node_index >= self.resource_nodes.len() {
                bail!("resource dispatch index references an invalid resource node");
            }
            match key.kind.as_str() {
                "personnel_capacity" | "equipment_capacity" if key.product_id.is_none() => {}
                "inventory"
                    if key
                        .product_id
                        .as_ref()
                        .is_some_and(|value| !value.is_empty()) => {}
                _ => bail!("resource dispatch index has an unsupported resource key"),
            }
            let entry = actual
                .entry((key.kind.clone(), key.node_index, key.product_id.clone()))
                .or_default();
            for candidate in &dependency.candidates {
                let Some(activity) = self.activities.get(candidate.activity_index) else {
                    bail!("resource dispatch index references an invalid activity");
                };
                let Some(step) = activity.steps.get(candidate.step_index) else {
                    bail!("resource dispatch index references an invalid work step");
                };
                let inventory_route_matches = key.kind == "inventory"
                    && self.supply_routes.iter().any(|route| {
                        route.destination_node_index == activity.resource_node_index
                            && route.source_node_index == key.node_index
                            && (route.product_id.is_empty()
                                || Some(route.product_id.as_str()) == key.product_id.as_deref())
                    });
                let capacity_route_matches = index.schema_version == "resource-dispatch-index/v2"
                    && matches!(
                        key.kind.as_str(),
                        "personnel_capacity" | "equipment_capacity"
                    )
                    && self.supply_routes.iter().any(|route| {
                        route.destination_node_index == activity.resource_node_index
                            && route.source_node_index == key.node_index
                            && (matches!(route.product_id.as_str(), "" | "*")
                                || (key.kind == "personnel_capacity"
                                    && route.product_id == "personnel")
                                || (key.kind == "equipment_capacity"
                                    && route.product_id == "equipment"))
                    });
                if activity.activity_id != candidate.activity_id
                    || step.code != candidate.step_code
                    || step.source_path != candidate.source_path
                    || (activity.resource_node_index != key.node_index
                        && !inventory_route_matches
                        && !capacity_route_matches)
                {
                    bail!("resource dispatch index candidate identity does not match the plan");
                }
                if let Some(product_filter) = &candidate.product_filter
                    && (key.kind != "inventory"
                        || key.product_id.as_deref() != Some(product_filter.as_str())
                        || !self.components.iter().any(|component| {
                            component.repair_activity_index == activity.index as i64
                                && component.product_type.trim().eq_ignore_ascii_case("LRU")
                                && component.product_id == *product_filter
                        }))
                {
                    bail!("resource dispatch index has an invalid dynamic spare filter");
                }
                if !entry.insert(dispatch_candidate_key(candidate)) {
                    bail!("resource dispatch index contains a duplicate candidate rule");
                }
                actual_count += 1;
            }
        }
        if actual_count != index.candidate_rule_count {
            bail!("resource dispatch index candidate count mismatch");
        }

        let mut expected: BTreeMap<DispatchDependencyKey, BTreeSet<DispatchCandidateKey>> =
            BTreeMap::new();
        for activity in &self.activities {
            for step in &activity.steps {
                let candidate = (
                    activity.index,
                    step.index,
                    activity.activity_id.clone(),
                    step.code.clone(),
                    step.source_path.clone(),
                    None,
                );
                if step.personnel > 0 {
                    add_expected_candidate(
                        &mut expected,
                        "personnel_capacity",
                        activity.resource_node_index,
                        None,
                        candidate.clone(),
                    );
                }
                if step.equipment > 0 {
                    add_expected_candidate(
                        &mut expected,
                        "equipment_capacity",
                        activity.resource_node_index,
                        None,
                        candidate.clone(),
                    );
                }
                if index.schema_version == "resource-dispatch-index/v2" {
                    for route in &self.supply_routes {
                        if route.destination_node_index != activity.resource_node_index {
                            continue;
                        }
                        for (quantity, kind, product) in [
                            (step.personnel, "personnel_capacity", "personnel"),
                            (step.equipment, "equipment_capacity", "equipment"),
                        ] {
                            if quantity > 0
                                && (matches!(route.product_id.as_str(), "" | "*")
                                    || route.product_id == product)
                            {
                                add_expected_candidate(
                                    &mut expected,
                                    kind,
                                    route.source_node_index,
                                    None,
                                    candidate.clone(),
                                );
                            }
                        }
                    }
                }
                for (product, quantity) in &step.spares {
                    if *quantity > 0 && !product.is_empty() {
                        add_expected_inventory(
                            &mut expected,
                            &self.supply_routes,
                            activity.resource_node_index,
                            product,
                            candidate.clone(),
                        );
                    }
                }
            }
        }
        for component in &self.components {
            if !component.product_type.trim().eq_ignore_ascii_case("LRU")
                || component.product_id.is_empty()
                || component.repair_activity_index < 0
            {
                continue;
            }
            let activity_index = component.repair_activity_index as usize;
            let Some(activity) = self.activities.get(activity_index) else {
                continue;
            };
            let permits_replacement = activity
                .maintenance_methods
                .iter()
                .any(|method| method == "replacement");
            let effective_ratio = if activity.maintenance_methods.len() == 1
                && activity.maintenance_methods[0] == "replacement"
            {
                1.0
            } else if permits_replacement {
                activity.replacement_ratio
            } else {
                0.0
            };
            if activity.steps.is_empty()
                || activity.steps.iter().any(|step| !step.spares.is_empty())
                || !permits_replacement
                || effective_ratio <= 0.0
            {
                continue;
            }
            let step = activity.steps.last().expect("non-empty activity");
            let candidate = (
                activity.index,
                step.index,
                activity.activity_id.clone(),
                step.code.clone(),
                step.source_path.clone(),
                Some(component.product_id.clone()),
            );
            add_expected_inventory(
                &mut expected,
                &self.supply_routes,
                activity.resource_node_index,
                &component.product_id,
                candidate,
            );
        }
        for (key, candidates) in expected {
            let Some(actual_candidates) = actual.get(&key) else {
                bail!("resource dispatch index omits a required resource dependency");
            };
            if !candidates.is_subset(actual_candidates) {
                bail!("resource dispatch index omits a required candidate rule");
            }
        }
        Ok(())
    }

    pub fn python_canonical(raw: &Value) -> Result<String> {
        let mut encoded = String::new();
        write_python_canonical(raw, &mut encoded)?;
        Ok(encoded)
    }
}

fn write_python_canonical(value: &Value, output: &mut String) -> Result<()> {
    match value {
        Value::Null => output.push_str("null"),
        Value::Bool(item) => output.push_str(if *item { "true" } else { "false" }),
        Value::Number(item) => {
            if let Some(value) = item.as_i64() {
                output.push_str(&value.to_string());
            } else if let Some(value) = item.as_u64() {
                output.push_str(&value.to_string());
            } else if let Some(value) = item.as_f64() {
                output.push_str(&python_float_repr(value));
            } else {
                bail!("unsupported JSON number {item}");
            }
        }
        Value::String(item) => output.push_str(&serde_json::to_string(item)?),
        Value::Array(items) => {
            output.push('[');
            for (index, item) in items.iter().enumerate() {
                if index != 0 {
                    output.push(',');
                }
                write_python_canonical(item, output)?;
            }
            output.push(']');
        }
        Value::Object(items) => {
            output.push('{');
            for (index, (key, item)) in items.iter().enumerate() {
                if index != 0 {
                    output.push(',');
                }
                output.push_str(&serde_json::to_string(key)?);
                output.push(':');
                write_python_canonical(item, output)?;
            }
            output.push('}');
        }
    }
    Ok(())
}

fn python_float_repr(value: f64) -> String {
    let raw = ryu::Buffer::new().format_finite(value).to_string();
    let (sign, unsigned) = raw
        .strip_prefix('-')
        .map_or(("", raw.as_str()), |item| ("-", item));
    let (mantissa, explicit_exponent) = unsigned
        .split_once(['e', 'E'])
        .map_or((unsigned, None), |(left, right)| {
            (left, Some(right.parse::<i32>().unwrap()))
        });
    let mut digits: String = mantissa.chars().filter(|item| *item != '.').collect();
    let exponent = if let Some(exponent) = explicit_exponent {
        exponent
    } else if let Some(dot) = mantissa.find('.') {
        let integer = &mantissa[..dot];
        if integer != "0" {
            integer.trim_start_matches('0').len() as i32 - 1
        } else {
            let fraction = &mantissa[dot + 1..];
            -(fraction.chars().take_while(|item| *item == '0').count() as i32) - 1
        }
    } else {
        mantissa.trim_start_matches('0').len() as i32 - 1
    };
    digits = digits.trim_start_matches('0').to_string();
    if digits.is_empty() {
        return format!("{sign}0.0");
    }
    if !(-4..16).contains(&exponent) {
        while digits.len() > 1 && digits.ends_with('0') {
            digits.pop();
        }
        let mut rendered = String::new();
        rendered.push_str(sign);
        rendered.push(digits.as_bytes()[0] as char);
        if digits.len() > 1 {
            rendered.push('.');
            rendered.push_str(&digits[1..]);
        }
        rendered.push('e');
        rendered.push(if exponent >= 0 { '+' } else { '-' });
        rendered.push_str(&format!("{:02}", exponent.unsigned_abs()));
        rendered
    } else {
        let decimal_position = exponent + 1;
        let body = if decimal_position <= 0 {
            format!("0.{}{}", "0".repeat((-decimal_position) as usize), digits)
        } else if decimal_position as usize >= digits.len() {
            format!(
                "{}{}.0",
                digits,
                "0".repeat(decimal_position as usize - digits.len())
            )
        } else {
            let position = decimal_position as usize;
            format!("{}.{}", &digits[..position], &digits[position..])
        };
        format!("{sign}{body}")
    }
}

#[cfg(test)]
mod fingerprint_tests {
    use super::{ExecutionPlan, python_float_repr};

    fn failure_plan() -> ExecutionPlan {
        let bytes = include_bytes!(
            "../../../tests/fixtures/synthetic/b2-failure-repair-execution-plan.json"
        );
        ExecutionPlan::from_slice(bytes).unwrap().0
    }

    #[test]
    fn formats_like_python_repr() {
        for (value, expected) in [
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1_000_000_000_000_000.0, "1000000000000000.0"),
            (10_000_000_000_000_000.0, "1e+16"),
            (-0.0, "-0.0"),
        ] {
            assert_eq!(python_float_repr(value), expected);
        }
    }

    #[test]
    fn rejects_non_dense_component_indexes() {
        let mut plan = failure_plan();
        plan.components[1].index = 7;
        let error = plan.validate().unwrap_err();
        assert!(error.to_string().contains("does not match position"));
    }

    #[test]
    fn rejects_invalid_component_aircraft_references() {
        let mut plan = failure_plan();
        plan.components[1].aircraft_indexes = vec![plan.aircraft.len()];
        let error = plan.validate().unwrap_err();
        assert!(error.to_string().contains("invalid aircraft index"));
    }
}
