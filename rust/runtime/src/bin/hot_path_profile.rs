use std::{
    fs,
    path::PathBuf,
    str::FromStr,
    sync::Arc,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Result, bail};
use clap::Parser;
use serde::Serialize;
use sha2::{Digest, Sha256};
use sim_engine_runtime::{ExecutionPlan, ObservationLevel, RunResult, Runtime, RuntimeProfile};

mod benchmark_support;

use benchmark_support::{BuildIdentity, build_identity};

#[derive(Parser)]
#[command(about = "Profile the F35 Rust execution hot path without timing plan loading")]
struct Args {
    plan: PathBuf,
    output: PathBuf,
    #[arg(long, default_value_t = 0)]
    seed: u64,
    #[arg(long, default_value = "full")]
    observation_level: String,
    #[arg(long, default_value_t = 3)]
    repeats: usize,
    #[arg(long, value_name = "PATH")]
    source_diff: Option<PathBuf>,
    #[arg(long, value_name = "PATH")]
    host_manifest: Option<PathBuf>,
}

#[derive(Serialize)]
struct ProfileRecord {
    repeat: usize,
    uninstrumented_execution_ns: u64,
    profile: RuntimeProfile,
    result_sha256: String,
    sample_requests_sha256: String,
    trace_sha256: String,
    metrics_sha256: String,
    terminal_state_sha256: String,
    result_plan_fingerprint: String,
    result_seed: u64,
    result_time: i64,
    result_stop_reason: String,
    trace_events: usize,
    result_bytes: usize,
}

#[derive(Serialize)]
struct ProfileReport {
    schema_version: &'static str,
    generated_at_unix_seconds: u64,
    build: BuildIdentity,
    plan_path: String,
    plan_bytes: usize,
    plan_file_sha256: String,
    plan_fingerprint: String,
    semantic_profile: String,
    work_policy: String,
    rng_profile: String,
    seed: u64,
    observation_level: ObservationLevel,
    repeats: usize,
    records: Vec<ProfileRecord>,
}

fn digest<T: Serialize>(value: &T) -> Result<String> {
    Ok(format!("{:x}", Sha256::digest(serde_json::to_vec(value)?)))
}

fn assert_matching_result_field<T: PartialEq>(
    field: &str,
    uninstrumented: &T,
    profiled: &T,
) -> Result<()> {
    if uninstrumented != profiled {
        bail!("profile instrumentation changed result field {field}");
    }
    Ok(())
}

fn assert_profile_equivalence(
    observation_level: ObservationLevel,
    uninstrumented: &RunResult,
    profiled: &RunResult,
) -> Result<()> {
    assert_matching_result_field(
        "plan_fingerprint",
        &uninstrumented.plan_fingerprint,
        &profiled.plan_fingerprint,
    )?;
    assert_matching_result_field("seed", &uninstrumented.seed, &profiled.seed)?;
    assert_matching_result_field("time", &uninstrumented.time, &profiled.time)?;
    assert_matching_result_field(
        "stop_reason",
        &uninstrumented.stop_reason,
        &profiled.stop_reason,
    )?;
    assert_matching_result_field(
        "sample_requests",
        &uninstrumented.sample_requests,
        &profiled.sample_requests,
    )?;
    assert_matching_result_field("metrics", &uninstrumented.metrics, &profiled.metrics)?;
    assert_matching_result_field(
        "terminal_state",
        &uninstrumented.terminal_state,
        &profiled.terminal_state,
    )?;
    match observation_level {
        ObservationLevel::Full => {
            assert_matching_result_field("trace", &uninstrumented.trace, &profiled.trace)?;
        }
        ObservationLevel::Summary => {
            if !uninstrumented.trace.is_empty() || !profiled.trace.is_empty() {
                bail!("summary result must have an empty trace");
            }
        }
    }
    Ok(())
}

