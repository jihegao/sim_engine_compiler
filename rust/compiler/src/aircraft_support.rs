//! Domain lowering for canonical `aircraft-support-v1-input-v1` documents.

use std::collections::{BTreeMap, HashMap, HashSet};

use anyhow::{Result, bail};
use serde_json::{Map, Value};
use sim_engine_runtime::plan::{
    ActivitySpec, AircraftSpec, ComponentSpec, ExecutionPlan, MissionSpec, PreventiveCycleSpec,
    ResourceNodeSpec, SupplyRouteSpec, WorkStepSpec,
};
use sim_engine_runtime::reliability::{
    RELIABILITY_POLICY, ReliabilityComponentGroupSpec, ReliabilityComponentInstanceSpec,
};

pub mod validation;

// Input acceptance changed: never reuse caches emitted before strict validation.
pub const COMPILER_VERSION: &str = "aircraft-support-aot/v1alpha6";

const LEGACY_MINUTE_PHASES: &[&str] = &[
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

fn object(value: Option<&Value>) -> Option<&Map<String, Value>> {
    value.and_then(Value::as_object)
}

fn array(value: Option<&Value>) -> &[Value] {
    value.and_then(Value::as_array).map_or(&[], Vec::as_slice)
}

fn text(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Number(value)) => value.to_string(),
        Some(Value::Bool(value)) => value.to_string(),
        _ => String::new(),
    }
}

fn number(value: Option<&Value>) -> Option<f64> {
    match value {
        Some(Value::Number(value)) => value.as_f64(),
        Some(Value::String(value)) => value.parse().ok(),
        Some(Value::Bool(value)) => Some(if *value { 1.0 } else { 0.0 }),
        _ => None,
    }
}

fn work_duration(value: Option<&Value>, default: i64) -> i64 {
    match value {
        Some(Value::String(raw)) => {
            positive_i64(Some(&Value::String(raw.trim().to_owned())), default)
        }
        _ => positive_i64(value, default),
    }
}

fn positive_i64(value: Option<&Value>, default: i64) -> i64 {
    number(value)
        .filter(|value| value.is_finite())
        .map(|value| value.trunc() as i64)
        .filter(|value| *value > 0)
        .unwrap_or(default)
}

fn non_negative_i64(value: Option<&Value>, default: i64) -> i64 {
    number(value)
        .filter(|value| value.is_finite())
        .map(|value| (value.trunc() as i64).max(0))
        .unwrap_or(default)
}

fn positive_usize(value: Option<&Value>, default: usize) -> usize {
    positive_i64(value, default as i64) as usize
}

fn non_negative_f64(value: Option<&Value>, default: f64) -> f64 {
    number(value)
        .filter(|value| value.is_finite())
        .map(|value| value.max(0.0))
        .unwrap_or(default)
}

fn first_non_empty(values: &[Option<&Value>]) -> String {
    values
        .iter()
        .map(|value| text(*value))
        .find(|value| !value.is_empty())
        .unwrap_or_default()
}

fn time_to_minute(value: Option<&Value>, default: i64) -> i64 {
    let raw = text(value);
    let Some((hour, rest)) = raw.split_once(':') else {
        return default;
    };
    let Some(minute) = rest.split(':').next() else {
        return default;
    };
    match (hour.parse::<i64>(), minute.parse::<i64>()) {
        (Ok(hour), Ok(minute)) => (hour * 60 + minute).max(0),
        _ => default,
    }
}

fn resource_quantity(items: Option<&Value>, explicit: Option<&Value>, default: i64) -> i64 {
    if let Some(value) = number(explicit)
        && value > 0.0
    {
        return (value.trunc() as i64).max(1);
    }
    let total = array(items)
        .iter()
        .filter_map(Value::as_object)
        .map(|item| non_negative_i64(item.get("quantity"), 1))
        .sum::<i64>();
    if total > 0 { total } else { default }
}

fn spare_requirements(value: Option<&Value>) -> Vec<(String, i64)> {
    let rows: Vec<&Value> = match value {
        Some(Value::Array(items)) => items.iter().collect(),
        Some(item) => vec![item],
        None => Vec::new(),
    };
    let mut result = BTreeMap::<String, i64>::new();
    for row in rows {
        let (product_id, quantity) = match row {
            Value::Object(item) => (
                first_non_empty(&[
                    item.get("product_id"),
                    item.get("productId"),
                    item.get("spare_type"),
                    item.get("id"),
                ])
                .trim()
                .to_owned(),
                positive_i64(item.get("quantity"), 1),
            ),
            Value::String(item) => {
                let parts = item.split(',').map(str::trim).collect::<Vec<_>>();
                let quantity = parts
                    .get(1)
                    .and_then(|value| value.parse::<f64>().ok())
                    .map(|value| value.trunc() as i64)
                    .filter(|value| *value > 0)
                    .unwrap_or(1);
                (parts.first().copied().unwrap_or("").to_owned(), quantity)
            }
            _ => (String::new(), 1),
        };
        if !product_id.is_empty() {
            *result.entry(product_id).or_default() += quantity;
        }
    }
    result.into_iter().collect()
}

fn activity_kind(item: &Map<String, Value>) -> String {
    let phase = text(item.get("operations_phase"));
    if !phase.is_empty() {
        return phase;
    }
    let value = format!(
        "{} {} {}",
        text(item.get("id")),
        text(item.get("name")),
        text(item.get("activity_type"))
    )
    .to_lowercase();
    for (needles, kind) in [
        (
            &["corrective", "repair", "修复性维修", "故障修复"][..],
            "repair",
        ),
        (&["preventive", "预防", "定检"][..], "preventive"),
        (&["postflight", "飞行后", "航后"][..], "postflight"),
        (
            &["preflight", "飞行前", "直接准备", "使用保障"][..],
            "preflight",
        ),
    ] {
        if needles.iter().any(|needle| value.contains(needle)) {
            return kind.to_owned();
        }
    }
    "other".to_owned()
}

fn aircraft_tokens(value: &str) -> HashSet<String> {
    let normalized = value.trim().to_lowercase();
    if normalized.is_empty() {
        return HashSet::new();
    }
    let compact = normalized
        .chars()
        .filter(|character| character.is_alphanumeric())
        .collect::<String>();
    [normalized, compact]
        .into_iter()
        .filter(|item| !item.is_empty())
        .collect()
}

fn topological_steps(item: &Map<String, Value>, source_path: &str) -> Result<Vec<WorkStepSpec>> {
    let raw_steps = array(item.get("jobs"))
        .iter()
        .filter_map(Value::as_object)
        .collect::<Vec<_>>();
    let codes = raw_steps
        .iter()
        .enumerate()
        .map(|(index, step)| {
            let code = text(step.get("activityCode"));
            if code.is_empty() {
                format!("step-{}", index + 1)
            } else {
                code
            }
        })
        .collect::<Vec<_>>();
    if codes.iter().collect::<HashSet<_>>().len() != codes.len() {
        bail!("duplicate activityCode in {:?}", text(item.get("id")));
    }
    let source_index = codes
        .iter()
        .enumerate()
        .map(|(index, code)| (code.as_str(), index))
        .collect::<HashMap<_, _>>();
    let mut predecessors = Vec::with_capacity(raw_steps.len());
    for step in &raw_steps {
        let mut current = Vec::new();
        for code in array(step.get("predecessors")) {
            let code = text(Some(code));
            let Some(index) = source_index.get(code.as_str()) else {
                bail!(
                    "unknown predecessor in {:?}: {code:?}",
                    text(item.get("id"))
                );
            };
            current.push(*index);
        }
        predecessors.push(current);
    }
    let mut ordered = Vec::new();
    let mut completed = HashSet::new();
    let mut remaining = (0..raw_steps.len()).collect::<Vec<_>>();
    while !remaining.is_empty() {
        let mut progressed = false;
        let snapshot = remaining.clone();
        for index in snapshot {
            if predecessors[index]
                .iter()
                .all(|parent| completed.contains(parent))
            {
                completed.insert(index);
                ordered.push(index);
                remaining.retain(|candidate| *candidate != index);
                progressed = true;
            }
        }
        if !progressed {
            bail!("cycle in activity {:?}", text(item.get("id")));
        }
    }
    let dense = ordered
        .iter()
        .enumerate()
        .map(|(dense, source)| (*source, dense))
        .collect::<HashMap<_, _>>();
    let default_duration = work_duration(item.get("duration_minutes"), 30);
    Ok(ordered
        .iter()
        .enumerate()
        .map(|(index, source)| {
            let step = raw_steps[*source];
            WorkStepSpec {
                index,
                code: codes[*source].clone(),
                duration_minutes: work_duration(
                    step.get("durationMinutes")
                        .or_else(|| step.get("duration_minutes")),
                    default_duration,
                ),
                personnel: resource_quantity(
                    step.get("personnel"),
                    step.get("requiredPersonnel")
                        .or_else(|| step.get("required_personnel"))
                        .or_else(|| item.get("required_personnel")),
                    1,
                ),
                equipment: resource_quantity(
                    step.get("equipment"),
                    step.get("requiredDevices")
                        .or_else(|| step.get("required_devices"))
                        .or_else(|| item.get("required_devices")),
                    1,
                ),
                spares: spare_requirements(step.get("spare")),
                predecessors: predecessors[*source]
                    .iter()
                    .map(|parent| dense[parent])
                    .collect(),
                source_path: format!("{source_path}.jobs[{source}]"),
            }
        })
        .collect())
}

