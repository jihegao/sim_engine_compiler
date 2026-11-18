//! Canonical-input Monte Carlo boundary for `spare_mvp`.
//!
//! This module accepts only the upstream Adapter's canonical
//! `simulation_inputs`. It deliberately does not parse Project JSON and does
//! not construct any analysis projections.

use std::{
    collections::{BTreeMap, HashSet},
    fs,
    path::Path,
    sync::Arc,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use sim_engine_runtime::{
    ExecutionPlan, IndexedSampleRequest, ObservationLevel, PLAN_CACHE_FORMAT_VERSION,
    PlanBatchGroup, RUNTIME_VERSION, RunResult, decode_plan_cache, encode_plan_cache,
    run_indexed_plan_batch_with_observation,
};

use crate::{COMPILER_VERSION, compile_aircraft_support_with_profile};

pub const CANONICAL_BATCH_CONTRACT_VERSION: &str = "spare-mvp-canonical-batch/v1";
pub const SEMANTIC_PROFILE: &str = "event-time-v2";
const OBSERVATION_LEVEL: ObservationLevel = ObservationLevel::Summary;

#[derive(Clone, Debug, Deserialize)]
pub struct CanonicalSampleRequest {
    pub sample_index: usize,
    pub seed: u64,
    #[serde(default)]
    pub sweep: Value,
    pub canonical_inputs: Value,
    /// Reserved for the upstream Monte Carlo request contract. The canonical
    /// input already contains the simulation horizon, so steps are not
    /// interpreted by the engine boundary.
    #[serde(default)]
    pub steps: Option<Value>,
}

#[derive(Debug, Serialize)]
pub struct CanonicalSampleResult {
    pub sample_index: usize,
    pub seed: u64,
    pub sweep: Value,
    pub metrics: Value,
    pub result: RunResult,
}

#[derive(Debug, Serialize)]
pub struct FailedCanonicalSample {
    pub sample_index: usize,
    pub seed: u64,
    pub sweep: Value,
    pub stage: String,
    pub error: String,
}

#[derive(Debug, Serialize)]
pub struct EngineMetadata {
    pub contract_version: &'static str,
    pub execution_backend: &'static str,
    pub compiler_version: &'static str,
    pub runtime_version: &'static str,
    pub semantic_profile: &'static str,
    pub observation_level: &'static str,
    pub cache_format_version: &'static str,
    pub build_commit: &'static str,
}

#[derive(Clone, Debug, Serialize)]
pub struct PlanCacheGroup {
    pub group_index: usize,
    pub source_inputs_sha256: String,
    pub plan_fingerprint: Option<String>,
    pub sample_count: usize,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rebuild_reason: Option<String>,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct CanonicalBatchTimings {
    pub input_fingerprint_ns: u64,
    pub cache_decode_ns: u64,
    pub compile_ns: u64,
    pub cache_write_ns: u64,
    pub plan_prepare_ns: u64,
    pub execute_ns: u64,
    pub total_ns: u64,
}

#[derive(Debug, Serialize)]
pub struct CanonicalBatchResult {
    pub samples: Vec<CanonicalSampleResult>,
    pub failed_samples: Vec<FailedCanonicalSample>,
    pub engine_metadata: EngineMetadata,
    pub plan_cache_status: String,
    pub cache_groups: Vec<PlanCacheGroup>,
    pub timings: CanonicalBatchTimings,
    pub worker_count: usize,
    pub requested_sample_count: usize,
}

#[derive(Debug)]
struct PendingGroup {
    group_index: usize,
    source_inputs_sha256: String,
    canonical_json: String,
    canonical_inputs: Value,
    sample_indexes: Vec<usize>,
}

#[derive(Debug)]
struct ResolvedPlan {
    plan: ExecutionPlan,
    plan_fingerprint: String,
    cache: PlanCacheGroup,
}

fn elapsed_ns(started: Instant) -> u64 {
    started.elapsed().as_nanos().try_into().unwrap_or(u64::MAX)
}

pub fn plan_cache_file_name(
    identity: &str,
    adapter_digest: Option<&str>,
    compiler_version: &str,
    semantic_profile: &str,
) -> String {
    let compiler = compiler_version.rsplit('/').next().unwrap_or("unknown");
    let format = PLAN_CACHE_FORMAT_VERSION
        .rsplit('/')
        .next()
        .unwrap_or("unknown");
    format!(
        "{identity}-{}-{compiler}-{semantic_profile}-{format}.seplan",
        adapter_digest.unwrap_or("canonical")
    )
}

fn cache_file_name(source_inputs_sha256: &str) -> String {
    plan_cache_file_name(
        source_inputs_sha256,
        None,
        COMPILER_VERSION,
        SEMANTIC_PROFILE,
    )
}

fn write_atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("create cache directory {}", parent.display()))?;
    }
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
    let file_name = path
        .file_name()
        .and_then(|value| value.to_str())
        .context("cache path has no UTF-8 file name")?;
    let temporary =
        path.with_file_name(format!(".{file_name}.{}.{}.tmp", std::process::id(), stamp));
    fs::write(&temporary, bytes)
        .with_context(|| format!("write temporary cache {}", temporary.display()))?;
    if let Err(error) = fs::rename(&temporary, path) {
        let _ = fs::remove_file(&temporary);
        return Err(error).with_context(|| format!("publish cache {}", path.display()));
    }
    Ok(())
}

