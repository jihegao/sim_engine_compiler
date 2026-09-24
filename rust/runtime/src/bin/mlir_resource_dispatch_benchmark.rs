use std::{
    fs,
    path::PathBuf,
    sync::Arc,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use clap::Parser;
use serde::Serialize;
use sha2::{Digest, Sha256};
use sim_engine_runtime::{ExecutionPlan, ObservationLevel, Runtime, RuntimeProfile};

#[derive(Parser)]
#[command(about = "Compare baseline, MLIR-verified, and MLIR-indexed F35 execution plans")]
struct Args {
    baseline_plan: PathBuf,
    mlir_off_plan: PathBuf,
    mlir_on_plan: PathBuf,
    output: PathBuf,
    #[arg(long, default_value = "0,1,7")]
    seeds: String,
    #[arg(long, default_value_t = 1)]
    repeats: usize,
}

#[derive(Clone)]
struct Arm {
    name: &'static str,
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    plan_load_parse_validate_ns: u64,
    plan_bytes: usize,
}

#[derive(Serialize)]
struct RunRecord {
    repeat: usize,
    seed: u64,
    arm: &'static str,
    initialization_ns: u64,
    execution_ns: u64,
    end_to_end_ns: u64,
    result_sha256: String,
    trace_events: usize,
    resource_dispatch_candidate_visits: u64,
    resource_dispatch_guard_evaluations: u64,
    resource_dispatch_cache_hits: u64,
    profile: RuntimeProfile,
}

#[derive(Serialize)]
struct Report {
    schema_version: &'static str,
    generated_at_unix_seconds: u64,
    host_os: &'static str,
    host_arch: &'static str,
    seeds: Vec<u64>,
    repeats: usize,
    baseline_plan_fingerprint: String,
    mlir_disabled_plan_fingerprint: String,
    mlir_enabled_plan_fingerprint: String,
    baseline_plan_load_parse_validate_ns: u64,
    mlir_disabled_plan_load_parse_validate_ns: u64,
    mlir_enabled_plan_load_parse_validate_ns: u64,
    plan_bytes: usize,
    mlir_candidate_rule_count: usize,
    exact_full_result_parity: bool,
    records: Vec<RunRecord>,
}

fn parse_plan(path: &PathBuf) -> Result<Arm> {
    let started = Instant::now();
    let bytes = fs::read(path).with_context(|| format!("read plan {}", path.display()))?;
    let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    Ok(Arm {
        name: "",
        plan: Arc::new(plan),
        fingerprint,
        plan_load_parse_validate_ns: elapsed_ns(started),
        plan_bytes: bytes.len(),
    })
}

fn elapsed_ns(start: Instant) -> u64 {
    start.elapsed().as_nanos().try_into().unwrap_or(u64::MAX)
}

fn digest<T: Serialize>(value: &T) -> Result<String> {
    Ok(format!("{:x}", Sha256::digest(serde_json::to_vec(value)?)))
}

fn run_one(arm: &Arm, seed: u64) -> Result<(serde_json::Value, RuntimeProfile, u64, u64, u64)> {
    let end_to_end = Instant::now();
    let initialize = Instant::now();
    let runtime = Runtime::from_shared_profiled(
        arm.plan.clone(),
        arm.fingerprint.clone(),
        seed,
        ObservationLevel::Full,
    )?;
    let initialization_ns = elapsed_ns(initialize);
    let (result, profile) = runtime.run_profiled(None)?;
    let execution_ns = profile.execution_ns;
    let total_ns = elapsed_ns(end_to_end);
    Ok((
        serde_json::to_value(result)?,
        profile,
        initialization_ns,
        execution_ns,
        total_ns,
    ))
}

fn main() -> Result<()> {
    let args = Args::parse();
    if args.repeats == 0 {
        bail!("repeats must be greater than zero");
    }
    let seeds = args
        .seeds
        .split(',')
        .map(|item| item.trim().parse::<u64>())
        .collect::<std::result::Result<Vec<_>, _>>()?;
    if seeds.is_empty() {
        bail!("at least one seed is required");
    }

    let mut baseline = parse_plan(&args.baseline_plan)?;
    let mut disabled = parse_plan(&args.mlir_off_plan)?;
    let mut enabled = parse_plan(&args.mlir_on_plan)?;
    baseline.name = "existing_compile_chain";
    disabled.name = "mlir_business_pass_disabled";
    enabled.name = "mlir_business_pass_enabled";
    if baseline.fingerprint != disabled.fingerprint || baseline.fingerprint != enabled.fingerprint {
        bail!("the three plans do not have the same semantic plan fingerprint");
    }
    if baseline.plan.resource_dispatch_index.is_some()
        || disabled.plan.resource_dispatch_index.is_some()
        || enabled.plan.resource_dispatch_index.is_none()
    {
        bail!("plan arms do not match baseline / MLIR-off / MLIR-on configuration");
    }
    let mlir_candidate_rule_count = enabled
        .plan
        .resource_dispatch_index
        .as_ref()
        .map_or(0, |index| index.candidate_rule_count);

    let arms = [&baseline, &disabled, &enabled];
    let mut records = Vec::with_capacity(seeds.len() * args.repeats * arms.len());
    for seed in &seeds {
        for repeat in 0..args.repeats {
            let order = if repeat % 2 == 0 {
                [0usize, 1, 2]
            } else {
                [2usize, 1, 0]
            };
            let mut arm_results: Vec<Option<serde_json::Value>> = vec![None; arms.len()];
            for arm_index in order {
                let arm = arms[arm_index];
                let (result, profile, initialization_ns, execution_ns, total_ns) =
                    run_one(arm, *seed)?;
                arm_results[arm_index] = Some(result.clone());
                let trace_events = result["trace"].as_array().map_or(0, Vec::len);
                records.push(RunRecord {
                    repeat,
                    seed: *seed,
                    arm: arm.name,
                    initialization_ns,
                    execution_ns,
                    end_to_end_ns: total_ns,
                    result_sha256: digest(&result)?,
                    trace_events,
                    resource_dispatch_candidate_visits: profile.resource_dispatch_candidate_visits,
                    resource_dispatch_guard_evaluations: profile
                        .resource_dispatch_guard_evaluations,
                    resource_dispatch_cache_hits: profile.resource_dispatch_cache_hits,
                    profile,
                });
            }
            let expected = arm_results[0].as_ref().expect("baseline arm ran");
            if arm_results
                .iter()
                .skip(1)
                .any(|result| result.as_ref() != Some(expected))
            {
                bail!("full-result mismatch for seed {seed}, repeat {repeat}");
            }
        }
    }
    let report = Report {
        schema_version: "mlir-resource-dispatch-pilot-benchmark/v1",
        generated_at_unix_seconds: SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs(),
        host_os: std::env::consts::OS,
        host_arch: std::env::consts::ARCH,
        seeds,
        repeats: args.repeats,
        baseline_plan_fingerprint: baseline.fingerprint,
        mlir_disabled_plan_fingerprint: disabled.fingerprint,
        mlir_enabled_plan_fingerprint: enabled.fingerprint,
        baseline_plan_load_parse_validate_ns: baseline.plan_load_parse_validate_ns,
        mlir_disabled_plan_load_parse_validate_ns: disabled.plan_load_parse_validate_ns,
        mlir_enabled_plan_load_parse_validate_ns: enabled.plan_load_parse_validate_ns,
        plan_bytes: baseline.plan_bytes,
        mlir_candidate_rule_count,
        exact_full_result_parity: true,
        records,
    };
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&args.output, serde_json::to_vec_pretty(&report)?)?;
    println!("{}", args.output.display());
    Ok(())
}