fn compile_aircraft(inputs: &Map<String, Value>) -> Result<Vec<AircraftSpec>> {
    let config = object(inputs.get("aircraft")).cloned().unwrap_or_default();
    let assets = array(config.get("assets"))
        .iter()
        .filter_map(Value::as_object)
        .collect::<Vec<_>>();
    let fleet_count = positive_usize(config.get("fleet_count"), 0)
        .max(assets.len())
        .max(1);
    let initial_ready = non_negative_i64(config.get("initial_ready"), fleet_count as i64)
        .min(fleet_count as i64) as usize;
    let models = if array(config.get("models")).is_empty() {
        vec!["Aircraft".to_owned()]
    } else {
        array(config.get("models"))
            .iter()
            .map(|item| text(Some(item)))
            .collect()
    };
    let mut result = Vec::with_capacity(fleet_count);
    for index in 0..fleet_count {
        let item = assets.get(index).copied().cloned().unwrap_or_default();
        let initial_life = object(item.get("initial_life_state"))
            .cloned()
            .unwrap_or_default();
        let aircraft_type = {
            let value = first_non_empty(&[
                item.get("aircraft_type"),
                item.get("aircraftType"),
                item.get("model"),
            ]);
            if value.is_empty() {
                models[index % models.len()].clone()
            } else {
                value
            }
        };
        let mut initial_state =
            first_non_empty(&[item.get("initial_state"), item.get("initialState")]);
        if !matches!(
            initial_state.as_str(),
            "available" | "maintenance" | "flying"
        ) {
            initial_state = if index < initial_ready {
                "available"
            } else {
                "maintenance"
            }
            .to_owned();
        }
        let tail_number = first_non_empty(&[item.get("tail_number"), item.get("tailNumber")]);
        result.push(AircraftSpec {
            index,
            tail_number: if tail_number.is_empty() {
                format!("AC-{:03}", index + 1)
            } else {
                tail_number
            },
            aircraft_type: aircraft_type.clone(),
            model: {
                let value = text(item.get("model"));
                if value.is_empty() {
                    aircraft_type
                } else {
                    value
                }
            },
            initial_state,
            airport: text(item.get("airport")),
            airport_id: first_non_empty(&[item.get("airport_id"), item.get("airportId")]),
            initial_calendar_days: non_negative_i64(initial_life.get("calendar_days"), 0),
            initial_flight_hours: non_negative_f64(initial_life.get("flight_hours"), 0.0),
            initial_cycles: non_negative_i64(initial_life.get("takeoff_landing_cycles"), 0),
        });
    }
    if result
        .iter()
        .map(|item| item.tail_number.as_str())
        .collect::<HashSet<_>>()
        .len()
        != result.len()
    {
        bail!("aircraft tail numbers must be unique");
    }
    Ok(result)
}

fn compile_nodes(inputs: &Map<String, Value>) -> Result<Vec<ResourceNodeSpec>> {
    let network = object(inputs.get("support_network"))
        .cloned()
        .unwrap_or_default();
    let mut nodes = array(network.get("nodes"))
        .iter()
        .filter_map(Value::as_object)
        .cloned()
        .collect::<Vec<_>>();
    if nodes.is_empty() {
        nodes.push(Map::from_iter([
            ("id".to_owned(), Value::String("default".to_owned())),
            ("personnel_capacity".to_owned(), Value::from(1)),
            ("equipment_capacity".to_owned(), Value::from(1)),
        ]));
    }
    let result = nodes
        .iter()
        .enumerate()
        .map(|(index, item)| {
            let node_id = {
                let value = text(item.get("id"));
                if value.is_empty() {
                    format!("node-{}", index + 1)
                } else {
                    value
                }
            };
            let inventory = object(item.get("inventory"))
                .map(|items| {
                    items
                        .iter()
                        .map(|(key, value)| (key.clone(), non_negative_i64(Some(value), 0)))
                        .collect()
                })
                .unwrap_or_default();
            ResourceNodeSpec {
                index,
                node_id: node_id.clone(),
                personnel_capacity: non_negative_i64(item.get("personnel_capacity"), 0),
                equipment_capacity: non_negative_i64(item.get("equipment_capacity"), 0),
                inventory,
                organization_node_id: {
                    let value = first_non_empty(&[
                        item.get("organization_node_id"),
                        item.get("organizationNodeId"),
                        item.get("id"),
                    ]);
                    if value.is_empty() { node_id } else { value }
                },
                source_path: format!("support_network.nodes[{index}]"),
            }
        })
        .collect::<Vec<_>>();
    if result
        .iter()
        .map(|item| item.node_id.as_str())
        .collect::<HashSet<_>>()
        .len()
        != result.len()
    {
        bail!("support node ids must be unique");
    }
    Ok(result)
}

fn compile_activities(
    inputs: &Map<String, Value>,
    nodes: &[ResourceNodeSpec],
    component_indexes: &HashMap<String, usize>,
) -> Result<Vec<ActivitySpec>> {
    let support = object(inputs.get("support_activities"))
        .cloned()
        .unwrap_or_default();
    let activities = array(support.get("activities"))
        .iter()
        .filter_map(Value::as_object)
        .collect::<Vec<_>>();
    let node_indexes = nodes
        .iter()
        .map(|node| (node.node_id.as_str(), node.index))
        .collect::<HashMap<_, _>>();
    let default_node = nodes
        .iter()
        .find(|node| node.personnel_capacity != 0 || node.equipment_capacity != 0)
        .map_or(0, |node| node.index);
    let mut result = Vec::with_capacity(activities.len());
    for (index, item) in activities.iter().enumerate() {
        let activity_id = {
            let value = text(item.get("id"));
            if value.is_empty() {
                format!("activity-{}", index + 1)
            } else {
                value
            }
        };
        let resource_id = text(item.get("resource_id"));
        if !resource_id.is_empty() && !node_indexes.contains_key(resource_id.as_str()) {
            bail!("unknown resource node {resource_id:?} for {activity_id:?}");
        }
        let mut seen_methods = HashSet::new();
        let maintenance_methods = array(item.get("maintenance_methods"))
            .iter()
            .map(|value| text(Some(value)))
            .filter(|value| matches!(value.as_str(), "non_replacement" | "replacement"))
            .filter(|value| seen_methods.insert(value.clone()))
            .collect();
        let aircraft_model = text(item.get("aircraft_model"));
        result.push(ActivitySpec {
            index,
            activity_id: activity_id.clone(),
            name: {
                let value = text(item.get("name"));
                if value.is_empty() { activity_id } else { value }
            },
            phase: text(item.get("operations_phase")),
            plan_group_id: text(item.get("plan_group_id")),
            aircraft_model,
            resource_node_index: node_indexes
                .get(resource_id.as_str())
                .copied()
                .unwrap_or(default_node),
            priority: positive_i64(item.get("priority"), 1),
            kind: activity_kind(item),
            equipment_component_index: component_indexes
                .get(&text(item.get("equipment_id")))
                .map_or(-1, |value| *value as i64),
            maintenance_methods,
            replacement_ratio: non_negative_f64(item.get("replacement_ratio"), 0.0).min(1.0),
            steps: topological_steps(item, &format!("support_activities.activities[{index}]"))?,
            source_path: format!("support_activities.activities[{index}]"),
        });
    }
    if result
        .iter()
        .map(|item| item.activity_id.as_str())
        .collect::<HashSet<_>>()
        .len()
        != result.len()
    {
        bail!("support activity ids must be unique");
    }
    Ok(result)
}