fn compile_plan(
    inputs: &Value,
    timings: &mut CanonicalBatchTimings,
) -> Result<(ExecutionPlan, String)> {
    let started = Instant::now();
    let plan = compile_aircraft_support_with_profile(inputs, SEMANTIC_PROFILE)?;
    timings.compile_ns = timings.compile_ns.saturating_add(elapsed_ns(started));
    let raw = serde_json::to_value(&plan)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    Ok((plan, fingerprint))
}

fn resolve_plan(
    group: &PendingGroup,
    cache_dir: Option<&Path>,
    timings: &mut CanonicalBatchTimings,
) -> Result<ResolvedPlan> {
    let cache_path =
        cache_dir.map(|directory| directory.join(cache_file_name(&group.source_inputs_sha256)));
    let mut cache_status = if cache_path.is_some() {
        "miss"
    } else {
        "disabled"
    };
    let mut rebuild_reason = None;

    if let Some(path) = cache_path.as_ref()
        && path.exists()
    {
        let decode_started = Instant::now();
        let cached = fs::read(path)
            .with_context(|| format!("read cached plan {}", path.display()))
            .and_then(|bytes| {
                decode_plan_cache(
                    &bytes,
                    Some(COMPILER_VERSION),
                    Some(&group.source_inputs_sha256),
                    Some(SEMANTIC_PROFILE),
                )
            });
        timings.cache_decode_ns = timings
            .cache_decode_ns
            .saturating_add(elapsed_ns(decode_started));
        match cached {
            Ok(cached) => {
                return Ok(ResolvedPlan {
                    plan: cached.plan,
                    plan_fingerprint: cached.plan_fingerprint.clone(),
                    cache: PlanCacheGroup {
                        group_index: group.group_index,
                        source_inputs_sha256: group.source_inputs_sha256.clone(),
                        plan_fingerprint: Some(cached.plan_fingerprint),
                        sample_count: group.sample_indexes.len(),
                        status: "hit".to_owned(),
                        rebuild_reason: None,
                    },
                });
            }
            Err(error) => {
                // Fail closed: an invalid envelope is never executed. Rebuild
                // only from the canonical source supplied in this request.
                cache_status = "rebuilt";
                rebuild_reason = Some(format!("{error:#}"));
            }
        }
    }

    let (plan, plan_fingerprint) = compile_plan(&group.canonical_inputs, timings)?;
    if plan.source_inputs_sha256 != group.source_inputs_sha256 {
        bail!("compiler source fingerprint does not match canonical cache key");
    }
    if let Some(path) = cache_path.as_ref() {
        let bytes = encode_plan_cache(plan.clone(), COMPILER_VERSION, &plan_fingerprint)?;
        let write_started = Instant::now();
        write_atomic(path, &bytes)?;
        timings.cache_write_ns = timings
            .cache_write_ns
            .saturating_add(elapsed_ns(write_started));
    }
    Ok(ResolvedPlan {
        plan,
        plan_fingerprint: plan_fingerprint.clone(),
        cache: PlanCacheGroup {
            group_index: group.group_index,
            source_inputs_sha256: group.source_inputs_sha256.clone(),
            plan_fingerprint: Some(plan_fingerprint),
            sample_count: group.sample_indexes.len(),
            status: cache_status.to_owned(),
            rebuild_reason,
        },
    })
}

