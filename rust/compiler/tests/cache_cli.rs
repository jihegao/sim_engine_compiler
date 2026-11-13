use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Output},
    time::{SystemTime, UNIX_EPOCH},
};

use serde_json::Value;
use sha2::{Digest, Sha256};
use sim_engine_compiler_aot::{
    COMPILER_VERSION, compile_aircraft_support_with_profile, plan_cache_file_name,
};
use sim_engine_runtime::{ExecutionPlan, encode_plan_cache};

const OLD_COMPILER: &str = "aircraft-support-aot/v1alpha5";
const PROFILE: &str = "event-time-v2";

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn temporary_dir() -> PathBuf {
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    std::env::temp_dir().join(format!(
        "sim-engine-cache-cli-{}-{stamp}",
        std::process::id()
    ))
}

fn run(input: &Path, output: &Path, cache: &Path) -> Output {
    Command::new(env!("CARGO_BIN_EXE_sim-engine-compiler-aot"))
        .arg(input)
        .arg(output)
        .arg("--cache-dir")
        .arg(cache)
        .arg("--semantic-profile")
        .arg(PROFILE)
        .output()
        .unwrap()
}

fn run_with_project(
    input: &Path,
    project: &Path,
    adapter: &str,
    output: &Path,
    cache: &Path,
) -> Output {
    Command::new(env!("CARGO_BIN_EXE_sim-engine-compiler-aot"))
        .arg(input)
        .arg(output)
        .arg("--cache-dir")
        .arg(cache)
        .arg("--semantic-profile")
        .arg(PROFILE)
        .arg("--project-json")
        .arg(project)
        .arg("--adapter-contract-version")
        .arg(adapter)
        .output()
        .unwrap()
}

fn cache_hit(output: &Output) -> bool {
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    value["cache_hit"].as_bool().unwrap()
}

fn stale_cache_bytes(inputs: &Value, identity: &str) -> Vec<u8> {
    let mut plan = compile_aircraft_support_with_profile(inputs, PROFILE).unwrap();
    plan.source_inputs_sha256 = identity.to_owned();
    let fingerprint = ExecutionPlan::fingerprint(&serde_json::to_value(&plan).unwrap()).unwrap();
    encode_plan_cache(plan, OLD_COMPILER, &fingerprint).unwrap()
}

fn identity(inputs: &Value) -> String {
    let canonical = ExecutionPlan::python_canonical(inputs).unwrap();
    format!("{:x}", Sha256::digest(canonical.as_bytes()))
}

fn project_cache_identity(project: &Value, input: &Value) -> String {
    let project_identity = identity(project);
    let input_identity = identity(input);
    format!(
        "{:x}",
        Sha256::digest(format!("{project_identity}:{input_identity}").as_bytes())
    )
}

fn write_json(path: &Path, value: &Value) {
    fs::write(path, serde_json::to_vec(value).unwrap()).unwrap();
}

fn plan_fingerprint(output: &Output) -> String {
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    value["plan_fingerprint"].as_str().unwrap().to_owned()
}