fn compile_missions(inputs: &Map<String, Value>, duration_minutes: i64) -> Vec<MissionSpec> {
    let profile = object(inputs.get("mission_profile"))
        .cloned()
        .unwrap_or_default();
    let distance_km = array(profile.get("airports"))
        .iter()
        .filter_map(Value::as_object)
        .map(|item| non_negative_f64(item.get("distanceToMissionKm"), 0.0))
        .fold(0.0_f64, f64::max);
    let phase_minutes = array(profile.get("mission_phases"))
        .iter()
        .filter_map(Value::as_object)
        .map(|item| (non_negative_f64(item.get("limitHours"), 0.0) * 10.0).round_ties_even() as i64)
        .sum::<i64>();
    let duration_adjustment =
        ((distance_km / 900.0) * 60.0).round_ties_even() as i64 + phase_minutes;

    let mut basics = HashMap::<String, Map<String, Value>>::new();
    let mut default_basic = Map::new();
    for (index, value) in array(profile.get("basic_missions")).iter().enumerate() {
        let Some(item) = value.as_object() else {
            continue;
        };
        if default_basic.is_empty() {
            default_basic = item.clone();
        }
        let mission_id = {
            let value =
                first_non_empty(&[item.get("id"), item.get("missionId"), item.get("taskNo")]);
            if value.is_empty() {
                format!("basic-{}", index + 1)
            } else {
                value
            }
        };
        for alias in [
            Some(Value::String(mission_id)),
            item.get("name").cloned(),
            item.get("basicTaskName").cloned(),
            item.get("missionId").cloned(),
            item.get("taskNo").cloned(),
        ] {
            let alias = text(alias.as_ref());
            if !alias.trim().is_empty() {
                basics.entry(alias).or_insert_with(|| item.clone());
            }
        }
    }

    let calendar = profile.get("mission_calendar");
    let has_calendar = calendar.is_some_and(Value::is_array);
    let mut active_days = HashMap::<String, Vec<i64>>::new();
    for value in array(calendar) {
        let Some(item) = value.as_object() else {
            continue;
        };
        let composite_id = text(item.get("composite_task_id"));
        let day = positive_i64(item.get("day_index"), 0);
        if !composite_id.is_empty() && day > 0 {
            active_days.entry(composite_id).or_default().push(day - 1);
        }
    }

    let mut result = Vec::new();
    for (composite_index, value) in array(profile.get("composite_tasks")).iter().enumerate() {
        let Some(composite) = value.as_object() else {
            continue;
        };
        let composite_id = text(composite.get("id"));
        if has_calendar && !active_days.contains_key(&composite_id) {
            continue;
        }
        for (item_index, value) in array(composite.get("taskItems")).iter().enumerate() {
            let Some(item) = value.as_object() else {
                continue;
            };
            let mut basic = &default_basic;
            for alias in [item.get("basicMissionId"), item.get("basicTaskName")] {
                let alias = text(alias);
                if let Some(candidate) = basics.get(&alias) {
                    basic = candidate;
                    break;
                }
            }
            let base_id = {
                let value = text(item.get("id"));
                if value.is_empty() {
                    format!("{composite_id}__item-{}", item_index + 1)
                } else {
                    value
                }
            };
            let first_start = time_to_minute(
                item.get("firstWaveTime"),
                positive_i64(basic.get("startHour"), 1) * 60,
            );
            let notice = non_negative_i64(
                item.get("advanceNoticeMinutes")
                    .or_else(|| basic.get("advanceNoticeMinutes")),
                0,
            );
            let mission_duration = positive_i64(
                item.get("taskDurationMinutes")
                    .or_else(|| basic.get("taskDurationMinutes")),
                120,
            ) + duration_adjustment.max(0);
            let repeat_count = positive_i64(item.get("dailyRepeatCount"), 1);
            let interval_hours = match item.get("intervalHours") {
                None | Some(Value::Null) => 24.0,
                value => number(value).unwrap_or(24.0),
            };
            let interval = (interval_hours * 60.0).round_ties_even().max(1.0) as i64;
            let mut days = active_days
                .get(&composite_id)
                .cloned()
                .unwrap_or_else(|| vec![0]);
            days.sort_unstable();
            days.dedup();
            let profile_duration = positive_i64(profile.get("duration_minutes"), duration_minutes);
            for day in days {
                for repeat in 0..repeat_count {
                    let planned = day * 1440 + first_start + repeat * interval;
                    if planned >= duration_minutes.min(profile_duration) {
                        continue;
                    }
                    let basic_name = first_non_empty(&[
                        item.get("basicTaskName"),
                        composite.get("name"),
                        basic.get("name"),
                    ]);
                    let required_aircraft = positive_usize(
                        item.get("equipmentQuantity")
                            .or_else(|| basic.get("equipmentQuantity")),
                        1,
                    );
                    result.push(MissionSpec {
                        index: usize::MAX,
                        mission_id: format!("{base_id}-d{}-w{}", planned / 1440 + 1, repeat + 1),
                        name: if basic_name.is_empty() { base_id.clone() } else { basic_name },
                        planned_start: planned,
                        preparation_start: (planned - notice).max(0),
                        duration_minutes: mission_duration,
                        required_aircraft,
                        min_required_aircraft: positive_usize(
                            basic.get("minRequiredSorties").or_else(|| basic.get("equipmentQuantity")),
                            1,
                        ),
                        priority: positive_i64(composite.get("priority"), 1),
                        cancel_minutes: non_negative_i64(basic.get("cancelMinutes"), 20),
                        success_point: number(basic.get("successPoint")).unwrap_or(1.0).clamp(0.0, 1.0),
                        required_aircraft_type: first_non_empty(&[item.get("equipmentType"), basic.get("equipmentType")]),
                        operations_plan_group_id: first_non_empty(&[
                            item.get("operations_plan_group_id"), basic.get("operations_plan_group_id")
                        ]),
                        source_path: format!("mission_profile.composite_tasks[{composite_index}].taskItems[{item_index}]"),
                    });
                }
            }
        }
    }
    if result.is_empty() && !has_calendar {
        let planned = positive_i64(default_basic.get("startHour"), 1) * 60;
        let notice = non_negative_i64(default_basic.get("advanceNoticeMinutes"), 0);
        let required = positive_usize(default_basic.get("equipmentQuantity"), 1);
        result.push(MissionSpec {
            index: 0,
            mission_id: {
                let value =
                    first_non_empty(&[default_basic.get("missionId"), default_basic.get("id")]);
                if value.is_empty() {
                    "mission-1".to_owned()
                } else {
                    value
                }
            },
            name: {
                let value = text(default_basic.get("name"));
                if value.is_empty() {
                    "mission".to_owned()
                } else {
                    value
                }
            },
            planned_start: planned,
            preparation_start: (planned - notice).max(0),
            duration_minutes: positive_i64(default_basic.get("taskDurationMinutes"), 120),
            required_aircraft: required,
            min_required_aircraft: positive_usize(
                default_basic
                    .get("minRequiredSorties")
                    .or_else(|| default_basic.get("equipmentQuantity")),
                1,
            ),
            priority: 1,
            cancel_minutes: non_negative_i64(default_basic.get("cancelMinutes"), 20),
            success_point: number(default_basic.get("successPoint"))
                .unwrap_or(1.0)
                .clamp(0.0, 1.0),
            required_aircraft_type: text(default_basic.get("equipmentType")),
            operations_plan_group_id: text(default_basic.get("operations_plan_group_id")),
            source_path: "mission_profile.basic_missions[0]".to_owned(),
        });
    }
    result.sort_by_key(|item| (item.planned_start, item.priority));
    for (index, item) in result.iter_mut().enumerate() {
        item.index = index;
    }
    result
}

fn failure_distribution_rate(distribution: &Map<String, Value>) -> Option<f64> {
    let parameters = distribution
        .get("parameters")
        .or_else(|| distribution.get("params"));
    let multiplier = non_negative_f64(distribution.get("_rate_multiplier"), 1.0);
    if let Some(value) = number(parameters) {
        return Some(value.max(0.0) * multiplier);
    }
    let distribution_type = first_non_empty(&[
        distribution.get("distributionType"),
        distribution.get("distribution_type"),
    ])
    .to_lowercase();
    let mut values = HashMap::<String, f64>::new();
    if let Some(Value::String(parameters)) = parameters {
        for part in parameters.replace(['，', '；', ';'], ",").split(',') {
            let Some((key, raw)) = part.split_once('=') else {
                continue;
            };
            values.insert(
                key.trim().to_lowercase(),
                raw.trim().parse::<f64>().unwrap_or(0.0).max(0.0),
            );
        }
        for key in ["lambda", "λ", "rate", "failure_rate"] {
            if let Some(value) = values.get(key) {
                return Some(value * multiplier);
            }
        }
        if distribution_type.contains("weibull") || distribution_type.contains("威布尔") {
            let beta = values
                .get("beta")
                .or_else(|| values.get("shape"))
                .copied()
                .unwrap_or(1.0);
            let eta = values
                .get("eta")
                .or_else(|| values.get("scale"))
                .or_else(|| values.get("mean"))
                .copied();
            if let Some(eta) = eta.filter(|value| *value > 0.0) {
                return Some(
                    (1.0 / (eta * libm::tgamma(1.0 + 1.0 / beta.max(0.001)))) * multiplier,
                );
            }
        }
        if (distribution_type.contains("normal") || distribution_type.contains("正态"))
            && let Some(mean) = values
                .get("mean")
                .or_else(|| values.get("mu"))
                .filter(|value| **value > 0.0)
        {
            return Some((1.0 / mean) * multiplier);
        }
    }
    if distribution_type.contains("exponential") || distribution_type.contains("指数") {
        let rate = non_negative_f64(
            distribution
                .get("lambda")
                .or_else(|| distribution.get("rate")),
            0.0,
        );
        return (rate > 0.0).then_some(rate * multiplier);
    }
    if distribution_type.contains("normal") || distribution_type.contains("正态") {
        let mean = non_negative_f64(
            distribution.get("mean").or_else(|| distribution.get("mu")),
            0.0,
        );
        return (mean > 0.0).then_some((1.0 / mean) * multiplier);
    }
    if distribution_type.contains("uniform") || distribution_type.contains("均匀") {
        let minimum = number(distribution.get("min")).unwrap_or(-1.0);
        let maximum = number(distribution.get("max")).unwrap_or(-1.0);
        return (minimum >= 0.0 && maximum >= minimum && minimum + maximum > 0.0)
            .then_some((2.0 / (minimum + maximum)) * multiplier);
    }
    if distribution_type.contains("fixed") || distribution_type.contains("固定") {
        let value = number(
            distribution
                .get("value")
                .or_else(|| distribution.get("mean")),
        )
        .unwrap_or(0.0);
        return (value > 0.0).then_some((1.0 / value) * multiplier);
    }
    None
}

fn component_applies(component_model: &str, aircraft: &AircraftSpec) -> bool {
    let component = aircraft_tokens(component_model);
    component.is_empty()
        || !component.is_disjoint(&aircraft_tokens(&aircraft.aircraft_type))
        || !component.is_disjoint(&aircraft_tokens(&aircraft.model))
}

fn is_reliability_input(inputs: &Map<String, Value>) -> bool {
    let equipment = object(inputs.get("equipment_tree"));
    array(equipment.and_then(|value| value.get("components")))
        .iter()
        .filter_map(Value::as_object)
        .any(|component| {
            [
                "component_type_id",
                "instances",
                "redundancy",
                "parent_instance_id",
            ]
            .iter()
            .any(|key| component.contains_key(*key))
                || component
                    .get("k_out_of_n")
                    .and_then(Value::as_object)
                    .and_then(|value| value.get("enabled"))
                    .and_then(Value::as_bool)
                    == Some(true)
        })
}

fn contains_failure_threshold(value: &Value) -> bool {
    match value {
        Value::Object(map) => {
            map.contains_key("failure_threshold") || map.values().any(contains_failure_threshold)
        }
        Value::Array(items) => items.iter().any(contains_failure_threshold),
        _ => false,
    }
}

fn optional_text(value: Option<&Value>, path: &str, code: &'static str) -> Result<Option<String>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) if value.is_empty() => Ok(None),
        Some(Value::String(value)) => Ok(Some(value.clone())),
        _ => bail!("{code} at {path}: expected string"),
    }
}

fn strict_positive_usize(
    value: Option<&Value>,
    default: Option<usize>,
    path: &str,
) -> Result<usize> {
    match value {
        None if default.is_some() => Ok(default.unwrap()),
        Some(value) => {
            let parsed = value
                .as_u64()
                .and_then(|value| usize::try_from(value).ok())
                .filter(|value| *value > 0);
            match parsed {
                Some(value) => Ok(value),
                None => bail!("invalid_quantity at {path}: expected a positive integer"),
            }
        }
        None => bail!("invalid_quantity at {path}: expected a positive integer"),
    }
}

