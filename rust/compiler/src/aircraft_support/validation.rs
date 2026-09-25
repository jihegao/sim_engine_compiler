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

pub fn validate_canonical_work(inputs: &Map<String, Value>) -> Result<()> {
    let components = object(inputs.get("equipment_tree"));
    let ids: HashSet<String> = array(components.and_then(|v| v.get("components")))
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
