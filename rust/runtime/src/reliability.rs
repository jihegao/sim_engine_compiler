use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{HashMap, HashSet};

pub const RELIABILITY_POLICY: &str = "instance-redundancy/v1";
pub const RELIABILITY_PLAN_VERSION: &str = "aircraft-support-plan/v1alpha2";

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ReliabilityComponentGroupSpec {
    pub index: usize,
    pub group_id: String,
    pub component_type_id: String,
    pub name: String,
    pub parent_group_index: i64,
    pub aircraft_indexes: Vec<usize>,
    pub quantity: usize,
    pub redundancy_kind: String,
    pub redundancy_k: usize,
    pub redundancy_n: usize,
    pub repair_activity_index: i64,
    pub repair_duration_minutes: i64,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ReliabilityComponentInstanceSpec {
    pub index: usize,
    pub instance_template_id: String,
    pub group_index: usize,
    pub parent_instance_index: i64,
    pub failure_rate_per_hour: f64,
    pub repair_activity_index: i64,
    pub repair_duration_minutes: i64,
    pub source_path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ReliabilityExecutionPlan {
    pub plan_version: String,
    pub domain: String,
    pub semantic_profile: String,
    pub work_policy: String,
    pub rng_profile: String,
    pub reliability_policy: String,
    pub source_inputs_sha256: String,
    pub duration_minutes: i64,
    pub aircraft_ids: Vec<String>,
    pub component_groups: Vec<ReliabilityComponentGroupSpec>,
    pub component_instances: Vec<ReliabilityComponentInstanceSpec>,
}

#[derive(Clone, Debug)]
pub struct ReliabilityComponentInstanceState {
    pub runtime_instance_id: String,
    pub aircraft_index: usize,
    pub aircraft_id: String,
    pub instance_template_id: String,
    pub group_index: usize,
    pub parent_instance_index: Option<usize>,
    pub remaining_exposure: f64,
    pub failed: bool,
    pub failed_at: Option<i64>,
    pub repairing: bool,
    pub repair_remaining: i64,
    pub exposure_paused: bool,
}

impl ReliabilityComponentInstanceState {
    pub fn healthy(&self) -> bool {
        !self.failed && !self.repairing
    }
}

pub(crate) fn reject_failure_threshold(value: &Value, path: &str) -> Result<()> {
    match value {
        Value::Object(map) => {
            if map.contains_key("failure_threshold") {
                bail!("failure_threshold_in_new_plan at {path}.failure_threshold");
            }
            for (key, child) in map {
                reject_failure_threshold(child, &format!("{path}.{key}"))?;
            }
        }
        Value::Array(items) => {
            for (index, child) in items.iter().enumerate() {
                reject_failure_threshold(child, &format!("{path}[{index}]"))?;
            }
        }
        _ => {}
    }
    Ok(())
}

impl ReliabilityExecutionPlan {
    pub fn from_slice(bytes: &[u8]) -> Result<Self> {
        let raw: Value = serde_json::from_slice(bytes)?;
        reject_failure_threshold(&raw, "$")?;
        let plan: Self = serde_json::from_value(raw)?;
        plan.validate()?;
        Ok(plan)
    }

    pub fn validate(&self) -> Result<()> {
        if self.plan_version != RELIABILITY_PLAN_VERSION {
            bail!("unsupported_plan_version");
        }
        if self.reliability_policy != RELIABILITY_POLICY {
            bail!("unsupported_reliability_policy");
        }
        if self.domain != "aircraft-support" {
            bail!("unsupported_domain");
        }
        if self.semantic_profile != "legacy-minute-v1" && self.semantic_profile != "event-time-v2" {
            bail!("unsupported_semantic_profile");
        }
        if self.work_policy != "stable-topological-serial" {
            bail!("unsupported_work_policy");
        }
        if self.rng_profile != "legacy-sequential-v1" {
            bail!("unsupported_rng_profile");
        }
        if self.source_inputs_sha256.len() != 64
            || !self
                .source_inputs_sha256
                .bytes()
                .all(|value| value.is_ascii_hexdigit() && !value.is_ascii_uppercase())
        {
            bail!("invalid_source_fingerprint");
        }
        if self.duration_minutes < 0 {
            bail!("invalid_duration");
        }
        if self.aircraft_ids.is_empty()
            || self.aircraft_ids.iter().any(|value| value.is_empty())
            || self.aircraft_ids.iter().collect::<HashSet<_>>().len() != self.aircraft_ids.len()
        {
            bail!("invalid_aircraft_ids");
        }

        let mut group_ids = HashSet::new();
        for (position, group) in self.component_groups.iter().enumerate() {
            if group.index != position {
                bail!("invalid_group_index");
            }
            if group.group_id.is_empty() || !group_ids.insert(group.group_id.clone()) {
                bail!("duplicate_component_group_id");
            }
            if group.component_type_id.is_empty() {
                bail!("component_type_missing");
            }
            if group.quantity == 0 {
                bail!("invalid_quantity");
            }
            if group.redundancy_kind != "series" && group.redundancy_kind != "k_out_of_n" {
                bail!("invalid_redundancy_kind");
            }
            if group.redundancy_n != group.quantity {
                bail!("redundancy_n_mismatch");
            }
            match group.redundancy_kind.as_str() {
                "series" if group.redundancy_k != 0 => bail!("redundancy_k_on_series"),
                "k_out_of_n" => {
                    let k = group.redundancy_k;
                    if k == 0 || k > group.redundancy_n {
                        bail!("invalid_redundancy_k");
                    }
                }
                _ => {}
            }
            if group.parent_group_index < -1
                || group.parent_group_index >= self.component_groups.len() as i64
            {
                bail!("unknown_parent_group");
            }
            if group.repair_activity_index < -1 {
                bail!("invalid_repair_activity");
            }
            if group.repair_duration_minutes < 0 {
                bail!("invalid_repair_duration");
            }
            if group.source_path.is_empty() {
                bail!("missing_source_path");
            }
            let indexes = group
                .aircraft_indexes
                .iter()
                .copied()
                .collect::<HashSet<_>>();
            if indexes.len() != group.aircraft_indexes.len()
                || group
                    .aircraft_indexes
                    .iter()
                    .any(|value| *value >= self.aircraft_ids.len())
            {
                bail!("invalid_aircraft_indexes");
            }
        }

        let mut instance_ids = HashSet::new();
        for (position, instance) in self.component_instances.iter().enumerate() {
            if instance.index != position {
                bail!("invalid_instance_index");
            }
            if instance.instance_template_id.is_empty()
                || !instance_ids.insert(instance.instance_template_id.clone())
            {
                bail!("duplicate_instance_id");
            }
            if instance.group_index >= self.component_groups.len() {
                bail!("unknown_instance_group");
            }
            if !instance.failure_rate_per_hour.is_finite() || instance.failure_rate_per_hour < 0.0 {
                bail!("invalid_failure_rate");
            }
            if instance.repair_activity_index < -1 {
                bail!("invalid_repair_activity");
            }
            if instance.repair_duration_minutes < 0 {
                bail!("invalid_repair_duration");
            }
            if instance.source_path.is_empty() {
                bail!("missing_source_path");
            }
        }

        for (position, group) in self.component_groups.iter().enumerate() {
            let members = self
                .component_instances
                .iter()
                .filter(|instance| instance.group_index == position)
                .collect::<Vec<_>>();
            if members.len() != group.quantity {
                bail!("quantity_instance_mismatch");
            }
            let parents = members
                .iter()
                .map(|instance| instance.parent_instance_index)
                .collect::<HashSet<_>>();
            if parents.len() != 1 {
                bail!("mixed_parent_instance_unsupported");
            }
            let parent = *parents.iter().next().unwrap();
            if group.parent_group_index == -1 {
                if parent != -1 {
                    bail!("parent_instance_mismatch");
                }
            } else {
                if parent < 0 || parent >= self.component_instances.len() as i64 {
                    bail!("ambiguous_parent_instance");
                }
                if self.component_instances[parent as usize].group_index
                    != group.parent_group_index as usize
                {
                    bail!("parent_instance_group_mismatch");
                }
            }
        }

        for start in 0..self.component_groups.len() {
            let mut seen = HashSet::new();
            let mut current = start as i64;
            while current >= 0 {
                if !seen.insert(current) {
                    bail!("cyclic_component_parent");
                }
                current = self.component_groups[current as usize].parent_group_index;
            }
        }
        Ok(())
    }
}

pub fn validate_repair_activity_references(
    groups: &[ReliabilityComponentGroupSpec],
    instances: &[ReliabilityComponentInstanceSpec],
    activity_count: usize,
) -> Result<()> {
    let groups = groups
        .iter()
        .enumerate()
        .map(|(index, row)| ("component_groups", index, row.repair_activity_index));
    let instances = instances
        .iter()
        .enumerate()
        .map(|(index, row)| ("component_instances", index, row.repair_activity_index));
    for (table, index, activity) in groups.chain(instances) {
        if activity >= activity_count as i64 {
            bail!(
                "invalid_repair_activity at {table}[{index}].repair_activity_index: repair activity index {activity} is out of range"
            );
        }
    }
    Ok(())
}

fn children_by_parent_instance(plan: &ReliabilityExecutionPlan) -> Vec<Vec<usize>> {
    let mut result = vec![Vec::new(); plan.component_instances.len()];
    for group in &plan.component_groups {
        if group.parent_group_index < 0 {
            continue;
        }
        let Some(first) = plan
            .component_instances
            .iter()
            .find(|instance| instance.group_index == group.index)
        else {
            continue;
        };
        if first.parent_instance_index >= 0 {
            result[first.parent_instance_index as usize].push(group.index);
        }
    }
    result
}

fn state_by_template<'a>(
    states: &'a [ReliabilityComponentInstanceState],
    aircraft_index: usize,
) -> HashMap<&'a str, &'a ReliabilityComponentInstanceState> {
    states
        .iter()
        .filter(|state| state.aircraft_index == aircraft_index)
        .map(|state| (state.instance_template_id.as_str(), state))
        .collect()
}

fn instance_healthy(
    plan: &ReliabilityExecutionPlan,
    states: &[ReliabilityComponentInstanceState],
    aircraft_index: usize,
    instance_index: usize,
    children: &[Vec<usize>],
    memo: &mut HashMap<(u8, usize), bool>,
) -> bool {
    if let Some(value) = memo.get(&(0, instance_index)) {
        return *value;
    }
    let template = &plan.component_instances[instance_index].instance_template_id;
    let by_template = state_by_template(states, aircraft_index);
    let mut value = by_template
        .get(template.as_str())
        .is_some_and(|state| state.healthy());
    if value {
        for child_group in &children[instance_index] {
            if !group_healthy(plan, states, aircraft_index, *child_group, children, memo) {
                value = false;
                break;
            }
        }
    }
    memo.insert((0, instance_index), value);
    value
}

fn group_healthy(
    plan: &ReliabilityExecutionPlan,
    states: &[ReliabilityComponentInstanceState],
    aircraft_index: usize,
    group_index: usize,
    children: &[Vec<usize>],
    memo: &mut HashMap<(u8, usize), bool>,
) -> bool {
    if let Some(value) = memo.get(&(1, group_index)) {
        return *value;
    }
    let group = &plan.component_groups[group_index];
    let members = plan
        .component_instances
        .iter()
        .filter(|instance| instance.group_index == group_index)
        .map(|instance| instance.index)
        .collect::<Vec<_>>();
    let value = if group.redundancy_kind == "series" {
        members
            .iter()
            .all(|index| instance_healthy(plan, states, aircraft_index, *index, children, memo))
    } else {
        let healthy = members
            .iter()
            .filter(|index| instance_healthy(plan, states, aircraft_index, **index, children, memo))
            .count();
        healthy >= group.redundancy_k
    };
    memo.insert((1, group_index), value);
    value
}

pub fn aircraft_healthy(
    plan: &ReliabilityExecutionPlan,
    states: &[ReliabilityComponentInstanceState],
    aircraft_index: usize,
) -> bool {
    let children = children_by_parent_instance(plan);
    let mut memo = HashMap::new();
    plan.component_groups
        .iter()
        .filter(|group| {
            group.parent_group_index == -1 && group.aircraft_indexes.contains(&aircraft_index)
        })
        .all(|group| {
            group_healthy(
                plan,
                states,
                aircraft_index,
                group.index,
                &children,
                &mut memo,
            )
        })
}

pub fn complete_repair(
    states: &[ReliabilityComponentInstanceState],
    runtime_instance_id: &str,
) -> Result<Vec<ReliabilityComponentInstanceState>> {
    let mut found = false;
    let result = states
        .iter()
        .map(|state| {
            if state.runtime_instance_id == runtime_instance_id {
                found = true;
                let mut repaired = state.clone();
                repaired.failed = false;
                repaired.failed_at = None;
                repaired.repairing = false;
                repaired.repair_remaining = 0;
                repaired.exposure_paused = false;
                repaired
            } else {
                state.clone()
            }
        })
        .collect::<Vec<_>>();
    if !found {
        bail!("repair_target_unknown");
    }
    Ok(result)
}

pub fn runtime_instance_id(aircraft_id: &str, instance_template_id: &str) -> String {
    format!("{aircraft_id}/{instance_template_id}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn plan(value: Value) -> ReliabilityExecutionPlan {
        let raw = serde_json::to_vec(&value).unwrap();
        ReliabilityExecutionPlan::from_slice(&raw).unwrap()
    }

    fn base_plan(groups: Value, instances: Value) -> Value {
        json!({
            "plan_version": RELIABILITY_PLAN_VERSION,
            "domain": "aircraft-support",
            "semantic_profile": "legacy-minute-v1",
            "work_policy": "stable-topological-serial",
            "rng_profile": "legacy-sequential-v1",
            "reliability_policy": RELIABILITY_POLICY,
            "source_inputs_sha256": "0".repeat(64),
            "duration_minutes": 1440,
            "aircraft_ids": ["F35-01"],
            "component_groups": groups,
            "component_instances": instances
        })
    }

    fn state(template: &str, failed: bool) -> ReliabilityComponentInstanceState {
        ReliabilityComponentInstanceState {
            runtime_instance_id: format!("F35-01/{template}"),
            aircraft_index: 0,
            aircraft_id: "F35-01".into(),
            instance_template_id: template.into(),
            group_index: 0,
            parent_instance_index: None,
            remaining_exposure: 10.0,
            failed,
            failed_at: failed.then_some(1),
            repairing: false,
            repair_remaining: 0,
            exposure_paused: false,
        }
    }

    #[test]
    fn series_and_k_out_of_n_health_are_distinct() {
        let series = plan(base_plan(
            json!([{
                "index": 0, "group_id": "A", "component_type_id": "A", "name": "A",
                "parent_group_index": -1, "aircraft_indexes": [0], "quantity": 2,
                "redundancy_kind": "series", "redundancy_k": 0, "redundancy_n": 2,
                "repair_activity_index": -1, "repair_duration_minutes": 0,
                "source_path": "A"
            }]),
            json!([
                {"index": 0, "instance_template_id": "A-0", "group_index": 0,
                 "parent_instance_index": -1, "failure_rate_per_hour": 0.5,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "A-0"},
                {"index": 1, "instance_template_id": "A-1", "group_index": 0,
                 "parent_instance_index": -1, "failure_rate_per_hour": 0.5,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "A-1"}
            ]),
        ));
        assert!(!aircraft_healthy(
            &series,
            &[state("A-0", true), state("A-1", false)],
            0
        ));

        let redundant = plan(base_plan(
            json!([{
                "index": 0, "group_id": "A", "component_type_id": "A", "name": "A",
                "parent_group_index": -1, "aircraft_indexes": [0], "quantity": 2,
                "redundancy_kind": "k_out_of_n", "redundancy_k": 1, "redundancy_n": 2,
                "repair_activity_index": -1, "repair_duration_minutes": 0,
                "source_path": "A"
            }]),
            json!([
                {"index": 0, "instance_template_id": "A-0", "group_index": 0,
                 "parent_instance_index": -1, "failure_rate_per_hour": 0.5,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "A-0"},
                {"index": 1, "instance_template_id": "A-1", "group_index": 0,
                 "parent_instance_index": -1, "failure_rate_per_hour": 0.5,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "A-1"}
            ]),
        ));
        assert!(aircraft_healthy(
            &redundant,
            &[state("A-0", true), state("A-1", false)],
            0
        ));
    }

    #[test]
    fn parent_instance_mapping_and_failure_threshold_rejection_work() {
        let value = base_plan(
            json!([
                {"index": 0, "group_id": "P", "component_type_id": "P", "name": "P",
                 "parent_group_index": -1, "aircraft_indexes": [0], "quantity": 2,
                 "redundancy_kind": "series", "redundancy_k": 0, "redundancy_n": 2,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "P"},
                {"index": 1, "group_id": "C", "component_type_id": "C", "name": "C",
                 "parent_group_index": 0, "aircraft_indexes": [0], "quantity": 1,
                 "redundancy_kind": "series", "redundancy_k": 0, "redundancy_n": 1,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "C"}
            ]),
            json!([
                {"index": 0, "instance_template_id": "P-0", "group_index": 0,
                 "parent_instance_index": -1, "failure_rate_per_hour": 0.1,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "P-0"},
                {"index": 1, "instance_template_id": "P-1", "group_index": 0,
                 "parent_instance_index": -1, "failure_rate_per_hour": 0.1,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "P-1"},
                {"index": 2, "instance_template_id": "C-0", "group_index": 1,
                 "parent_instance_index": 0, "failure_rate_per_hour": 0.1,
                 "repair_activity_index": -1, "repair_duration_minutes": 0,
                 "source_path": "C-0"}
            ]),
        );
        let parsed = plan(value.clone());
        assert_eq!(parsed.component_instances[2].parent_instance_index, 0);

        let mut invalid = value;
        invalid["component_groups"][0]["failure_threshold"] = json!(2);
        let raw = serde_json::to_vec(&invalid).unwrap();
        assert!(ReliabilityExecutionPlan::from_slice(&raw).is_err());
    }

    #[test]
    fn repair_only_changes_target_state() {
        let states = [state("A-0", true), state("A-1", true)];
        let repaired = complete_repair(&states, "F35-01/A-0").unwrap();
        assert!(!repaired[0].failed);
        assert!(repaired[1].failed);
    }
}