fn strict_nonnegative_i64(value: Option<&Value>, path: &str, code: &'static str) -> Result<i64> {
    value
        .and_then(Value::as_i64)
        .filter(|value| *value >= 0)
        .ok_or_else(|| anyhow::anyhow!("{code} at {path}: expected a nonnegative integer"))
}

fn strict_repair_activity(value: Option<&Value>, path: &str) -> Result<i64> {
    value
        .and_then(Value::as_i64)
        .filter(|value| *value >= -1)
        .ok_or_else(|| {
            anyhow::anyhow!("invalid_repair_activity at {path}: expected an index >= -1")
        })
}

fn strict_rate(value: &Value, path: &str) -> Result<f64> {
    value
        .as_f64()
        .filter(|value| value.is_finite() && *value >= 0.0)
        .ok_or_else(|| {
            anyhow::anyhow!(
                "invalid_failure_rate at {path}: failure rate must be finite and nonnegative"
            )
        })
}

fn reliability_rate(item: &Map<String, Value>, path: &str) -> Result<Option<f64>> {
    let explicit = item
        .get("failure_rate_per_hour")
        .filter(|value| !value.is_null())
        .or_else(|| item.get("failure_rate").filter(|value| !value.is_null()));
    let distribution = object(item.get("failure_distribution")).filter(|value| !value.is_empty());
    if explicit.is_some() && distribution.is_some() {
        bail!(
            "ambiguous_failure_parameter at {path}: failure_rate_per_hour and failure_distribution are mutually exclusive"
        );
    }
    if let Some(value) = explicit {
        return strict_rate(value, &format!("{path}.failure_rate_per_hour")).map(Some);
    }
    let Some(distribution) = distribution else {
        return Ok(None);
    };
    if let Some(mtbf) = distribution.get("mtbf") {
        if distribution.get("timeUnit").and_then(Value::as_str) != Some("hour") {
            bail!(
                "unsupported_failure_time_unit at {path}.failure_distribution.timeUnit: MTBF timeUnit must be 'hour'"
            );
        }
        if distribution.get("timeBasis").and_then(Value::as_str) != Some("flight_hour") {
            bail!(
                "unsupported_failure_time_basis at {path}.failure_distribution.timeBasis: MTBF timeBasis must be 'flight_hour'"
            );
        }
        let mtbf = mtbf
            .as_f64()
            .filter(|value| value.is_finite() && *value > 0.0)
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "invalid_mtbf at {path}.failure_distribution.mtbf: MTBF must be a positive finite number"
                )
            })?;
        return strict_rate(
            &Value::from(1.0 / mtbf),
            &format!("{path}.failure_distribution"),
        )
        .map(Some);
    }
    let converted = failure_distribution_rate(distribution).ok_or_else(|| {
        anyhow::anyhow!(
            "unsupported_failure_distribution at {path}.failure_distribution: unsupported failure distribution"
        )
    })?;
    strict_rate(
        &Value::from(converted),
        &format!("{path}.failure_distribution"),
    )
    .map(Some)
}

fn repair_activity(profile: Option<&Map<String, Value>>, path: &str) -> Result<i64> {
    let Some(profile) = profile else {
        return Ok(-1);
    };
    match profile
        .get("repair_activity_index")
        .filter(|value| !value.is_null())
        .or_else(|| profile.get("repairActivityIndex"))
    {
        None => Ok(-1),
        value => strict_repair_activity(value, path),
    }
}

fn repair_duration(profile: Option<&Map<String, Value>>, path: &str) -> Result<Option<i64>> {
    let Some(profile) = profile else {
        return Ok(None);
    };
    match profile
        .get("repair_duration_minutes")
        .filter(|value| !value.is_null())
        .or_else(|| profile.get("repairTimeMinutes"))
    {
        None => Ok(None),
        value => strict_nonnegative_i64(value, path, "invalid_repair_duration").map(Some),
    }
}

fn repair_profile(item: &Map<String, Value>) -> Option<&Map<String, Value>> {
    if item.contains_key("repair_profile") {
        item.get("repair_profile").and_then(Value::as_object)
    } else {
        item.get("special_repair_profile")
            .and_then(Value::as_object)
    }
}

fn parse_redundancy(
    item: &Map<String, Value>,
    path: &str,
    instance_count: usize,
) -> Result<(String, usize, usize)> {
    let redundancy = item.get("redundancy").filter(|value| !value.is_null());
    let legacy = item.get("k_out_of_n").filter(|value| !value.is_null());
    if redundancy.is_some() && legacy.is_some() {
        bail!("ambiguous_redundancy at {path}: redundancy and k_out_of_n are mutually exclusive");
    }
    if let Some(redundancy) = redundancy {
        let Some(redundancy) = redundancy.as_object() else {
            bail!("invalid_redundancy at {path}: redundancy must be an object");
        };
        let kind = text(redundancy.get("kind"));
        if kind != "series" && kind != "k_out_of_n" {
            bail!("invalid_redundancy_kind at {path}: invalid redundancy kind");
        }
        if kind == "series" {
            if redundancy.get("k").is_some_and(|value| !value.is_null()) {
                bail!("redundancy_k_on_series at {path}: series must not define k");
            }
            if let Some(n) = redundancy.get("n").filter(|value| !value.is_null()) {
                if n.as_u64() != Some(instance_count as u64) {
                    bail!("redundancy_n_mismatch at {path}: redundancy_n must equal quantity");
                }
            }
            return Ok((kind, 0, instance_count));
        }
        let n = redundancy
            .get("n")
            .and_then(Value::as_u64)
            .and_then(|value| usize::try_from(value).ok())
            .filter(|value| *value == instance_count)
            .ok_or_else(|| {
                anyhow::anyhow!("redundancy_n_mismatch at {path}: redundancy_n must equal quantity")
            })?;
        let k = redundancy
            .get("k")
            .and_then(Value::as_u64)
            .and_then(|value| usize::try_from(value).ok())
            .filter(|value| *value >= 1 && *value <= n)
            .ok_or_else(|| {
                anyhow::anyhow!("invalid_redundancy_k at {path}: k must be between 1 and n")
            })?;
        return Ok((kind, k, n));
    }
    if let Some(legacy) = legacy {
        let Some(legacy) = legacy.as_object() else {
            bail!(
                "invalid_k_out_of_n at {path}: k_out_of_n must be an object with a boolean enabled field"
            );
        };
        let Some(enabled) = legacy.get("enabled").and_then(Value::as_bool) else {
            bail!(
                "invalid_k_out_of_n at {path}: k_out_of_n must be an object with a boolean enabled field"
            );
        };
        if !enabled {
            return Ok(("series".into(), 0, instance_count));
        }
        let n = legacy
            .get("n")
            .and_then(Value::as_u64)
            .and_then(|value| usize::try_from(value).ok())
            .filter(|value| *value == instance_count)
            .ok_or_else(|| {
                anyhow::anyhow!("redundancy_n_mismatch at {path}: k_out_of_n n must equal quantity")
            })?;
        let k = legacy
            .get("k")
            .and_then(Value::as_u64)
            .and_then(|value| usize::try_from(value).ok())
            .filter(|value| *value >= 1 && *value <= n)
            .ok_or_else(|| {
                anyhow::anyhow!("invalid_redundancy_k at {path}: k must be between 1 and n")
            })?;
        return Ok(("k_out_of_n".into(), k, n));
    }
    Ok(("series".into(), 0, instance_count))
}

fn reliability_applies(item: &Map<String, Value>, aircraft: &[AircraftSpec]) -> Vec<usize> {
    let model = text(item.get("aircraft_model"));
    let component_tokens = aircraft_tokens(&model);
    if component_tokens.is_empty() {
        return (0..aircraft.len()).collect();
    }
    aircraft
        .iter()
        .enumerate()
        .filter(|(_, value)| {
            let tokens = aircraft_tokens(&value.tail_number)
                .into_iter()
                .chain(aircraft_tokens(&value.aircraft_type))
                .chain(aircraft_tokens(&value.model))
                .collect::<HashSet<_>>();
            !component_tokens.is_disjoint(&tokens)
        })
        .map(|(index, _)| index)
        .collect()
}

struct ReliabilityRawInstance {
    instance_id: String,
    failure_rate_per_hour: f64,
    repair_activity_index: i64,
    repair_duration_minutes: i64,
    source_path: String,
}

struct ReliabilityRawGroup {
    group_id: String,
    component_type_id: String,
    name: String,
    quantity: usize,
    parent_id: Option<String>,
    parent_instance_id: Option<String>,
    instances: Vec<ReliabilityRawInstance>,
    redundancy_kind: String,
    redundancy_k: usize,
    redundancy_n: usize,
    repair_activity_index: i64,
    repair_duration_minutes: i64,
    aircraft_indexes: Vec<usize>,
    source_path: String,
}