#[test]
fn cli_ignores_old_compiler_cache_and_then_hits_new_cache() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let input_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let inputs: Value = serde_json::from_slice(&fs::read(&input_path).unwrap()).unwrap();
    let input_identity = identity(&inputs);
    let old_path = cache.join(plan_cache_file_name(
        &input_identity,
        None,
        OLD_COMPILER,
        PROFILE,
    ));
    fs::create_dir_all(&cache).unwrap();
    fs::write(&old_path, stale_cache_bytes(&inputs, &input_identity)).unwrap();

    let first = run(&input_path, &directory.join("first.seplan"), &cache);
    assert!(
        first.status.success(),
        "{}",
        String::from_utf8_lossy(&first.stderr)
    );
    assert!(!cache_hit(&first));
    assert!(old_path.exists());
    assert!(
        cache
            .join(plan_cache_file_name(
                &input_identity,
                None,
                COMPILER_VERSION,
                PROFILE,
            ))
            .exists()
    );

    let second = run(&input_path, &directory.join("second.seplan"), &cache);
    assert!(
        second.status.success(),
        "{}",
        String::from_utf8_lossy(&second.stderr)
    );
    assert!(cache_hit(&second));

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn project_json_cache_lookup_ignores_old_compiler_identity() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let input_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let project_path = input_path.clone();
    let inputs: Value = serde_json::from_slice(&fs::read(&input_path).unwrap()).unwrap();
    let project_identity = identity(&inputs);
    let cache_identity = project_cache_identity(&inputs, &inputs);
    let adapter = "adapter/v1";
    let adapter_digest = format!("{:x}", Sha256::digest(adapter.as_bytes()));
    let old_path = cache.join(plan_cache_file_name(
        &project_identity,
        Some(&adapter_digest),
        OLD_COMPILER,
        PROFILE,
    ));
    fs::create_dir_all(&cache).unwrap();
    fs::write(&old_path, stale_cache_bytes(&inputs, &project_identity)).unwrap();

    let first = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("first.seplan"),
        &cache,
    );
    assert!(
        first.status.success(),
        "{}",
        String::from_utf8_lossy(&first.stderr)
    );
    assert!(!cache_hit(&first));
    assert!(old_path.exists());
    assert!(
        cache
            .join(plan_cache_file_name(
                &cache_identity,
                Some(&adapter_digest),
                COMPILER_VERSION,
                PROFILE,
            ))
            .exists()
    );

    let second = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("second.seplan"),
        &cache,
    );
    assert!(
        second.status.success(),
        "{}",
        String::from_utf8_lossy(&second.stderr)
    );
    assert!(cache_hit(&second));

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn project_cache_cannot_bypass_invalid_failure_threshold() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let project_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let project: Value = serde_json::from_slice(&fs::read(&project_path).unwrap()).unwrap();
    let input_path = directory.join("input.json");
    fs::create_dir_all(&directory).unwrap();
    write_json(&input_path, &project);
    let adapter = "adapter/v1";
    let adapter_digest = format!("{:x}", Sha256::digest(adapter.as_bytes()));
    let expected_cache = cache.join(plan_cache_file_name(
        &project_cache_identity(&project, &project),
        Some(&adapter_digest),
        COMPILER_VERSION,
        PROFILE,
    ));

    let first = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("first.seplan"),
        &cache,
    );
    assert!(
        first.status.success(),
        "{}",
        String::from_utf8_lossy(&first.stderr)
    );
    assert!(!cache_hit(&first));
    assert!(expected_cache.exists());

    let mut invalid = project.clone();
    invalid["equipment_tree"]["components"][0]["failure_threshold"] = Value::from(2);
    write_json(&input_path, &invalid);

    let second = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("second.seplan"),
        &cache,
    );
    assert!(!second.status.success());
    let stderr = String::from_utf8_lossy(&second.stderr);
    assert!(stderr.contains("failure_threshold_in_new_plan"), "{stderr}");
    assert!(
        stderr.contains("equipment_tree.components[0].failure_threshold"),
        "{stderr}"
    );

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn project_cache_cannot_bypass_invalid_k_out_of_n() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let project_path = directory.join("project.json");
    let input_path = directory.join("input.json");
    fs::create_dir_all(&directory).unwrap();
    let mut project: Value = serde_json::from_slice(
        &fs::read(root().join("tests/fixtures/synthetic/b2-failure-repair.json")).unwrap(),
    )
    .unwrap();
    for component in project["equipment_tree"]["components"]
        .as_array_mut()
        .unwrap()
    {
        component["component_type_id"] = component["id"].clone();
    }
    project["equipment_tree"]["components"][1]["quantity"] = Value::from(3);
    project["equipment_tree"]["components"][1]["k_out_of_n"] =
        serde_json::json!({"enabled": true, "k": 2, "n": 3});
    project["equipment_tree"]["components"][1]
        .as_object_mut()
        .unwrap()
        .remove("failure_distribution");
    project["equipment_tree"]["components"][1]["failure_rate_per_hour"] = Value::from(0.5);
    write_json(&project_path, &project);
    write_json(&input_path, &project);
    let adapter = "adapter/v1";
    let adapter_digest = format!("{:x}", Sha256::digest(adapter.as_bytes()));
    let expected_cache = cache.join(plan_cache_file_name(
        &project_cache_identity(&project, &project),
        Some(&adapter_digest),
        COMPILER_VERSION,
        PROFILE,
    ));

    let first = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("first.seplan"),
        &cache,
    );
    assert!(
        first.status.success(),
        "{}",
        String::from_utf8_lossy(&first.stderr)
    );
    assert!(!cache_hit(&first));
    assert!(expected_cache.exists());

    let mut invalid = project.clone();
    invalid["equipment_tree"]["components"][1]["k_out_of_n"] =
        serde_json::json!({"enabled": true, "k": 2, "n": 2});
    write_json(&input_path, &invalid);

    let second = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("second.seplan"),
        &cache,
    );
    assert!(!second.status.success());
    let stderr = String::from_utf8_lossy(&second.stderr);
    assert!(stderr.contains("redundancy_n_mismatch"), "{stderr}");

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn project_cache_recompiles_when_valid_input_changes() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let project_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let project: Value = serde_json::from_slice(&fs::read(&project_path).unwrap()).unwrap();
    let input_path = directory.join("input.json");
    fs::create_dir_all(&directory).unwrap();
    write_json(&input_path, &project);
    let adapter = "adapter/v1";

    let first = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("first.seplan"),
        &cache,
    );
    assert!(
        first.status.success(),
        "{}",
        String::from_utf8_lossy(&first.stderr)
    );
    assert!(!cache_hit(&first));
    let first_fingerprint = plan_fingerprint(&first);

    let mut changed = project.clone();
    changed["time"]["duration_minutes"] = Value::from(90);
    write_json(&input_path, &changed);

    let second = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("second.seplan"),
        &cache,
    );
    assert!(
        second.status.success(),
        "{}",
        String::from_utf8_lossy(&second.stderr)
    );
    assert!(!cache_hit(&second));
    let second_fingerprint = plan_fingerprint(&second);
    assert_ne!(first_fingerprint, second_fingerprint);

    let third = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("third.seplan"),
        &cache,
    );
    assert!(
        third.status.success(),
        "{}",
        String::from_utf8_lossy(&third.stderr)
    );
    assert!(cache_hit(&third));
    assert_eq!(plan_fingerprint(&third), second_fingerprint);

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn project_cache_hits_for_identical_input() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let project_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let project: Value = serde_json::from_slice(&fs::read(&project_path).unwrap()).unwrap();
    let input_path = directory.join("input.json");
    fs::create_dir_all(&directory).unwrap();
    write_json(&input_path, &project);
    let adapter = "adapter/v1";

    let first = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("first.seplan"),
        &cache,
    );
    assert!(
        first.status.success(),
        "{}",
        String::from_utf8_lossy(&first.stderr)
    );
    assert!(!cache_hit(&first));
    let first_fingerprint = plan_fingerprint(&first);

    let second = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("second.seplan"),
        &cache,
    );
    assert!(
        second.status.success(),
        "{}",
        String::from_utf8_lossy(&second.stderr)
    );
    assert!(cache_hit(&second));
    assert_eq!(plan_fingerprint(&second), first_fingerprint);

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn project_json_rejects_old_envelope_under_current_cache_name() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let project_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let project: Value = serde_json::from_slice(&fs::read(&project_path).unwrap()).unwrap();
    let adapter = "adapter/v1";
    let adapter_digest = format!("{:x}", Sha256::digest(adapter.as_bytes()));
    fs::create_dir_all(&cache).unwrap();
    fs::write(
        cache.join(plan_cache_file_name(
            &project_cache_identity(&project, &project),
            Some(&adapter_digest),
            COMPILER_VERSION,
            PROFILE,
        )),
        stale_cache_bytes(&project, &identity(&project)),
    )
    .unwrap();

    let output = run_with_project(
        &project_path,
        &project_path,
        adapter,
        &directory.join("plan.seplan"),
        &cache,
    );
    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("cached compiler version"), "{stderr}");

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn project_json_rejects_current_cache_for_different_input() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let project_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let project: Value = serde_json::from_slice(&fs::read(&project_path).unwrap()).unwrap();
    let mut changed = project.clone();
    changed["time"]["duration_minutes"] = Value::from(90);
    let input_path = directory.join("input.json");
    fs::create_dir_all(&directory).unwrap();
    write_json(&input_path, &changed);
    let adapter = "adapter/v1";
    let adapter_digest = format!("{:x}", Sha256::digest(adapter.as_bytes()));
    let plan = compile_aircraft_support_with_profile(&project, PROFILE).unwrap();
    let fingerprint = ExecutionPlan::fingerprint(&serde_json::to_value(&plan).unwrap()).unwrap();
    let bytes = encode_plan_cache(plan, COMPILER_VERSION, &fingerprint).unwrap();
    fs::create_dir_all(&cache).unwrap();
    fs::write(
        cache.join(plan_cache_file_name(
            &project_cache_identity(&project, &changed),
            Some(&adapter_digest),
            COMPILER_VERSION,
            PROFILE,
        )),
        bytes,
    )
    .unwrap();

    let output = run_with_project(
        &input_path,
        &project_path,
        adapter,
        &directory.join("plan.seplan"),
        &cache,
    );
    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("source fingerprint does not match"),
        "{stderr}"
    );

    fs::remove_dir_all(directory).unwrap();
}

#[test]
fn cli_rejects_old_envelope_under_current_cache_name() {
    let directory = temporary_dir();
    let cache = directory.join("cache");
    let input_path = root().join("tests/fixtures/synthetic/b1-daily-operations.json");
    let inputs: Value = serde_json::from_slice(&fs::read(&input_path).unwrap()).unwrap();
    let input_identity = identity(&inputs);
    fs::create_dir_all(&cache).unwrap();
    fs::write(
        cache.join(plan_cache_file_name(
            &input_identity,
            None,
            COMPILER_VERSION,
            PROFILE,
        )),
        stale_cache_bytes(&inputs, &input_identity),
    )
    .unwrap();

    let output = run(&input_path, &directory.join("plan.seplan"), &cache);
    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("cached compiler version"), "{stderr}");

    fs::remove_dir_all(directory).unwrap();
}