fn main() -> Result<()> {
    let args = Args::parse();
    if args.repeats == 0 {
        bail!("repeats must be greater than zero");
    }
    let observation_level = ObservationLevel::from_str(&args.observation_level)?;
    let bytes = fs::read(&args.plan)?;
    let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    let semantic_profile = plan.semantic_profile.clone();
    let work_policy = plan.work_policy.clone();
    let rng_profile = plan.rng_profile.clone();
    let plan = Arc::new(plan);
    let mut records = Vec::with_capacity(args.repeats);

    for repeat in 0..args.repeats {
        let runtime = Runtime::from_shared_with_observation(
            plan.clone(),
            fingerprint.clone(),
            args.seed,
            observation_level,
        )?;
        let started = Instant::now();
        let uninstrumented_result = runtime.run(None)?;
        let uninstrumented_execution_ns =
            started.elapsed().as_nanos().try_into().unwrap_or(u64::MAX);
        let runtime = Runtime::from_shared_profiled(
            plan.clone(),
            fingerprint.clone(),
            args.seed,
            observation_level,
        )?;
        let (result, profile) = runtime.run_profiled(None)?;
        assert_profile_equivalence(observation_level, &uninstrumented_result, &result)?;
        records.push(ProfileRecord {
            repeat,
            uninstrumented_execution_ns,
            profile,
            result_sha256: digest(&result)?,
            sample_requests_sha256: digest(&result.sample_requests)?,
            trace_sha256: digest(&result.trace)?,
            metrics_sha256: digest(&result.metrics)?,
            terminal_state_sha256: digest(&result.terminal_state)?,
            result_plan_fingerprint: result.plan_fingerprint.clone(),
            result_seed: result.seed,
            result_time: result.time,
            result_stop_reason: result.stop_reason.clone(),
            trace_events: result.trace.len(),
            result_bytes: serde_json::to_vec(&result)?.len(),
        });
    }

    let report = ProfileReport {
        schema_version: "runtime-hot-path-profile/v2",
        generated_at_unix_seconds: SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs(),
        build: build_identity(
            "rust/runtime/src/bin/hot_path_profile.rs",
            include_bytes!("hot_path_profile.rs"),
            args.source_diff.as_deref(),
            args.host_manifest.as_deref(),
        )?,
        plan_path: args.plan.display().to_string(),
        plan_bytes: bytes.len(),
        plan_file_sha256: format!("{:x}", Sha256::digest(&bytes)),
        plan_fingerprint: fingerprint,
        semantic_profile,
        work_policy,
        rng_profile,
        seed: args.seed,
        observation_level,
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

    fn result(trace: Vec<serde_json::Value>) -> RunResult {
        RunResult {
            plan_fingerprint: "plan-1".into(),
            seed: 7,
            time: 42,
            stop_reason: "duration".into(),
            sample_requests: vec![json!({"sequence": 1})],
            trace,
            metrics: json!({"completed": 1}),
            terminal_state: json!({"aircraft": []}),
        }
    }

    fn changed_non_trace_field(field: &str) -> RunResult {
        let mut changed = result(vec![]);
        match field {
            "plan_fingerprint" => changed.plan_fingerprint = "plan-2".into(),
            "seed" => changed.seed = 8,
            "time" => changed.time = 43,
            "stop_reason" => changed.stop_reason = "requested_until".into(),
            "sample_requests" => changed.sample_requests.push(json!({"sequence": 2})),
            "metrics" => changed.metrics = json!({"completed": 2}),
            "terminal_state" => changed.terminal_state = json!({"aircraft": ["A1"]}),
            other => panic!("unsupported test field {other}"),
        }
        changed
    }

    #[test]
    fn full_requires_the_complete_trace_to_match() {
        let baseline = result(vec![json!({"sequence": 1, "kind": "start"})]);
        let same = result(vec![json!({"sequence": 1, "kind": "start"})]);
        assert!(assert_profile_equivalence(ObservationLevel::Full, &baseline, &same).is_ok());

        let changed = result(vec![json!({"sequence": 1, "kind": "finish"})]);
        let error = assert_profile_equivalence(ObservationLevel::Full, &baseline, &changed)
            .expect_err("trace mismatch must be rejected");
        assert!(error.to_string().contains("trace"));
    }

    #[test]
    fn summary_requires_both_traces_to_be_empty() {
        let baseline = result(vec![]);
        let same = result(vec![]);
        assert!(assert_profile_equivalence(ObservationLevel::Summary, &baseline, &same).is_ok());

        let non_empty = result(vec![json!({"sequence": 1})]);
        let error = assert_profile_equivalence(ObservationLevel::Summary, &non_empty, &non_empty)
            .expect_err("summary trace materialization must be rejected");
        assert!(error.to_string().contains("empty trace"));
    }

    #[test]
    fn every_non_trace_result_field_must_match() {
        let baseline = result(vec![]);
        for field in [
            "plan_fingerprint",
            "seed",
            "time",
            "stop_reason",
            "sample_requests",
            "metrics",
            "terminal_state",
        ] {
            let changed = changed_non_trace_field(field);
            let error = assert_profile_equivalence(ObservationLevel::Summary, &baseline, &changed)
                .expect_err("non-trace mismatch must be rejected");
            assert!(error.to_string().contains(field));
        }
    }
}