fn build_reliability_plan_records(
    inputs: &Map<String, Value>,
    aircraft: &[AircraftSpec],
) -> Result<(
    Vec<ReliabilityComponentGroupSpec>,
    Vec<ReliabilityComponentInstanceSpec>,
)> {
    let equipment = object(inputs.get("equipment_tree"))
        .cloned()
        .unwrap_or_default();
    let rows = array(equipment.get("components"));
    let mut raw_groups = Vec::<ReliabilityRawGroup>::new();
    let mut seen_groups = HashSet::<String>::new();
    let mut seen_instances = HashSet::<String>::new();

    for (index, value) in rows.iter().enumerate() {
        let path = format!("equipment_tree.components[{index}]");
        let Some(item) = value.as_object() else {
            bail!("invalid_component at {path}: component must be an object");
        };
        if contains_failure_threshold(&Value::Object(item.clone())) {
            bail!(
                "failure_threshold_in_new_plan at {path}.failure_threshold: failure_threshold is not allowed in the reliability schema"
            );
        }
        let group_id = item
            .get("id")
            .and_then(Value::as_str)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| {
                anyhow::anyhow!("invalid_component_id at {path}.id: component id is required")
            })?
            .to_owned();
        if !seen_groups.insert(group_id.clone()) {
            bail!("duplicate_component_group_id at {path}.id: duplicate component id");
        }
        let component_type_id = item
            .get("component_type_id")
            .and_then(Value::as_str)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| anyhow::anyhow!("component_type_missing at {path}.component_type_id: component_type_id is required"))?
            .to_owned();
        let group_rate = reliability_rate(item, &path)?;
        let profile = repair_profile(item);
        let group_repair_activity = repair_activity(profile, &format!("{path}.repair_profile"))?;
        let group_repair_duration = repair_duration(profile, &format!("{path}.repair_profile"))?;
        let parent_id = optional_text(
            item.get("parent_id"),
            &format!("{path}.parent_id"),
            "invalid_parent_group",
        )?;
        let parent_instance_id = optional_text(
            item.get("parent_instance_id"),
            &format!("{path}.parent_instance_id"),
            "invalid_parent_instance",
        )?;

        let mut instances = Vec::<ReliabilityRawInstance>::new();
        let explicit = item.get("instances").filter(|value| !value.is_null());
        let quantity = if let Some(explicit) = explicit {
            let Some(values) = explicit.as_array().filter(|values| !values.is_empty()) else {
                bail!("invalid_instances at {path}.instances: instances must be a nonempty list");
            };
            if let Some(quantity_value) = item.get("quantity").filter(|value| !value.is_null()) {
                if quantity_value.as_u64() != Some(values.len() as u64) {
                    bail!(
                        "quantity_instance_mismatch at {path}.quantity: quantity must equal the explicit instance count"
                    );
                }
            }
            for (instance_index, value) in values.iter().enumerate() {
                let instance_path = format!("{path}.instances[{instance_index}]");
                let Some(instance) = value.as_object() else {
                    bail!("invalid_instance at {instance_path}: instance must be an object");
                };
                let instance_id = instance
                    .get("instance_id")
                    .and_then(Value::as_str)
                    .filter(|value| !value.is_empty())
                    .ok_or_else(|| anyhow::anyhow!("invalid_instance_id at {instance_path}.instance_id: instance_id is required"))?
                    .to_owned();
                if !seen_instances.insert(instance_id.clone()) {
                    bail!(
                        "duplicate_instance_id at {instance_path}.instance_id: duplicate instance_id"
                    );
                }
                let failure_rate = reliability_rate(instance, &instance_path)?
                    .unwrap_or_else(|| group_rate.unwrap_or(0.0));
                let instance_profile = instance.get("repair_profile").and_then(Value::as_object);
                let (repair_activity_index, repair_duration_minutes) =
                    if let Some(instance_profile) = instance_profile {
                        (
                            repair_activity(
                                Some(instance_profile),
                                &format!("{instance_path}.repair_profile"),
                            )?,
                            repair_duration(
                                Some(instance_profile),
                                &format!("{instance_path}.repair_profile"),
                            )?
                            .unwrap_or(0),
                        )
                    } else {
                        (group_repair_activity, group_repair_duration.unwrap_or(0))
                    };
                instances.push(ReliabilityRawInstance {
                    instance_id,
                    failure_rate_per_hour: failure_rate,
                    repair_activity_index,
                    repair_duration_minutes,
                    source_path: instance_path,
                });
            }
            values.len()
        } else {
            let quantity =
                strict_positive_usize(item.get("quantity"), Some(1), &format!("{path}.quantity"))?;
            let failure_rate = group_rate.unwrap_or(0.0);
            for instance_index in 0..quantity {
                let instance_id = format!("{group_id}-{instance_index}");
                if !seen_instances.insert(instance_id.clone()) {
                    bail!(
                        "duplicate_instance_id at {path}: generated instance_id collides with another instance"
                    );
                }
                instances.push(ReliabilityRawInstance {
                    instance_id,
                    failure_rate_per_hour: failure_rate,
                    repair_activity_index: group_repair_activity,
                    repair_duration_minutes: group_repair_duration.unwrap_or(0),
                    source_path: format!("{path}.instances[{instance_index}]"),
                });
            }
            quantity
        };

        if instances.len() != quantity {
            bail!("invalid_instances at {path}.instances: instance count mismatch");
        }
        let (redundancy_kind, redundancy_k, redundancy_n) =
            parse_redundancy(item, &format!("{path}.redundancy"), quantity)?;
        raw_groups.push(ReliabilityRawGroup {
            group_id,
            component_type_id,
            name: {
                let name = text(item.get("name"));
                if name.is_empty() {
                    text(item.get("id"))
                } else {
                    name
                }
            },
            quantity,
            parent_id,
            parent_instance_id,
            instances,
            redundancy_kind,
            redundancy_k,
            redundancy_n,
            repair_activity_index: group_repair_activity,
            repair_duration_minutes: group_repair_duration.unwrap_or(0),
            aircraft_indexes: reliability_applies(item, aircraft),
            source_path: path,
        });
    }

    let group_indexes = raw_groups
        .iter()
        .enumerate()
        .map(|(index, group)| (group.group_id.clone(), index))
        .collect::<HashMap<_, _>>();
    for index in 0..raw_groups.len() {
        let parent_id = raw_groups[index].parent_id.clone();
        let parent_instance = raw_groups[index].parent_instance_id.clone();
        let source_path = raw_groups[index].source_path.clone();
        let Some(parent_id) = parent_id else {
            if parent_instance.is_some() {
                bail!(
                    "parent_instance_mismatch at {source_path}: parent_instance_id requires parent_id"
                );
            }
            continue;
        };
        let Some(parent_index) = group_indexes.get(&parent_id).copied() else {
            bail!("unknown_parent_group at {source_path}: unknown parent group");
        };
        let parent_instances = raw_groups[parent_index]
            .instances
            .iter()
            .map(|instance| instance.instance_id.clone())
            .collect::<Vec<_>>();
        if parent_instances.len() > 1 && parent_instance.is_none() {
            bail!(
                "ambiguous_parent_instance at {source_path}: parent_instance_id is required when the parent has multiple instances"
            );
        }
        let parent_instance_id = parent_instance
            .or_else(|| parent_instances.first().cloned())
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "unknown_parent_group at {source_path}: parent group has no instances"
                )
            })?;
        if !parent_instances.contains(&parent_instance_id) {
            bail!(
                "parent_instance_group_mismatch at {source_path}: parent_instance_id does not belong to the parent group"
            );
        }
        raw_groups[index].parent_instance_id = Some(parent_instance_id);
    }

    for group in &raw_groups {
        let mut seen = HashSet::<String>::new();
        let mut current = Some(group.group_id.clone());
        while let Some(id) = current {
            if !seen.insert(id.clone()) {
                bail!(
                    "cyclic_component_parent at {}: cyclic component parent groups are unsupported",
                    group.source_path
                );
            }
            current = raw_groups[group_indexes[&id]].parent_id.clone();
        }
    }

    let instance_indexes = raw_groups
        .iter()
        .flat_map(|group| group.instances.iter())
        .enumerate()
        .map(|(index, instance)| (instance.instance_id.clone(), index))
        .collect::<HashMap<_, _>>();
    let mut groups = Vec::with_capacity(raw_groups.len());
    let mut instances = Vec::with_capacity(instance_indexes.len());
    for (index, group) in raw_groups.iter().enumerate() {
        let parent_group_index = group
            .parent_id
            .as_ref()
            .and_then(|id| group_indexes.get(id))
            .map_or(-1, |value| *value as i64);
        let parent_instance_index = group
            .parent_instance_id
            .as_ref()
            .and_then(|id| instance_indexes.get(id))
            .map_or(-1, |value| *value as i64);
        groups.push(ReliabilityComponentGroupSpec {
            index,
            group_id: group.group_id.clone(),
            component_type_id: group.component_type_id.clone(),
            name: group.name.clone(),
            parent_group_index,
            aircraft_indexes: group.aircraft_indexes.clone(),
            quantity: group.quantity,
            redundancy_kind: group.redundancy_kind.clone(),
            redundancy_k: group.redundancy_k,
            redundancy_n: group.redundancy_n,
            repair_activity_index: group.repair_activity_index,
            repair_duration_minutes: group.repair_duration_minutes,
            source_path: group.source_path.clone(),
        });
        for instance in &group.instances {
            instances.push(ReliabilityComponentInstanceSpec {
                index: instances.len(),
                instance_template_id: instance.instance_id.clone(),
                group_index: index,
                parent_instance_index,
                failure_rate_per_hour: instance.failure_rate_per_hour,
                repair_activity_index: instance.repair_activity_index,
                repair_duration_minutes: instance.repair_duration_minutes,
                source_path: instance.source_path.clone(),
            });
        }
    }
    Ok((groups, instances))
}

