use std::{
    collections::HashSet,
    fs,
    path::{Path, PathBuf},
    str::FromStr,
    sync::Arc,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use clap::Parser;
use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use sim_engine_runtime::{ExecutionPlan, ObservationLevel, RunResult, Runtime};

mod benchmark_support;

use benchmark_support::{BuildIdentity, build_identity};

const LEGACY_PROFILE: &str = "legacy-minute-v1";
const EVENT_PROFILE: &str = "event-time-v2";
const NORMALIZED_PROFILE: &str = "paired-time-profile";

#[derive(Parser)]
#[command(about = "Pair legacy-minute-v1 and event-time-v2 in one benchmark binary")]
struct Args {
    legacy_plan: PathBuf,
    event_plan: PathBuf,
    output: PathBuf,
    #[arg(long, default_value = "0,1,7")]
    seeds: String,
    #[arg(long, default_value = "full,summary")]
    observation_levels: String,
    #[arg(long, default_value_t = 1)]
    warmups: usize,
    #[arg(long, default_value_t = 6)]
    repeats: usize,
    #[arg(long)]
    until: Option<i64>,
    #[arg(long)]
    session_label: String,
    #[arg(long, value_name = "PATH")]
    source_diff: Option<PathBuf>,
    #[arg(long, value_name = "PATH")]
    host_manifest: Option<PathBuf>,
}

#[derive(Serialize)]
struct PlanIdentity {
    path: String,
    bytes: usize,
    file_sha256: String,
    plan_fingerprint: String,
    semantic_profile: String,
}

#[derive(Serialize)]
struct RunMeasurement {
    time_profile: &'static str,
    order: usize,
    execution_ns: u64,
    result_bytes: usize,
    trace_events: usize,
    result_sha256: String,
    business_result_sha256: String,
    sample_requests_sha256: String,
    trace_sha256: String,
    metrics_sha256: String,
    terminal_state_sha256: String,
    result_time: i64,
    result_stop_reason: String,
    result_plan_fingerprint: String,
    result_seed: u64,
}

#[derive(Serialize)]
struct PairRecord {
    observation_level: ObservationLevel,
    seed: u64,
    repeat: usize,
    first_profile: &'static str,
    legacy: RunMeasurement,
    event_time: RunMeasurement,
    business_equivalent: bool,
    legacy_to_event_ratio: f64,
    event_improvement_pct: f64,
}

#[derive(Serialize)]
struct BenchmarkReport {
    schema_version: &'static str,
    generated_at_unix_seconds: u64,
    session_label: String,
    build: BuildIdentity,
    legacy_plan: PlanIdentity,
    event_plan: PlanIdentity,
    paired_model_sha256: String,
    source_inputs_sha256: String,
    plan_version: String,
    work_policy: String,
    rng_profile: String,
    duration_minutes: i64,
    until: Option<i64>,
    seeds: Vec<u64>,
    observation_levels: Vec<ObservationLevel>,
    warmups: usize,
    repeats: usize,
    records: Vec<PairRecord>,
}

struct LoadedPlan {
    bytes: Vec<u8>,
    raw: Value,
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
}

fn digest<T: Serialize>(value: &T) -> Result<String> {
    Ok(format!("{:x}", Sha256::digest(serde_json::to_vec(value)?)))
}

fn parse_seeds(value: &str) -> Result<Vec<u64>> {
    let seeds = value
        .split(',')
        .map(str::trim)
        .filter(|item| !item.is_empty())
        .map(str::parse)
        .collect::<std::result::Result<Vec<_>, _>>()?;
    if seeds.is_empty() {
        bail!("at least one seed is required");
    }
    Ok(seeds)
}

fn parse_observation_levels(value: &str) -> Result<Vec<ObservationLevel>> {
    let levels = value
        .split(',')
        .map(str::trim)
        .filter(|item| !item.is_empty())
        .map(ObservationLevel::from_str)
        .collect::<Result<Vec<_>>>()?;
    if levels.is_empty() {
        bail!("at least one observation level is required");
    }
    let mut unique = HashSet::new();
    for level in &levels {
        let name = match level {
            ObservationLevel::Full => "full",
            ObservationLevel::Summary => "summary",
        };
        if !unique.insert(name) {
            bail!("duplicate observation level {name:?}");
        }
    }
    Ok(levels)
}

fn validate_run_counts(warmups: usize, repeats: usize) -> Result<()> {
    if warmups == 0 {
        bail!("warmups must be greater than zero");
    }
    if repeats == 0 {
        bail!("repeats must be greater than zero");
    }
    Ok(())
}

fn legacy_runs_first(observation_index: usize, seed_index: usize, iteration: usize) -> bool {
    (observation_index + seed_index + iteration).is_multiple_of(2)
}

fn load_plan(path: &Path, expected_profile: &str) -> Result<LoadedPlan> {
    let bytes = fs::read(path).with_context(|| format!("read plan {}", path.display()))?;
    let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
    if plan.semantic_profile != expected_profile {
        bail!(
            "plan {} has semantic profile {:?}; expected {expected_profile:?}",
            path.display(),
            plan.semantic_profile
        );
    }
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    Ok(LoadedPlan {
        bytes,
        raw,
        plan: Arc::new(plan),
        fingerprint,
    })
}

fn normalized_plan(raw: &Value) -> Result<Value> {
    let mut normalized = raw.clone();
    let object = normalized
        .as_object_mut()
        .context("execution plan JSON must be an object")?;
    object.insert(
        "semantic_profile".into(),
        Value::String(NORMALIZED_PROFILE.into()),
    );
    Ok(normalized)
}

fn assert_matching_field<T: PartialEq>(field: &str, legacy: &T, event_time: &T) -> Result<()> {
    if legacy != event_time {
        bail!("time profile changed result field {field}");
    }
    Ok(())
}

fn assert_business_equivalence(
    observation_level: ObservationLevel,
    legacy: &RunResult,
    event_time: &RunResult,
) -> Result<()> {
    assert_matching_field("seed", &legacy.seed, &event_time.seed)?;
    assert_matching_field("time", &legacy.time, &event_time.time)?;
    assert_matching_field("stop_reason", &legacy.stop_reason, &event_time.stop_reason)?;
    assert_matching_field(
        "sample_requests",
        &legacy.sample_requests,
        &event_time.sample_requests,
    )?;
    assert_matching_field("trace", &legacy.trace, &event_time.trace)?;
    assert_matching_field("metrics", &legacy.metrics, &event_time.metrics)?;
    assert_matching_field(
        "terminal_state",
        &legacy.terminal_state,
        &event_time.terminal_state,
    )?;
    if observation_level == ObservationLevel::Summary
        && (!legacy.trace.is_empty() || !event_time.trace.is_empty())
    {
        bail!("summary results must have empty traces");
    }
    Ok(())
}

fn business_result_sha256(result: &RunResult) -> Result<String> {
    let mut value = serde_json::to_value(result)?;
    value
        .as_object_mut()
        .context("serialized run result must be an object")?
        .remove("plan_fingerprint");
    digest(&value)
}

fn run_one(
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    time_profile: &'static str,
    seed: u64,
    observation_level: ObservationLevel,
    until: Option<i64>,
    order: usize,
) -> Result<(RunMeasurement, RunResult)> {
    let runtime =
        Runtime::from_shared_with_observation(plan, fingerprint, seed, observation_level)?;
    let started = Instant::now();
    let result = runtime.run(until)?;
    let execution_ns = started.elapsed().as_nanos().try_into().unwrap_or(u64::MAX);
    let measurement = RunMeasurement {
        time_profile,
        order,
        execution_ns,
        result_bytes: serde_json::to_vec(&result)?.len(),
        trace_events: result.trace.len(),
        result_sha256: digest(&result)?,
        business_result_sha256: business_result_sha256(&result)?,
        sample_requests_sha256: digest(&result.sample_requests)?,
        trace_sha256: digest(&result.trace)?,
        metrics_sha256: digest(&result.metrics)?,
        terminal_state_sha256: digest(&result.terminal_state)?,
        result_time: result.time,
        result_stop_reason: result.stop_reason.clone(),
        result_plan_fingerprint: result.plan_fingerprint.clone(),
        result_seed: result.seed,
    };
    Ok((measurement, result))
}

fn run_pair(
    legacy: &LoadedPlan,
    event_time: &LoadedPlan,
    seed: u64,
    observation_level: ObservationLevel,
    until: Option<i64>,
    legacy_first: bool,
) -> Result<(RunMeasurement, RunMeasurement)> {
    let run_legacy = |order| {
        run_one(
            legacy.plan.clone(),
            legacy.fingerprint.clone(),
            LEGACY_PROFILE,
            seed,
            observation_level,
            until,
            order,
        )
    };
    let run_event = |order| {
        run_one(
            event_time.plan.clone(),
            event_time.fingerprint.clone(),
            EVENT_PROFILE,
            seed,
            observation_level,
            until,
            order,
        )
    };

    let (legacy_measurement, legacy_result, event_measurement, event_result) = if legacy_first {
        let (legacy_measurement, legacy_result) = run_legacy(0)?;
        let (event_measurement, event_result) = run_event(1)?;
        (
            legacy_measurement,
            legacy_result,
            event_measurement,
            event_result,
        )
    } else {
        let (event_measurement, event_result) = run_event(0)?;
        let (legacy_measurement, legacy_result) = run_legacy(1)?;
        (
            legacy_measurement,
            legacy_result,
            event_measurement,
            event_result,
        )
    };
    assert_business_equivalence(observation_level, &legacy_result, &event_result)?;
    if legacy_measurement.business_result_sha256 != event_measurement.business_result_sha256 {
        bail!("time profiles produced different business result digests after exact comparison");
    }
    Ok((legacy_measurement, event_measurement))
}

fn plan_identity(path: &Path, loaded: &LoadedPlan) -> PlanIdentity {
    PlanIdentity {
        path: path.display().to_string(),
        bytes: loaded.bytes.len(),
        file_sha256: format!("{:x}", Sha256::digest(&loaded.bytes)),
        plan_fingerprint: loaded.fingerprint.clone(),
        semantic_profile: loaded.plan.semantic_profile.clone(),
    }
}

fn main() -> Result<()> {
    let args = Args::parse();
    validate_run_counts(args.warmups, args.repeats)?;
    if args.session_label.trim().is_empty() {
        bail!("session-label must not be empty");
    }
    if args.until.is_some_and(|value| value < 0) {
        bail!("until must be non-negative");
    }
    let seeds = parse_seeds(&args.seeds)?;
    let observation_levels = parse_observation_levels(&args.observation_levels)?;
    let legacy = load_plan(&args.legacy_plan, LEGACY_PROFILE)?;
    let event_time = load_plan(&args.event_plan, EVENT_PROFILE)?;
    let normalized_legacy = normalized_plan(&legacy.raw)?;
    let normalized_event = normalized_plan(&event_time.raw)?;
    if normalized_legacy != normalized_event {
        bail!("paired plans differ in fields other than semantic_profile");
    }
    let paired_model_sha256 = digest(&normalized_legacy)?;
    let duration_minutes = legacy.plan.duration_minutes;
    let source_inputs_sha256 = legacy.plan.source_inputs_sha256.clone();
    let plan_version = legacy.plan.plan_version.clone();
    let work_policy = legacy.plan.work_policy.clone();
    let rng_profile = legacy.plan.rng_profile.clone();

    for (observation_index, &observation_level) in observation_levels.iter().enumerate() {
        for (seed_index, &seed) in seeds.iter().enumerate() {
            for warmup in 0..args.warmups {
                let legacy_first = legacy_runs_first(observation_index, seed_index, warmup);
                run_pair(
                    &legacy,
                    &event_time,
                    seed,
                    observation_level,
                    args.until,
                    legacy_first,
                )?;
            }
        }
    }

    let mut records = Vec::with_capacity(observation_levels.len() * seeds.len() * args.repeats);
    for (observation_index, &observation_level) in observation_levels.iter().enumerate() {
        for (seed_index, &seed) in seeds.iter().enumerate() {
            for repeat in 0..args.repeats {
                let legacy_first = legacy_runs_first(observation_index, seed_index, repeat);
                let (legacy_measurement, event_measurement) = run_pair(
                    &legacy,
                    &event_time,
                    seed,
                    observation_level,
                    args.until,
                    legacy_first,
                )?;
                let legacy_ns = legacy_measurement.execution_ns as f64;
                let event_ns = event_measurement.execution_ns as f64;
                records.push(PairRecord {
                    observation_level,
                    seed,
                    repeat,
                    first_profile: if legacy_first {
                        LEGACY_PROFILE
                    } else {
                        EVENT_PROFILE
                    },
                    legacy: legacy_measurement,
                    event_time: event_measurement,
                    business_equivalent: true,
                    legacy_to_event_ratio: legacy_ns / event_ns,
                    event_improvement_pct: (legacy_ns - event_ns) / legacy_ns * 100.0,
                });
            }
        }
    }

    let report = BenchmarkReport {
        schema_version: "event-time-paired-benchmark/v1",
        generated_at_unix_seconds: SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs(),
        session_label: args.session_label,
        build: build_identity(
            "rust/runtime/src/bin/event_time_benchmark.rs",
            include_bytes!("event_time_benchmark.rs"),
            args.source_diff.as_deref(),
            args.host_manifest.as_deref(),
        )?,
        legacy_plan: plan_identity(&args.legacy_plan, &legacy),
        event_plan: plan_identity(&args.event_plan, &event_time),
        paired_model_sha256,
        source_inputs_sha256,
        plan_version,
        work_policy,
        rng_profile,
        duration_minutes,
        until: args.until,
        seeds,
        observation_levels,
        warmups: args.warmups,
        repeats: args.repeats,
        records,
    };
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&args.output, serde_json::to_vec_pretty(&report)?)?;
    println!("{}", args.output.display());
    Ok(())
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn result(plan_fingerprint: &str, trace: Vec<Value>) -> RunResult {
        RunResult {
            plan_fingerprint: plan_fingerprint.into(),
            seed: 7,
            time: 42,
            stop_reason: "duration".into(),
            sample_requests: vec![json!({"request": 1})],
            trace,
            metrics: json!({"completed": 2}),
            terminal_state: json!({"state": "done"}),
        }
    }

    #[test]
    fn plan_normalization_only_replaces_semantic_profile() {
        let legacy = json!({"semantic_profile": LEGACY_PROFILE, "duration_minutes": 42});
        let event = json!({"semantic_profile": EVENT_PROFILE, "duration_minutes": 42});
        assert_eq!(
            normalized_plan(&legacy).unwrap(),
            normalized_plan(&event).unwrap()
        );

        let changed = json!({"semantic_profile": EVENT_PROFILE, "duration_minutes": 43});
        assert_ne!(
            normalized_plan(&legacy).unwrap(),
            normalized_plan(&changed).unwrap()
        );
    }

    #[test]
    fn business_equivalence_ignores_only_plan_fingerprint() {
        let legacy = result("legacy", vec![json!({"kind": "event"})]);
        let event = result("event", vec![json!({"kind": "event"})]);
        assert_business_equivalence(ObservationLevel::Full, &legacy, &event).unwrap();
        assert_eq!(
            business_result_sha256(&legacy).unwrap(),
            business_result_sha256(&event).unwrap()
        );

        let mut changed = result("event", vec![json!({"kind": "changed"})]);
        assert!(assert_business_equivalence(ObservationLevel::Full, &legacy, &changed).is_err());
        changed.trace.clear();
        assert!(assert_business_equivalence(ObservationLevel::Summary, &legacy, &changed).is_err());
    }

    #[test]
    fn summary_requires_empty_trace() {
        let legacy = result("legacy", vec![]);
        let event = result("event", vec![]);
        assert_business_equivalence(ObservationLevel::Summary, &legacy, &event).unwrap();

        let with_trace = result("event", vec![json!({"kind": "event"})]);
        assert!(
            assert_business_equivalence(ObservationLevel::Summary, &legacy, &with_trace).is_err()
        );
    }

    #[test]
    fn observation_level_parser_rejects_duplicates_and_empty_input() {
        assert!(parse_observation_levels("").is_err());
        assert!(parse_observation_levels("full,full").is_err());
        assert_eq!(
            parse_observation_levels("full,summary").unwrap(),
            vec![ObservationLevel::Full, ObservationLevel::Summary]
        );
    }

    #[test]
    fn paired_order_alternates_across_repeats_and_starting_combinations() {
        assert!(legacy_runs_first(0, 0, 0));
        assert!(!legacy_runs_first(0, 0, 1));
        assert!(!legacy_runs_first(0, 1, 0));
        assert!(!legacy_runs_first(1, 0, 0));
        assert!(legacy_runs_first(1, 1, 0));
    }

    #[test]
    fn formal_runs_require_warmup_and_measurement_repeats() {
        assert!(validate_run_counts(1, 1).is_ok());
        assert!(validate_run_counts(0, 1).is_err());
        assert!(validate_run_counts(1, 0).is_err());
    }
}