fn aggregate_cache_status(groups: &[PlanCacheGroup], requested: usize) -> String {
    if groups.is_empty() {
        return if requested == 0 { "disabled" } else { "failed" }.to_owned();
    }
    let statuses = groups
        .iter()
        .map(|group| group.status.as_str())
        .collect::<HashSet<_>>();
    if statuses.len() == 1 {
        statuses.into_iter().next().unwrap_or("failed").to_owned()
    } else {
        "mixed".to_owned()
    }
}

pub fn run_canonical_batch(
    samples: Vec<CanonicalSampleRequest>,
    worker_threads: Option<usize>,
    cache_dir: Option<&Path>,
) -> Result<CanonicalBatchResult> {
    let total_started = Instant::now();
    if samples.is_empty() {
        bail!("canonical batch request must contain at least one sample");
    }
    if worker_threads == Some(0) {
        bail!("worker_threads must be greater than zero");
    }
    let requested_sample_count = samples.len();
    let mut by_index = BTreeMap::new();
    for sample in samples {
        let sample_index = sample.sample_index;
        if by_index.insert(sample_index, sample).is_some() {
            bail!("duplicate sample_index {sample_index}");
        }
    }

    let mut timings = CanonicalBatchTimings::default();
    let fingerprint_started = Instant::now();
    let mut groups_by_fingerprint = BTreeMap::<String, PendingGroup>::new();
    for sample in by_index.values() {
        let canonical_json = ExecutionPlan::python_canonical(&sample.canonical_inputs)?;
        let source_inputs_sha256 = format!("{:x}", Sha256::digest(canonical_json.as_bytes()));
        match groups_by_fingerprint.get_mut(&source_inputs_sha256) {
            Some(group) => {
                if group.canonical_json != canonical_json {
                    bail!("canonical fingerprint collision for source inputs");
                }
                group.sample_indexes.push(sample.sample_index);
            }
            None => {
                let group_index = groups_by_fingerprint.len();
                groups_by_fingerprint.insert(
                    source_inputs_sha256.clone(),
                    PendingGroup {
                        group_index,
                        source_inputs_sha256,
                        canonical_json,
                        canonical_inputs: sample.canonical_inputs.clone(),
                        sample_indexes: vec![sample.sample_index],
                    },
                );
            }
        }
    }
    timings.input_fingerprint_ns = elapsed_ns(fingerprint_started);

    let mut runtime_groups = Vec::new();
    let mut cache_groups = Vec::new();
    let mut failed_samples = Vec::new();
    for group in groups_by_fingerprint.values() {
        match resolve_plan(group, cache_dir, &mut timings) {
            Ok(resolved) => {
                cache_groups.push(resolved.cache);
                runtime_groups.push(PlanBatchGroup {
                    group_index: group.group_index,
                    plan: Arc::new(resolved.plan),
                    plan_fingerprint: resolved.plan_fingerprint,
                    samples: group
                        .sample_indexes
                        .iter()
                        .map(|sample_index| {
                            let sample = &by_index[sample_index];
                            IndexedSampleRequest {
                                sample_index: *sample_index,
                                seed: sample.seed,
                            }
                        })
                        .collect(),
                });
            }
            Err(error) => {
                cache_groups.push(PlanCacheGroup {
                    group_index: group.group_index,
                    source_inputs_sha256: group.source_inputs_sha256.clone(),
                    plan_fingerprint: None,
                    sample_count: group.sample_indexes.len(),
                    status: "compile_failed".to_owned(),
                    rebuild_reason: None,
                });
                for sample_index in &group.sample_indexes {
                    let sample = &by_index[sample_index];
                    failed_samples.push(FailedCanonicalSample {
                        sample_index: *sample_index,
                        seed: sample.seed,
                        sweep: sample.sweep.clone(),
                        stage: "compile".to_owned(),
                        error: format!("{error:#}"),
                    });
                }
            }
        }
    }

    let mut successful_samples = Vec::new();
    let mut worker_count = 0;
    if !runtime_groups.is_empty() {
        let batch = run_indexed_plan_batch_with_observation(
            runtime_groups,
            worker_threads,
            None,
            OBSERVATION_LEVEL,
        )?;
        timings.plan_prepare_ns = batch.prepare_ns;
        timings.execute_ns = batch.execute_ns;
        worker_count = batch.worker_threads;
        for output in batch.samples {
            let request = &by_index[&output.sample_index];
            successful_samples.push(CanonicalSampleResult {
                sample_index: output.sample_index,
                seed: output.seed,
                sweep: request.sweep.clone(),
                metrics: output.result.metrics.clone(),
                result: output.result,
            });
        }
        for output in batch.failed_samples {
            let request = &by_index[&output.sample_index];
            failed_samples.push(FailedCanonicalSample {
                sample_index: output.sample_index,
                seed: output.seed,
                sweep: request.sweep.clone(),
                stage: "execution".to_owned(),
                error: output.error,
            });
        }
    }
    successful_samples.sort_by_key(|sample| sample.sample_index);
    failed_samples.sort_by_key(|sample| sample.sample_index);
    cache_groups.sort_by_key(|group| group.group_index);
    let plan_cache_status = aggregate_cache_status(&cache_groups, requested_sample_count);
    timings.total_ns = elapsed_ns(total_started);

    Ok(CanonicalBatchResult {
        samples: successful_samples,
        failed_samples,
        engine_metadata: EngineMetadata {
            contract_version: CANONICAL_BATCH_CONTRACT_VERSION,
            execution_backend: "rust_event_time_v2",
            compiler_version: COMPILER_VERSION,
            runtime_version: RUNTIME_VERSION,
            semantic_profile: SEMANTIC_PROFILE,
            observation_level: "summary",
            cache_format_version: PLAN_CACHE_FORMAT_VERSION,
            build_commit: option_env!("SIM_ENGINE_GIT_COMMIT").unwrap_or("unknown"),
        },
        plan_cache_status,
        cache_groups,
        timings,
        worker_count,
        requested_sample_count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
    }

    fn fixture(path: &str) -> Value {
        serde_json::from_slice(&fs::read(root().join(path)).unwrap()).unwrap()
    }

    fn temporary_cache() -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!(
            "sim-engine-canonical-batch-{}-{stamp}",
            std::process::id()
        ))
    }

    fn request(sample_index: usize, seed: u64, canonical_inputs: Value) -> CanonicalSampleRequest {
        CanonicalSampleRequest {
            sample_index,
            seed,
            sweep: serde_json::json!({"row": sample_index}),
            canonical_inputs,
            steps: None,
        }
    }

    #[test]
    fn groups_inputs_runs_event_time_and_sorts_by_sample_index() {
        let inputs = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        let result = run_canonical_batch(
            vec![
                request(9, 7, inputs.clone()),
                request(2, 0, inputs.clone()),
                request(5, 7, inputs),
            ],
            Some(2),
            None,
        )
        .unwrap();
        assert_eq!(result.plan_cache_status, "disabled");
        assert_eq!(result.cache_groups.len(), 1);
        assert_eq!(result.worker_count, 2);
        assert_eq!(
            result
                .samples
                .iter()
                .map(|sample| sample.sample_index)
                .collect::<Vec<_>>(),
            vec![2, 5, 9]
        );
        assert_eq!(
            result
                .samples
                .iter()
                .map(|sample| sample.seed)
                .collect::<Vec<_>>(),
            vec![0, 7, 7]
        );
        assert!(
            result
                .samples
                .iter()
                .all(|sample| sample.result.trace.is_empty())
        );
        assert!(result.samples.iter().all(|sample| {
            sample.result.plan_fingerprint
                == result.cache_groups[0].plan_fingerprint.as_deref().unwrap()
        }));
        assert!(result.failed_samples.is_empty());
    }

    #[test]
    fn cache_miss_hit_and_corruption_rebuild_are_explicit() {
        let cache = temporary_cache();
        let inputs = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        let first = run_canonical_batch(vec![request(0, 0, inputs.clone())], Some(1), Some(&cache))
            .unwrap();
        assert_eq!(first.plan_cache_status, "miss");
        let second =
            run_canonical_batch(vec![request(0, 0, inputs.clone())], Some(1), Some(&cache))
                .unwrap();
        assert_eq!(second.plan_cache_status, "hit");
        assert_eq!(
            first.samples[0].result.plan_fingerprint,
            second.samples[0].result.plan_fingerprint
        );

        let cache_file = fs::read_dir(&cache)
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        fs::write(&cache_file, b"corrupt-cache").unwrap();
        let rebuilt =
            run_canonical_batch(vec![request(0, 0, inputs)], Some(1), Some(&cache)).unwrap();
        assert_eq!(rebuilt.plan_cache_status, "rebuilt");
        assert!(rebuilt.cache_groups[0].rebuild_reason.is_some());
        assert_eq!(
            first.samples[0].result.plan_fingerprint,
            rebuilt.samples[0].result.plan_fingerprint
        );
        fs::remove_dir_all(cache).unwrap();
    }

    #[test]
    fn one_invalid_canonical_group_does_not_hide_valid_samples() {
        let valid = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        let invalid = serde_json::json!({"schema_version": "unknown"});
        let result = run_canonical_batch(
            vec![request(4, 1, invalid), request(3, 0, valid)],
            Some(2),
            None,
        )
        .unwrap();
        assert_eq!(result.samples.len(), 1);
        assert_eq!(result.samples[0].sample_index, 3);
        assert_eq!(result.failed_samples.len(), 1);
        assert_eq!(result.failed_samples[0].sample_index, 4);
        assert_eq!(result.failed_samples[0].stage, "compile");
    }

    #[test]
    fn pre_validation_cache_cannot_admit_invalid_work() {
        let cache = temporary_cache();
        let valid = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        let mut invalid = valid.clone();
        invalid["support_activities"]["activities"][0]["jobs"][0]["durationMinutes"] =
            Value::from(-3);
        // Reconstruct the permissive compiler's old artifact: defaulted plan,
        // but the invalid input identity. Even at the new filename it is refused.
        let mut old_plan = compile_aircraft_support_with_profile(&valid, SEMANTIC_PROFILE).unwrap();
        let canonical = ExecutionPlan::python_canonical(&invalid).unwrap();
        let identity = format!("{:x}", Sha256::digest(canonical.as_bytes()));
        old_plan.source_inputs_sha256 = identity.clone();
        let fingerprint =
            ExecutionPlan::fingerprint(&serde_json::to_value(&old_plan).unwrap()).unwrap();
        let old_bytes =
            encode_plan_cache(old_plan, "aircraft-support-aot/v1alpha2", &fingerprint).unwrap();
        fs::create_dir_all(&cache).unwrap();
        fs::write(cache.join(cache_file_name(&identity)), old_bytes).unwrap();
        let result = run_canonical_batch(
            vec![request(4, 1, invalid), request(3, 0, valid)],
            Some(2),
            Some(&cache),
        )
        .unwrap();
        assert_eq!(result.samples.len(), 1);
        assert_eq!(result.samples[0].sample_index, 3);
        assert_eq!(result.failed_samples.len(), 1);
        assert!(result.failed_samples[0].error.contains(
            "negative_duration at support_activities.activities[0].jobs[0].durationMinutes"
        ));
        fs::remove_dir_all(cache).unwrap();
    }

    #[test]
    fn heterogeneous_valid_groups_share_one_bounded_worker_pool() {
        let b1 = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        let b3 = fixture("tests/fixtures/synthetic/b3-upstream-transport.json");
        let result =
            run_canonical_batch(vec![request(10, 0, b1), request(1, 7, b3)], Some(2), None)
                .unwrap();
        assert_eq!(result.cache_groups.len(), 2);
        assert_eq!(result.worker_count, 2);
        assert_eq!(
            result
                .samples
                .iter()
                .map(|sample| sample.sample_index)
                .collect::<Vec<_>>(),
            vec![1, 10]
        );
        assert_ne!(
            result.samples[0].result.plan_fingerprint,
            result.samples[1].result.plan_fingerprint
        );
    }

    #[test]
    fn compiler_version_change_invalidates_old_cache_file_name() {
        let old_name = plan_cache_file_name(
            "abc",
            None,
            "aircraft-support-aot/v1alpha6",
            SEMANTIC_PROFILE,
        );
        let new_name = plan_cache_file_name("abc", None, COMPILER_VERSION, SEMANTIC_PROFILE);
        assert_ne!(old_name, new_name);
        assert!(new_name.contains("v1alpha7"));
        assert!(!new_name.contains("v1alpha6"));
        let adapter_name = plan_cache_file_name(
            "abc",
            Some("adapter-sha"),
            COMPILER_VERSION,
            SEMANTIC_PROFILE,
        );
        assert!(adapter_name.starts_with("abc-adapter-sha-v1alpha7-"));
        assert_ne!(adapter_name, new_name);
    }

    #[test]
    fn stale_v1alpha5_cache_is_not_reused() {
        let cache = temporary_cache();
        let inputs = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        let canonical = ExecutionPlan::python_canonical(&inputs).unwrap();
        let identity = format!("{:x}", Sha256::digest(canonical.as_bytes()));
        let mut old_plan =
            compile_aircraft_support_with_profile(&inputs, SEMANTIC_PROFILE).unwrap();
        old_plan.source_inputs_sha256 = identity.clone();
        let fingerprint =
            ExecutionPlan::fingerprint(&serde_json::to_value(&old_plan).unwrap()).unwrap();
        let old_bytes =
            encode_plan_cache(old_plan, "aircraft-support-aot/v1alpha5", &fingerprint).unwrap();
        fs::create_dir_all(&cache).unwrap();
        let old_path = cache.join(plan_cache_file_name(
            &identity,
            None,
            "aircraft-support-aot/v1alpha5",
            SEMANTIC_PROFILE,
        ));
        fs::write(&old_path, old_bytes).unwrap();

        let result =
            run_canonical_batch(vec![request(0, 0, inputs)], Some(1), Some(&cache)).unwrap();
        assert_eq!(result.plan_cache_status, "miss");
        assert!(old_path.exists());
        assert!(cache.join(cache_file_name(&identity)).exists());
        fs::remove_dir_all(cache).unwrap();
    }

    #[test]
    fn stale_v1alpha5_envelope_under_current_name_is_rejected() {
        let cache = temporary_cache();
        let inputs = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        let canonical = ExecutionPlan::python_canonical(&inputs).unwrap();
        let identity = format!("{:x}", Sha256::digest(canonical.as_bytes()));
        let mut old_plan =
            compile_aircraft_support_with_profile(&inputs, SEMANTIC_PROFILE).unwrap();
        old_plan.source_inputs_sha256 = identity.clone();
        let fingerprint =
            ExecutionPlan::fingerprint(&serde_json::to_value(&old_plan).unwrap()).unwrap();
        let old_bytes =
            encode_plan_cache(old_plan, "aircraft-support-aot/v1alpha5", &fingerprint).unwrap();
        fs::create_dir_all(&cache).unwrap();
        fs::write(cache.join(cache_file_name(&identity)), old_bytes).unwrap();

        let result =
            run_canonical_batch(vec![request(0, 0, inputs)], Some(1), Some(&cache)).unwrap();
        assert_eq!(result.plan_cache_status, "rebuilt");
        assert!(
            result.cache_groups[0]
                .rebuild_reason
                .as_deref()
                .unwrap_or_default()
                .contains("compiler version")
        );
        fs::remove_dir_all(cache).unwrap();
    }

    #[test]
    fn stale_cache_cannot_bypass_reliability_validation() {
        let cache = temporary_cache();
        let mut valid = fixture("tests/fixtures/synthetic/b2-failure-repair.json");
        for component in valid["equipment_tree"]["components"]
            .as_array_mut()
            .unwrap()
        {
            component["component_type_id"] = component["id"].clone();
        }
        valid["equipment_tree"]["components"][1]["quantity"] = Value::from(3);
        valid["equipment_tree"]["components"][1]["k_out_of_n"] =
            serde_json::json!({"enabled": true, "k": 2, "n": 3});
        valid["equipment_tree"]["components"][1]
            .as_object_mut()
            .unwrap()
            .remove("failure_distribution");
        valid["equipment_tree"]["components"][1]["failure_rate_per_hour"] = Value::from(0.5);
        let mut old_plan = compile_aircraft_support_with_profile(&valid, SEMANTIC_PROFILE).unwrap();

        let mut invalid = valid.clone();
        invalid["equipment_tree"]["components"][1]["k_out_of_n"] =
            serde_json::json!({"enabled": true, "k": 2, "n": 2});
        let canonical = ExecutionPlan::python_canonical(&invalid).unwrap();
        let identity = format!("{:x}", Sha256::digest(canonical.as_bytes()));
        old_plan.source_inputs_sha256 = identity.clone();
        let fingerprint =
            ExecutionPlan::fingerprint(&serde_json::to_value(&old_plan).unwrap()).unwrap();
        let old_bytes =
            encode_plan_cache(old_plan, "aircraft-support-aot/v1alpha5", &fingerprint).unwrap();
        fs::create_dir_all(&cache).unwrap();
        fs::write(
            cache.join(plan_cache_file_name(
                &identity,
                None,
                "aircraft-support-aot/v1alpha5",
                SEMANTIC_PROFILE,
            )),
            old_bytes,
        )
        .unwrap();

        let result =
            run_canonical_batch(vec![request(0, 0, invalid)], Some(1), Some(&cache)).unwrap();
        assert!(result.samples.is_empty());
        assert_eq!(result.failed_samples.len(), 1);
        assert_eq!(result.failed_samples[0].stage, "compile");
        assert!(
            result.failed_samples[0]
                .error
                .contains("redundancy_n_mismatch")
        );
        fs::remove_dir_all(cache).unwrap();
    }

    #[test]
    fn rejects_empty_duplicate_and_zero_worker_requests() {
        assert!(run_canonical_batch(Vec::new(), Some(1), None).is_err());
        let inputs = fixture("tests/fixtures/synthetic/b1-daily-operations.json");
        assert!(run_canonical_batch(vec![request(0, 0, inputs.clone())], Some(0), None).is_err());
        assert!(
            run_canonical_batch(
                vec![request(0, 0, inputs.clone()), request(0, 1, inputs)],
                Some(1),
                None,
            )
            .is_err()
        );
    }
}