fn compile_components(
    inputs: &Map<String, Value>,
    aircraft: &[AircraftSpec],
    activities: &[ActivitySpec],
) -> Result<Vec<ComponentSpec>> {
    let equipment = object(inputs.get("equipment_tree"))
        .cloned()
        .unwrap_or_default();
    let raw = array(equipment.get("components"))
        .iter()
        .filter_map(Value::as_object)
        .filter(|item| {
            item.get("id")
                .is_some_and(|value| !value.is_null() && !text(Some(value)).is_empty())
        })
        .collect::<Vec<_>>();
    let indexes = raw
        .iter()
        .enumerate()
        .map(|(index, item)| (text(item.get("id")), index))
        .collect::<HashMap<_, _>>();
    let generic_repairs = activities
        .iter()
        .filter(|item| item.kind == "repair" && item.equipment_component_index < 0)
        .collect::<Vec<_>>();
    raw.iter()
        .enumerate()
        .map(|(index, item)| -> Result<ComponentSpec> {
            let component_id = text(item.get("id"));
            let quantity = positive_usize(item.get("quantity"), 1).max(1);
            let distribution = object(item.get("failure_distribution"))
                .cloned()
                .unwrap_or_default();
            let rate = match distribution.get("mtbf") {
                Some(mtbf) => {
                    let mtbf = mtbf
                        .as_f64()
                        .ok_or_else(|| anyhow::anyhow!("MTBF must be a positive finite number"))?;
                    let rate = 1.0 / mtbf;
                    if !rate.is_finite() || rate <= 0.0 {
                        bail!("MTBF produces an invalid failure rate");
                    }
                    rate
                }
                None => failure_distribution_rate(&distribution).unwrap_or(0.0),
            };
            let applicable = aircraft
                .iter()
                .filter(|candidate| component_applies(&text(item.get("aircraft_model")), candidate))
                .map(|candidate| candidate.index)
                .collect::<Vec<_>>();
            let exact = activities
                .iter()
                .filter(|activity| {
                    activity.kind == "repair" && activity.equipment_component_index == index as i64
                })
                .map(|activity| activity.index)
                .collect::<Vec<_>>();
            let compatible = generic_repairs
                .iter()
                .filter(|activity| {
                    let activity_tokens = aircraft_tokens(&activity.aircraft_model);
                    activity_tokens.is_empty()
                        || applicable.iter().any(|aircraft_index| {
                            !activity_tokens.is_disjoint(&aircraft_tokens(
                                &aircraft[*aircraft_index].aircraft_type,
                            )) || !activity_tokens
                                .is_disjoint(&aircraft_tokens(&aircraft[*aircraft_index].model))
                        })
                })
                .map(|activity| activity.index)
                .collect::<Vec<_>>();
            let special = object(item.get("special_repair_profile"))
                .cloned()
                .unwrap_or_default();
            Ok(ComponentSpec {
                index,
                component_id: component_id.clone(),
                name: {
                    let value = text(item.get("name"));
                    if value.is_empty() {
                        component_id
                    } else {
                        value
                    }
                },
                parent_index: indexes
                    .get(&text(item.get("parent_id")))
                    .map_or(-1, |value| *value as i64),
                aircraft_indexes: applicable,
                product_id: first_non_empty(&[item.get("product_id"), item.get("spare_type")]),
                product_type: text(item.get("product_type")),
                quantity,
                failure_rate_per_hour: rate.max(0.0),
                failure_threshold: 1,
                repair_activity_index: exact
                    .first()
                    .or_else(|| compatible.first())
                    .map_or(-1, |value| *value as i64),
                repair_duration_minutes: positive_i64(special.get("repairTimeMinutes"), 0),
                source_path: format!("equipment_tree.components[{index}]"),
            })
        })
        .collect()
}

fn compile_preventive_cycles(
    inputs: &Map<String, Value>,
    activities: &[ActivitySpec],
) -> Result<Vec<PreventiveCycleSpec>> {
    let activity_indexes = activities
        .iter()
        .map(|item| (item.activity_id.as_str(), item.index))
        .collect::<HashMap<_, _>>();
    let aircraft = object(inputs.get("aircraft")).cloned().unwrap_or_default();
    let mut result = Vec::new();
    for (aircraft_index, value) in array(aircraft.get("assets")).iter().enumerate() {
        let Some(asset) = value.as_object() else {
            continue;
        };
        let fallback = object(asset.get("initial_life_state"))
            .cloned()
            .unwrap_or_default();
        for (cycle_index, value) in array(asset.get("preventive_cycles")).iter().enumerate() {
            let Some(cycle) = value.as_object() else {
                continue;
            };
            let activity_id = first_non_empty(&[cycle.get("activity_id"), cycle.get("activityId")]);
            let Some(activity_index) = activity_indexes.get(activity_id.as_str()).copied() else {
                bail!("unknown preventive activity {activity_id:?}");
            };
            let thresholds = object(cycle.get("thresholds")).cloned().unwrap_or_default();
            let life = object(cycle.get("initial_life_state")).unwrap_or(&fallback);
            result.push(PreventiveCycleSpec {
                index: result.len(),
                aircraft_index,
                activity_index,
                calendar_days: non_negative_i64(thresholds.get("calendar_days"), 0),
                flight_hours: non_negative_f64(thresholds.get("flight_hours"), 0.0),
                landing_cycles: non_negative_i64(thresholds.get("takeoff_landing_cycles"), 0),
                initial_calendar_days: non_negative_i64(life.get("calendar_days"), 0),
                initial_flight_hours: non_negative_f64(life.get("flight_hours"), 0.0),
                initial_landing_cycles: non_negative_i64(life.get("takeoff_landing_cycles"), 0),
                source_path: format!(
                    "aircraft.assets[{aircraft_index}].preventive_cycles[{cycle_index}]"
                ),
            });
        }
    }
    Ok(result)
}

fn compile_supply_routes(
    inputs: &Map<String, Value>,
    nodes: &[ResourceNodeSpec],
) -> Vec<SupplyRouteSpec> {
    let mut node_indexes = HashMap::<String, usize>::new();
    for node in nodes {
        node_indexes.insert(node.node_id.clone(), node.index);
        if !node.organization_node_id.is_empty() {
            node_indexes
                .entry(node.organization_node_id.clone())
                .or_insert(node.index);
        }
    }
    let network = object(inputs.get("support_network"))
        .cloned()
        .unwrap_or_default();
    let graph = object(network.get("organization_graph"))
        .cloned()
        .unwrap_or_default();
    let mut lateral = HashMap::<(String, String), String>::new();
    for (index, value) in array(graph.get("lateral_edges")).iter().enumerate() {
        let Some(edge) = value.as_object() else {
            continue;
        };
        if edge.get("enabled").and_then(Value::as_bool) == Some(false) {
            continue;
        }
        let source = first_non_empty(&[edge.get("from_node_id"), edge.get("from")]);
        let destination = first_non_empty(&[edge.get("to_node_id"), edge.get("to")]);
        if !source.is_empty() && !destination.is_empty() {
            let edge_id = {
                let value = text(edge.get("id"));
                if value.is_empty() {
                    format!("lateral-{}", index + 1)
                } else {
                    value
                }
            };
            lateral.insert((source, destination), edge_id);
        }
    }
    let mut groups = Vec::<(i64, Vec<&Value>, String)>::new();
    if !array(graph.get("transport_policies")).is_empty() {
        groups.push((
            -1,
            array(graph.get("transport_policies")).iter().collect(),
            "support_network.organization_graph.transport_policies".to_owned(),
        ));
    } else {
        for (node_index, value) in array(network.get("nodes")).iter().enumerate() {
            if let Some(node) = value.as_object() {
                groups.push((
                    node_index as i64,
                    array(node.get("transport_policies")).iter().collect(),
                    format!("support_network.nodes[{node_index}].transport_policies"),
                ));
            }
        }
    }
    let raw_nodes = array(network.get("nodes"));
    let mut routes = Vec::new();
    for (node_index, policies, source_prefix) in groups {
        for (policy_index, value) in policies.iter().enumerate() {
            let Some(policy) = value.as_object() else {
                continue;
            };
            let source_id = first_non_empty(&[
                policy.get("from_organization_node_id"),
                policy.get("fromOrganizationNodeId"),
                policy.get("from"),
                policy.get("from_node_id"),
            ]);
            let mut destination_id = first_non_empty(&[
                policy.get("to_organization_node_id"),
                policy.get("toOrganizationNodeId"),
                policy.get("to"),
                policy.get("to_node_id"),
            ]);
            if destination_id.is_empty() && node_index >= 0 {
                destination_id = raw_nodes
                    .get(node_index as usize)
                    .and_then(Value::as_object)
                    .map(|node| text(node.get("id")))
                    .unwrap_or_default();
            }
            let (Some(source_index), Some(destination_index)) = (
                node_indexes.get(&source_id).copied(),
                node_indexes.get(&destination_id).copied(),
            ) else {
                continue;
            };
            let relation_id = lateral
                .get(&(source_id, destination_id))
                .cloned()
                .unwrap_or_default();
            let transport_minutes = if policy
                .get("transport_minutes")
                .is_some_and(|value| !value.is_null() && !text(Some(value)).is_empty())
            {
                non_negative_i64(policy.get("transport_minutes"), 0)
            } else if policy
                .get("transportMinutes")
                .is_some_and(|value| !value.is_null() && !text(Some(value)).is_empty())
            {
                non_negative_i64(policy.get("transportMinutes"), 0)
            } else {
                (non_negative_f64(
                    policy
                        .get("transportTimeHours")
                        .or_else(|| policy.get("transport_time_hours")),
                    0.0,
                ) * 60.0)
                    .round_ties_even()
                    .max(0.0) as i64
            };
            let route_id = {
                let value = text(policy.get("id"));
                if value.is_empty() {
                    format!("route-{}-{}", node_index + 1, policy_index + 1)
                } else {
                    value
                }
            };
            routes.push(SupplyRouteSpec {
                index: routes.len(),
                route_id,
                source_node_index: source_index,
                destination_node_index: destination_index,
                product_id: first_non_empty(&[policy.get("product_id"), policy.get("spare_type")]),
                capacity: positive_i64(policy.get("capacity"), 1),
                transport_minutes,
                supply_mode: if relation_id.is_empty() {
                    "vertical"
                } else {
                    "lateral"
                }
                .to_owned(),
                relation_id,
                source_path: format!("{source_prefix}[{policy_index}]"),
            });
        }
    }
    routes
}

pub fn compile_aircraft_support(inputs: &Value) -> Result<ExecutionPlan> {
    compile_aircraft_support_with_profile(inputs, "legacy-minute-v1")
}

