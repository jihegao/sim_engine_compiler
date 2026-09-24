//! Domain lowering for canonical `aircraft-support-v1-input-v1` documents.

use std::collections::{BTreeMap, HashMap, HashSet};

use anyhow::{Result, bail};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use sim_engine_runtime::plan::{
    ActivitySpec, AircraftSpec, ComponentSpec, ExecutionPlan, MissionSpec, PLAN_VERSION,
    PreventiveCycleSpec, ResourceNodeSpec, SupplyRouteSpec, WorkStepSpec,
};

pub const COMPILER_VERSION: &str = "aircraft-support-aot/v1alpha2";

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
    let default_duration = positive_i64(item.get("duration_minutes"), 30);
    Ok(ordered
        .iter()
        .enumerate()
        .map(|(index, source)| {
            let step = raw_steps[*source];
            WorkStepSpec {
                index,
                code: codes[*source].clone(),
                duration_minutes: positive_i64(
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

fn compile_components(
    inputs: &Map<String, Value>,
    aircraft: &[AircraftSpec],
    activities: &[ActivitySpec],
) -> Vec<ComponentSpec> {
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
        .map(|(index, item)| {
            let component_id = text(item.get("id"));
            let quantity = positive_usize(item.get("quantity"), 1).max(1);
            let distribution = object(item.get("failure_distribution"))
                .cloned()
                .unwrap_or_default();
            let mut rate = failure_distribution_rate(&distribution).unwrap_or(0.0);
            let k_out = object(item.get("k_out_of_n")).cloned().unwrap_or_default();
            let enabled = k_out
                .get("enabled")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            if enabled {
                let k = positive_usize(k_out.get("k"), 1).max(1);
                let n = positive_usize(k_out.get("n"), k).max(k);
                rate /= (n - k + 1).max(1) as f64;
            }
            rate *= (quantity as f64).sqrt().max(1.0);
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
            ComponentSpec {
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
                failure_threshold: if enabled {
                    positive_usize(k_out.get("k"), 1).max(1)
                } else {
                    1
                },
                repair_activity_index: exact
                    .first()
                    .or_else(|| compatible.first())
                    .map_or(-1, |value| *value as i64),
                repair_duration_minutes: positive_i64(special.get("repairTimeMinutes"), 0),
                source_path: format!("equipment_tree.components[{index}]"),
            }
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
    let activities = compile_activities(inputs, &resource_nodes, &component_indexes)?;
    let missions = compile_missions(inputs, duration_minutes);
    let components = compile_components(inputs, &aircraft, &activities);
    let preventive_cycles = compile_preventive_cycles(inputs, &activities)?;
    let supply_routes = compile_supply_routes(inputs, &resource_nodes);

    let canonical = ExecutionPlan::python_canonical(&Value::Object(inputs.clone()))?;
    let plan = ExecutionPlan {
        plan_version: PLAN_VERSION.to_owned(),
        domain: "aircraft-support".to_owned(),
        semantic_profile: semantic_profile.to_owned(),
        work_policy: "stable-topological-serial".to_owned(),
        rng_profile: "legacy-sequential-v1".to_owned(),
        source_inputs_sha256: format!("{:x}", Sha256::digest(canonical.as_bytes())),
        duration_minutes,
        natural_completion_enabled,
        phases: LEGACY_MINUTE_PHASES
            .iter()
            .map(|value| (*value).to_owned())
            .collect(),
        aircraft,
        missions,
        activities,
        resource_nodes,
        components,
        preventive_cycles,
        supply_routes,
        resource_dispatch_index: None,
        unsupported_features: Vec::new(),
    };
    plan.validate()?;
    Ok(plan)
}

#[cfg(test)]
mod tests {
    use std::{fs, path::PathBuf};

    use super::*;

    fn root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
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
        ] {
            assert_matches_python_fixture(input, expected);
        }
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
