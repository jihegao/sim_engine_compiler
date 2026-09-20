use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

pub const PLAN_VERSION: &str = "aircraft-support-plan/v1alpha2";

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
pub struct ExecutionPlan {
    pub plan_version: String,
    pub domain: String,
    pub semantic_profile: String,
    pub work_policy: String,
    pub rng_profile: String,
    pub source_inputs_sha256: String,
    pub duration_minutes: i64,
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
        if self.semantic_profile != "legacy-minute-v1" {
            bail!("unsupported time profile {:?}", self.semantic_profile);
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
        let encoded = Self::python_canonical(raw)?;
        Ok(format!("{:x}", Sha256::digest(encoded)))
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