pub fn compile_aircraft_support_with_profile(
    inputs: &Value,
    semantic_profile: &str,
) -> Result<ExecutionPlan> {
    let business = crate::layers::import_business(inputs, semantic_profile)?;
    crate::layers::compile_core(&lower_business(&business)?)
}

fn core_provenance(business: &crate::layers::Artifact, aircraft: &[AircraftSpec]) -> Result<Value> {
    let assets = array(business.payload["sections"]["aircraft"]["collections"].get("assets"));
    let mut origins = serde_json::json!({"aircraft":{}, "preventive_cycles":{}});
    for (index, spec) in aircraft.iter().enumerate() {
        let entity = assets.get(index);
        let path = entity
            .and_then(|e| e["source_path"].as_str())
            .unwrap_or("aircraft.fleet_count");
        origins["aircraft"][&spec.tail_number] = serde_json::json!({"source_path":path});
        let cycles = entity
            .map(|e| array(e["definition"].get("preventive_cycles")))
            .unwrap_or_default();
        for (cycle_index, raw) in cycles.iter().enumerate() {
            let Some(cycle) = raw.as_object() else {
                continue;
            };
            let cycle_path = format!("aircraft.assets[{index}].preventive_cycles[{cycle_index}]");
            let explicit = ["id", "cycle_id"]
                .iter()
                .filter_map(|key| cycle.get(*key))
                .collect::<Vec<_>>();
            let key = if let Some(first) = explicit.first() {
                let Some(id) = first.as_str().filter(|v| !v.is_empty()) else {
                    bail!("{cycle_path}: cycle id must be a nonempty string");
                };
                if explicit.iter().any(|v| v.as_str() != Some(id)) {
                    bail!("{cycle_path}: conflicting cycle ids");
                }
                serde_json::json!(["id", id])
            } else {
                let Some(equipment) = cycle
                    .get("equipment_id")
                    .and_then(Value::as_str)
                    .filter(|v| !v.is_empty())
                else {
                    bail!("{cycle_path}: cycle requires id/cycle_id or stable equipment_id");
                };
                serde_json::json!(["equipment", equipment])
            };
            origins["preventive_cycles"][cycle_path] = serde_json::json!({
                "source_path":format!("{path}.preventive_cycles[{cycle_index}]"), "cycle_key":key});
        }
    }
    Ok(origins)
}

