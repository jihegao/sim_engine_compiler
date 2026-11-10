//! The scoped work-input contract shared with the Python domain validator.

use std::{collections::HashSet, error::Error, fmt};

use anyhow::Result;
use serde_json::{Map, Value};

use super::{array, object, text};

#[derive(Debug)]
pub struct CompilationDiagnostic {
    pub code: &'static str,
    pub source_path: String,
    pub message: String,
}

impl fmt::Display for CompilationDiagnostic {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} at {}: {}", self.code, self.source_path, self.message)
    }
}

impl Error for CompilationDiagnostic {}

fn reject(code: &'static str, path: String, message: impl Into<String>) -> anyhow::Error {
    CompilationDiagnostic {
        code,
        source_path: path,
        message: message.into(),
    }
    .into()
}

fn duration(value: Option<&Value>, path: String) -> Result<()> {
    let Some(value) = value.filter(|v| !v.is_null()) else {
        return Ok(());
    };
    let parsed = match value {
        Value::String(raw) => serde_json::from_str::<Value>(raw.trim()).ok(),
        _ => Some(value.clone()),
    };
    let number = parsed
        .as_ref()
        .and_then(Value::as_f64)
        .filter(|v| v.is_finite())
        .ok_or_else(|| {
            reject(
                "invalid_duration_type",
                path.clone(),
                "expected finite numeric minutes (unit text is not supported)",
            )
        })?;
    if number < 0.0 {
        return Err(reject(
            "negative_duration",
            path,
            "duration must be nonnegative",
        ));
    }
    if number >= 2_f64.powi(63) {
        return Err(reject(
            "duration_out_of_range",
            path,
            "duration exceeds supported integer minutes",
        ));
    }
    Ok(())
}

fn failure_distribution(value: Option<&Value>, path: String) -> Result<()> {
    let Some(value) = value.filter(|v| !v.is_null()) else {
        return Ok(());
    };
    let Some(distribution) = value.as_object() else {
        return Err(reject(
            "invalid_failure_distribution",
            path,
            "expected failure distribution object",
        ));
    };
    if distribution.is_empty() {
        return Ok(());
    }

    let raw_type = distribution
        .get("distributionType")
        .filter(|value| !value.is_null())
        .or_else(|| distribution.get("distribution_type"));
    if raw_type.is_some_and(|value| !value.is_string()) {
        return Err(reject(
            "unsupported_failure_distribution",
            path,
            "failure distribution type must be a string",
        ));
    }
    let distribution_type = raw_type
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_lowercase();
    if let Some(mtbf_value) = distribution.get("mtbf") {
        if !matches!(distribution_type.as_str(), "exponential" | "指数分布") {
            return Err(reject(
                "unsupported_failure_distribution",
                path,
                "MTBF is currently supported only for the exponential distribution",
            ));
        }
        let mtbf = mtbf_value
            .as_f64()
            .filter(|value| value.is_finite() && *value > 0.0)
            .ok_or_else(|| {
                reject(
                    "invalid_mtbf",
                    format!("{path}.mtbf"),
                    "MTBF must be a positive finite number",
                )
            })?;
        if distribution.get("timeUnit").is_none() {
            return Err(reject(
                "missing_failure_time_unit",
                format!("{path}.timeUnit"),
                "MTBF timeUnit is required",
            ));
        }
        if distribution.get("timeUnit").and_then(Value::as_str) != Some("hour") {
            return Err(reject(
                "unsupported_failure_time_unit",
                format!("{path}.timeUnit"),
                "aircraft-support MTBF timeUnit must be 'hour'",
            ));
        }
        if distribution.get("timeBasis").is_none() {
            return Err(reject(
                "missing_failure_time_basis",
                format!("{path}.timeBasis"),
                "aircraft-support MTBF timeBasis is required",
            ));
        }
        if distribution.get("timeBasis").and_then(Value::as_str) != Some("flight_hour") {
            return Err(reject(
                "unsupported_failure_time_basis",
                format!("{path}.timeBasis"),
                "aircraft-support MTBF timeBasis must be 'flight_hour'",
            ));
        }
        if !(1.0 / mtbf).is_finite() {
            return Err(reject(
                "invalid_mtbf",
                format!("{path}.mtbf"),
                "MTBF is outside the supported numeric range",
            ));
        }
    } else if !distribution_type.is_empty()
        && ![
            "exponential",
            "指数",
            "weibull",
            "威布尔",
            "normal",
            "正态",
            "uniform",
            "均匀",
            "fixed",
            "固定",
        ]
        .iter()
        .any(|kind| distribution_type.contains(kind))
    {
        return Err(reject(
            "unsupported_failure_distribution",
            path,
            format!("unsupported failure distribution {distribution_type:?}"),
        ));
    }
    Ok(())
}

pub fn validate_canonical_work(inputs: &Map<String, Value>) -> Result<()> {
    let components = object(inputs.get("equipment_tree"));
    let component_rows = array(components.and_then(|v| v.get("components")));
    for (index, component) in component_rows.iter().enumerate() {
        if let Some(component) = component.as_object() {
            if let Some(redundancy) = component
                .get("k_out_of_n")
                .filter(|value| !value.is_null())
            {
                let path = format!("equipment_tree.components[{index}].k_out_of_n");
                let Some(redundancy) = redundancy.as_object() else {
                    return Err(reject(
                        "invalid_k_out_of_n",
                        path,
                        "k_out_of_n must be an object with a boolean enabled field",
                    ));
                };
                let Some(enabled) = redundancy.get("enabled").and_then(Value::as_bool) else {
                    return Err(reject(
                        "invalid_k_out_of_n",
                        path,
                        "k_out_of_n must be an object with a boolean enabled field",
                    ));
                };
                if enabled {
                    return Err(reject(
                        "unsupported_k_out_of_n",
                        path,
                        "aircraft-support k_out_of_n is not supported",
                    ));
                }
            }
            failure_distribution(
                component.get("failure_distribution"),
                format!("equipment_tree.components[{index}].failure_distribution"),
            )?;
        }
    }
    let ids: HashSet<String> = component_rows
        .iter()
        .filter_map(Value::as_object)
        .filter_map(|v| v.get("id"))
        .filter(|v| !v.is_null())
        .map(|v| text(Some(v)))
        .filter(|v| !v.is_empty())
        .collect();
    let support = object(inputs.get("support_activities"));
    for (index, value) in array(support.and_then(|v| v.get("activities")))
        .iter()
        .enumerate()
    {
        let Some(activity) = value.as_object() else {
            continue;
        };
        let path = format!("support_activities.activities[{index}]");
        duration(
            activity.get("duration_minutes"),
            format!("{path}.duration_minutes"),
        )?;
        if let Some(reference) = activity
            .get("equipment_id")
            .filter(|v| !v.is_null() && **v != "")
        {
            if !reference.as_str().is_some_and(|id| ids.contains(id)) {
                return Err(reject(
                    "unresolved_component_reference",
                    format!("{path}.equipment_id"),
                    format!(
                        "activity {:?} has unresolved component reference {reference}",
                        text(activity.get("id"))
                    ),
                ));
            }
        }
        for (job_index, value) in array(activity.get("jobs")).iter().enumerate() {
            if let Some(job) = value.as_object() {
                for field in ["durationMinutes", "duration_minutes"] {
                    duration(job.get(field), format!("{path}.jobs[{job_index}].{field}"))?;
                }
            }
        }
    }
    Ok(())
}