pub fn lower_business(business: &crate::layers::Artifact) -> Result<crate::layers::Artifact> {
    let view = crate::layers::canonical_view(business)?;
    let inputs = &view;
    let semantic_profile = business.payload["semantic_profile"].as_str().unwrap();
    let Some(inputs) = inputs.as_object() else {
        bail!("canonical inputs must be a JSON object");
    };
    if text(inputs.get("schema_version")) != "aircraft-support-v1-input-v1" {
        bail!("unsupported canonical input schema");
    }
    if text(inputs.get("operations_support_policy")) != "daily-v1" {
        bail!("B1 requires operations_support_policy=daily-v1");
    }
    let time = object(inputs.get("time")).cloned().unwrap_or_default();
    if !matches!(semantic_profile, "legacy-minute-v1" | "event-time-v2") {
        bail!("unsupported time profile {semantic_profile:?}");
    }
    if positive_i64(time.get("tick_minutes"), 1) != 1 {
        bail!("{semantic_profile} requires tick_minutes=1");
    }
    validation::validate_canonical_work(inputs)?;
    let duration_minutes = positive_i64(time.get("duration_minutes"), 1440);
    let stop_policy = object(inputs.get("stop_policy"));
    let stop_conditions = stop_policy
        .map(|policy| array(policy.get("conditions")))
        .unwrap_or_default();
    let natural_completion_enabled = stop_policy
        .and_then(|policy| policy.get("defaulted"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
        || !stop_conditions.iter().any(|condition| {
            matches!(
                text(condition.get("type")).as_str(),
                "duration" | "specified_time"
            )
        });
    let aircraft = compile_aircraft(inputs)?;
    let resource_nodes = compile_nodes(inputs)?;
    let equipment = object(inputs.get("equipment_tree"))
        .cloned()
        .unwrap_or_default();
    let component_indexes = array(equipment.get("components"))
        .iter()
        .enumerate()
        .filter_map(|(index, value)| {
            let item = value.as_object()?;
            let id = text(item.get("id"));
            (!id.is_empty()).then_some((id, index))
        })
        .collect::<HashMap<_, _>>();
    let fused_reliability = is_reliability_input(inputs);
    let (groups, instances) = if fused_reliability {
        build_reliability_plan_records(inputs, &aircraft)?
    } else {
        (Vec::new(), Vec::new())
    };
    let mut activities = compile_activities(inputs, &resource_nodes, &component_indexes)?;
    if fused_reliability {
        for activity in &mut activities {
            activity.equipment_component_index = -1;
        }
    }
    let missions = compile_missions(inputs, duration_minutes);
    let components = if fused_reliability {
        Vec::new()
    } else {
        compile_components(inputs, &aircraft, &activities)?
    };
    let preventive_cycles = compile_preventive_cycles(inputs, &activities)?;
    let supply_routes = compile_supply_routes(inputs, &resource_nodes);

    let provenance = core_provenance(business, &aircraft)?;
    let mut records = serde_json::json!({
        "domain": "aircraft-support", "semantic_profile": semantic_profile,
        "work_policy": "stable-topological-serial", "rng_profile": "legacy-sequential-v1",
        "duration_minutes": duration_minutes, "natural_completion_enabled": natural_completion_enabled,
        "phases": LEGACY_MINUTE_PHASES, "aircraft": aircraft, "missions": missions,
        "activities": activities, "resource_nodes": resource_nodes, "components": components,
        "preventive_cycles": preventive_cycles, "supply_routes": supply_routes,
        "unsupported_features": []
    });
    if fused_reliability {
        let records = records.as_object_mut().unwrap();
        records.insert("component_groups".into(), serde_json::to_value(groups)?);
        records.insert(
            "component_instances".into(),
            serde_json::to_value(instances)?,
        );
        records.insert(
            "reliability_policy".into(),
            serde_json::json!(RELIABILITY_POLICY),
        );
    }
    crate::layers::core_from_records(business, records, provenance)
}

#[cfg(test)]
mod tests {
    use std::{fs, path::PathBuf};

    use super::*;

    fn root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
    }

    #[test]
    fn shared_python_rust_work_input_contract() {
        let base: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/b1-daily-operations.json")).unwrap(),
        )
        .unwrap();
        let cases: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/work-input-validation.json")).unwrap(),
        )
        .unwrap();
        for case in cases.as_array().unwrap() {
            for profile in ["legacy-minute-v1", "event-time-v2"] {
                let mut inputs = base.clone();
                let mut target = &mut inputs;
                let mut path = String::new();
                for part in case["path"].as_array().unwrap() {
                    if let Some(index) = part.as_u64() {
                        target = &mut target[index as usize];
                        path.push_str(&format!("[{index}]"));
                    } else {
                        let key = part.as_str().unwrap();
                        target = &mut target[key];
                        if !path.is_empty() {
                            path.push('.');
                        }
                        path.push_str(key);
                    }
                }
                *target = case["value"].clone();
                let compiled = compile_aircraft_support_with_profile(&inputs, profile);
                if let Some(expected) = case["error"].as_str() {
                    let error = compiled.unwrap_err();
                    let diagnostic = error
                        .downcast_ref::<validation::CompilationDiagnostic>()
                        .unwrap();
                    assert_eq!(diagnostic.code, expected, "{}", case["name"]);
                    assert_eq!(diagnostic.source_path, path);
                } else {
                    let plan = compiled.unwrap();
                    if let Some(expected) = case["expected_minutes"].as_i64() {
                        assert_eq!(
                            plan.activities[0].steps[0].duration_minutes, expected,
                            "{}",
                            case["name"]
                        );
                    }
                    if let Some(expected) = case["expected_component"].as_i64() {
                        assert_eq!(plan.activities[0].equipment_component_index, expected);
                    }
                }
            }
        }
    }

    fn assert_matches_python_fixture(input: &str, expected: &str) {
        let inputs: Value = serde_json::from_slice(&fs::read(root().join(input)).unwrap()).unwrap();
        let expected: Value =
            serde_json::from_slice(&fs::read(root().join(expected)).unwrap()).unwrap();
        let actual = serde_json::to_value(compile_aircraft_support(&inputs).unwrap()).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(
            ExecutionPlan::fingerprint(&actual).unwrap(),
            ExecutionPlan::fingerprint(&expected).unwrap()
        );
    }

    #[test]
    fn matches_python_plans_for_all_checked_in_contract_fixtures() {
        for (input, expected) in [
            (
                "tests/fixtures/synthetic/b1-daily-operations.json",
                "tests/fixtures/synthetic/b1-execution-plan.json",
            ),
            (
                "tests/fixtures/synthetic/b2-failure-repair.json",
                "tests/fixtures/synthetic/b2-failure-repair-execution-plan.json",
            ),
            (
                "tests/fixtures/synthetic/b2-preventive-maintenance.json",
                "tests/fixtures/synthetic/b2-preventive-maintenance-execution-plan.json",
            ),
            (
                "tests/fixtures/synthetic/b3-upstream-transport.json",
                "tests/fixtures/synthetic/b3-upstream-transport-execution-plan.json",
            ),
            (
                "tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json",
                "tests/fixtures/spare_mvp/f35-43day-5352a0d/execution-plan.json",
            ),
            (
                "tests/fixtures/reliability/r1-fused-input.json",
                "tests/fixtures/reliability/r1-fused-input-plan.json",
            ),
        ] {
            assert_matches_python_fixture(input, expected);
        }
    }

    fn fused_reliability_input() -> Value {
        let mut inputs: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/b2-failure-repair.json")).unwrap(),
        )
        .unwrap();
        inputs["equipment_tree"]["components"] = serde_json::json!([
            {
                "id": "f35",
                "component_type_id": "airframe",
                "name": "F35",
                "aircraft_model": "F35",
                "instances": [{"instance_id": "f35-1"}]
            },
            {
                "id": "radar-lru",
                "component_type_id": "radar-lru",
                "name": "Radar LRU",
                "aircraft_model": "F35",
                "parent_id": "f35",
                "parent_instance_id": "f35-1",
                "instances": [
                    {
                        "instance_id": "radar-a",
                        "failure_rate_per_hour": 0.5,
                        "repair_profile": {
                            "repair_activity_index": 0,
                            "repair_duration_minutes": 10
                        }
                    },
                    {
                        "instance_id": "radar-b",
                        "failure_rate_per_hour": 0.25,
                        "repair_profile": {
                            "repair_activity_index": 0,
                            "repair_duration_minutes": 20
                        }
                    }
                ],
                "redundancy": {"kind": "k_out_of_n", "k": 1, "n": 2}
            }
        ]);
        inputs
    }

    #[test]
    fn fused_reliability_compiles_groups_instances_and_parent_mapping() {
        let plan = compile_aircraft_support(&fused_reliability_input()).unwrap();

        assert_eq!(plan.reliability_policy.as_deref(), Some(RELIABILITY_POLICY));
        assert!(plan.components.is_empty());
        assert_eq!(plan.component_groups.len(), 2);
        assert_eq!(plan.component_instances.len(), 3);
        assert_eq!(plan.component_groups[0].redundancy_kind, "series");
        assert_eq!(plan.component_groups[0].redundancy_k, 0);
        assert_eq!(plan.component_groups[0].redundancy_n, 1);
        assert_eq!(plan.component_groups[1].redundancy_kind, "k_out_of_n");
        assert_eq!(plan.component_groups[1].redundancy_k, 1);
        assert_eq!(plan.component_groups[1].redundancy_n, 2);
        assert_eq!(plan.component_groups[1].parent_group_index, 0);
        assert_eq!(plan.component_instances[1].parent_instance_index, 0);
        assert_eq!(plan.component_instances[2].parent_instance_index, 0);
        assert_eq!(plan.component_instances[1].failure_rate_per_hour, 0.5);
        assert_eq!(plan.component_instances[2].failure_rate_per_hour, 0.25);
        assert_eq!(plan.component_instances[1].repair_duration_minutes, 10);
        assert_eq!(plan.component_instances[2].repair_duration_minutes, 20);
        assert!(
            plan.activities
                .iter()
                .all(|activity| activity.equipment_component_index == -1)
        );
    }

    #[test]
    fn fused_reliability_defaults_to_series_for_generated_instances() {
        let mut inputs = fused_reliability_input();
        inputs["equipment_tree"]["components"][1] = serde_json::json!({
            "id": "radar-lru",
            "component_type_id": "radar-lru",
            "aircraft_model": "F35",
            "parent_id": "f35",
            "quantity": 2,
            "failure_rate_per_hour": 0.75
        });
        let plan = compile_aircraft_support(&inputs).unwrap();
        let group = &plan.component_groups[1];
        assert_eq!(group.redundancy_kind, "series");
        assert_eq!(group.redundancy_k, 0);
        assert_eq!(group.redundancy_n, 2);
        assert_eq!(
            plan.component_instances
                .iter()
                .filter(|instance| instance.group_index == 1)
                .map(|instance| instance.instance_template_id.as_str())
                .collect::<Vec<_>>(),
            ["radar-lru-0", "radar-lru-1"]
        );
    }

    #[test]
    fn fused_reliability_accepts_legacy_k_out_alias_and_mtbf() {
        let mut inputs = fused_reliability_input();
        inputs["equipment_tree"]["components"][1] = serde_json::json!({
            "id": "radar-lru",
            "component_type_id": "radar-lru",
            "aircraft_model": "F35",
            "parent_id": "f35",
            "quantity": 2,
            "failure_distribution": {
                "distributionType": "exponential",
                "mtbf": 2,
                "timeUnit": "hour",
                "timeBasis": "flight_hour"
            },
            "k_out_of_n": {"enabled": true, "k": 1, "n": 2}
        });
        let plan = compile_aircraft_support(&inputs).unwrap();
        assert_eq!(plan.component_groups[1].redundancy_kind, "k_out_of_n");
        assert_eq!(plan.component_groups[1].redundancy_k, 1);
        assert_eq!(
            plan.component_instances
                .iter()
                .filter(|instance| instance.group_index == 1)
                .map(|instance| instance.failure_rate_per_hour)
                .collect::<Vec<_>>(),
            [0.5, 0.5]
        );
    }

    #[test]
    fn fused_reliability_rejects_direct_and_nested_failure_threshold() {
        let mut inputs = fused_reliability_input();
        inputs["equipment_tree"]["components"][1]["failure_threshold"] = Value::from(2);
        let error = compile_aircraft_support(&inputs).unwrap_err();
        let diagnostic = error
            .downcast_ref::<validation::CompilationDiagnostic>()
            .unwrap();
        assert_eq!(diagnostic.code, "failure_threshold_in_new_plan");

        let mut inputs = fused_reliability_input();
        inputs["equipment_tree"]["components"][1]["instances"][0]["failure_threshold"] =
            Value::from(2);
        assert!(compile_aircraft_support(&inputs).is_err());
    }

    #[test]
    fn legacy_and_mixed_inputs_reject_failure_threshold() {
        let mut inputs: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/b2-failure-repair.json")).unwrap(),
        )
        .unwrap();
        inputs["equipment_tree"]["components"][1]["failure_threshold"] = Value::from(2);
        let error = compile_aircraft_support(&inputs).unwrap_err();
        let diagnostic = error
            .downcast_ref::<validation::CompilationDiagnostic>()
            .unwrap();
        assert_eq!(diagnostic.code, "failure_threshold_in_new_plan");
        assert_eq!(
            diagnostic.source_path,
            "equipment_tree.components[1].failure_threshold"
        );

        let mut mixed: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/b2-failure-repair.json")).unwrap(),
        )
        .unwrap();
        mixed["equipment_tree"]["components"][1]["component_type_id"] = Value::from("radar-lru");
        let error = compile_aircraft_support(&mixed).unwrap_err();
        let diagnostic = error
            .downcast_ref::<validation::CompilationDiagnostic>()
            .unwrap();
        assert_eq!(diagnostic.code, "component_type_missing");
        assert_eq!(
            diagnostic.source_path,
            "equipment_tree.components[0].component_type_id"
        );

        let mut nested: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/b2-failure-repair.json")).unwrap(),
        )
        .unwrap();
        nested["equipment_tree"]["components"][0]["component_type_id"] = Value::from("f35");
        nested["equipment_tree"]["components"][1]["component_type_id"] = Value::from("radar-lru");
        nested["equipment_tree"]["components"][1]["instances"] =
            serde_json::json!([{"instance_id": "radar-0", "failure_threshold": 2}]);
        let error = compile_aircraft_support(&nested).unwrap_err();
        let diagnostic = error
            .downcast_ref::<validation::CompilationDiagnostic>()
            .unwrap();
        assert_eq!(diagnostic.code, "failure_threshold_in_new_plan");
        assert_eq!(
            diagnostic.source_path,
            "equipment_tree.components[1].instances[0].failure_threshold"
        );
    }

    #[test]
    fn rejects_unknown_schema_and_tick_profile() {
        let mut inputs: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/b1-daily-operations.json")).unwrap(),
        )
        .unwrap();
        inputs["schema_version"] = Value::String("unknown".to_owned());
        assert!(compile_aircraft_support(&inputs).is_err());
        inputs["schema_version"] = Value::String("aircraft-support-v1-input-v1".to_owned());
        inputs["time"]["tick_minutes"] = Value::from(5);
        assert!(compile_aircraft_support(&inputs).is_err());
    }

    #[test]
    fn event_time_profile_changes_only_versioned_plan_identity() {
        let inputs: Value = serde_json::from_slice(
            &fs::read(
                root().join("tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json"),
            )
            .unwrap(),
        )
        .unwrap();
        let legacy = compile_aircraft_support(&inputs).unwrap();
        let event = compile_aircraft_support_with_profile(&inputs, "event-time-v2").unwrap();
        let mut legacy_value = serde_json::to_value(&legacy).unwrap();
        let event_value = serde_json::to_value(&event).unwrap();
        legacy_value["semantic_profile"] = Value::String("event-time-v2".to_owned());
        assert_eq!(legacy_value, event_value);
        assert_ne!(
            ExecutionPlan::fingerprint(&serde_json::to_value(legacy).unwrap()).unwrap(),
            ExecutionPlan::fingerprint(&event_value).unwrap(),
        );
    }

    #[test]
    fn activity_resource_defaults_override_task_lists_like_spare_mvp() {
        let inputs: Value = serde_json::from_slice(
            &fs::read(
                root().join("tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json"),
            )
            .unwrap(),
        )
        .unwrap();
        let plan = compile_aircraft_support(&inputs).unwrap();
        let activity = plan
            .activities
            .iter()
            .find(|item| item.activity_id == "f35-service-0103")
            .unwrap();

        assert!(
            activity
                .steps
                .iter()
                .all(|step| step.personnel == 1 && step.equipment == 1)
        );
    }

    #[test]
    fn compiles_natural_completion_only_without_explicit_temporal_blocking() {
        let f35: Value = serde_json::from_slice(
            &fs::read(
                root().join("tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json"),
            )
            .unwrap(),
        )
        .unwrap();
        let explicit_duration: Value = serde_json::from_slice(
            &fs::read(root().join("tests/fixtures/synthetic/b1-daily-operations.json")).unwrap(),
        )
        .unwrap();

        assert!(
            compile_aircraft_support(&f35)
                .unwrap()
                .natural_completion_enabled
        );
        assert!(
            !compile_aircraft_support(&explicit_duration)
                .unwrap()
                .natural_completion_enabled
        );
    }
}
