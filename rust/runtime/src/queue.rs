//! Restricted two-server queue runtime.
//!
//! The event and random-call order is the same contract as
//! `domains/multi_server_queue/runtime.py`. This module does not interpret
//! aircraft plans and the aircraft runtime does not interpret queue plans.

use std::cmp::Ordering;

use anyhow::{Result, bail};
use serde::Serialize;
use serde_json::{Value, json};

use crate::plan::ExecutionPlan;
use crate::rng::PythonRandom;

pub const QUEUE_PLAN_VERSION: &str = "multi-server-queue-plan/v1";
const MAX_ADMITTED_ARRIVALS: i64 = 10_000;
const MAX_LOOP_STEPS: i64 = 100_000;

#[derive(Clone, Debug)]
struct Class {
    id: String,
    priority: i64,
    weight: i64,
}

#[derive(Clone, Debug)]
struct ServerSpec {
    id: String,
    index: usize,
    rate: f64,
    source_path: String,
}

#[derive(Clone, Debug)]
struct Plan {
    profile: String,
    semantic_profile: String,
    business_fingerprint: String,
    core_fingerprint: String,
    horizon: i64,
    arrival_rate: f64,
    classes: Vec<Class>,
    servers: Vec<ServerSpec>,
}

#[derive(Clone, Debug)]
struct Customer {
    id: String,
    class_id: String,
    priority: i64,
    arrival: f64,
    service: f64,
}

#[derive(Clone, Debug)]
struct ServerState {
    spec: ServerSpec,
    customer: Option<Customer>,
    busy_until: Option<f64>,
}

#[derive(Serialize)]
struct RunResult {
    plan_fingerprint: String,
    business_fingerprint: String,
    core_fingerprint: String,
    profile: String,
    semantic_profile: String,
    seed: u64,
    sample_index: i64,
    time: i64,
    stop_reason: String,
    sample_requests: Vec<Value>,
    trace: Vec<Value>,
    metrics: Value,
    terminal_state: Value,
}

#[derive(Serialize)]
struct BatchSample {
    sample_index: usize,
    seed: u64,
    result: RunResult,
}

#[derive(Serialize)]
struct BatchResult {
    plan_fingerprint: String,
    sample_count: usize,
    worker_threads: usize,
    until: Option<i64>,
    samples: Vec<BatchSample>,
}

fn expect_object<'a>(value: &'a Value, path: &str) -> Result<&'a serde_json::Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| anyhow::anyhow!("{path} must be an object"))
}

fn exact_keys(value: &Value, keys: &[&str], path: &str) -> Result<()> {
    let object = expect_object(value, path)?;
    let actual: std::collections::BTreeSet<_> = object.keys().cloned().collect();
    let expected: std::collections::BTreeSet<_> = keys.iter().map(|item| (*item).to_string()).collect();
    if actual != expected {
        bail!("{path} expected fields {keys:?}");
    }
    Ok(())
}

fn sha256_text(value: &str, path: &str) -> Result<()> {
    if value.len() != 64 || !value.chars().all(|ch| ch.is_ascii_hexdigit()) {
        bail!("{path} expected SHA-256");
    }
    Ok(())
}

fn parse_plan(raw: &Value) -> Result<Plan> {
    exact_keys(
        raw,
        &[
            "plan_version",
            "domain",
            "profile",
            "semantic_profile",
            "work_policy",
            "rng_profile",
            "source_inputs_sha256",
            "business_fingerprint",
            "core_fingerprint",
            "duration_minutes",
            "horizon_minutes",
            "arrival_rate_per_minute",
            "classes",
            "servers",
            "priority_rule",
            "metrics",
            "operations",
            "limits",
        ],
        "plan",
    )?;
    let plan_version = raw["plan_version"].as_str().unwrap_or("");
    if plan_version != QUEUE_PLAN_VERSION {
        bail!("unsupported plan version {plan_version:?}");
    }
    if raw["domain"] != "multi-server-queue" || raw["profile"] != "multi-server-queue-v1" {
        bail!("unsupported queue profile");
    }
    if raw["semantic_profile"] != "event-time-queue-v1"
        || raw["work_policy"] != "nonpreemptive-priority"
        || raw["rng_profile"] != "cpython-mt19937-v1"
    {
        bail!("unsupported queue execution contract");
    }
    for field in ["source_inputs_sha256", "business_fingerprint", "core_fingerprint"] {
        sha256_text(raw[field].as_str().unwrap_or(""), &format!("plan.{field}"))?;
    }
    let horizon = raw["duration_minutes"].as_i64().ok_or_else(|| anyhow::anyhow!("invalid horizon"))?;
    if !(1..=10_080).contains(&horizon) || raw["horizon_minutes"] != horizon {
        bail!("horizon_minutes must equal duration_minutes");
    }
    let arrival_rate = raw["arrival_rate_per_minute"]
        .as_f64()
        .ok_or_else(|| anyhow::anyhow!("invalid arrival rate"))?;
    if !(arrival_rate.is_finite() && arrival_rate > 0.0 && arrival_rate <= 1_000_000.0) {
        bail!("invalid arrival rate");
    }
    if arrival_rate * horizon as f64 > MAX_ADMITTED_ARRIVALS as f64 {
        bail!("expected arrivals exceed the restricted profile limit");
    }
    let expected_operations: Value = serde_json::from_str(include_str!(
        "../../../tests/fixtures/queue/operations.json"
    ))?;
    if &raw["operations"] != &expected_operations {
        bail!("unknown or incomplete queue operation contract");
    }
    if raw["limits"] != json!({"max_admitted_arrivals": MAX_ADMITTED_ARRIVALS, "max_loop_steps": MAX_LOOP_STEPS}) {
        bail!("queue resource limits are fixed by the restricted profile");
    }
    if raw["metrics"] != json!(["mean_wait"]) {
        bail!("the admitted metric set is exactly ['mean_wait']");
    }
    let class_values = raw["classes"].as_array().ok_or_else(|| anyhow::anyhow!("classes must be a list"))?;
    if !(1..=8).contains(&class_values.len()) {
        bail!("expected 1 to 8 arrival classes");
    }
    let server_values = raw["servers"].as_array().ok_or_else(|| anyhow::anyhow!("servers must be a list"))?;
    if server_values.len() != 2 {
        bail!("this restricted profile requires exactly two servers");
    }
    let mut seen = std::collections::BTreeSet::new();
    let mut classes = Vec::new();
    for (index, item) in class_values.iter().enumerate() {
        exact_keys(item, &["id", "priority", "weight", "source_path"], "plan.classes")?;
        let id = item["id"].as_str().unwrap_or("").to_string();
        if id.is_empty() || !seen.insert(id.clone()) {
            bail!("duplicate class id");
        }
        let source = item["source_path"].as_str().unwrap_or("");
        if source != format!("arrivals.classes[{index}]") {
            bail!("class source path does not match its position");
        }
        let weight = item["weight"]
            .as_i64()
            .filter(|weight| (1..=1_000_000).contains(weight))
            .ok_or_else(|| {
                anyhow::anyhow!("plan.classes[{index}].weight must be an integer in [1, 1000000]")
            })?;
        classes.push(Class {
            id,
            priority: item["priority"].as_i64().ok_or_else(|| anyhow::anyhow!("invalid priority"))?,
            weight,
        });
    }
    let mut servers = Vec::new();
    for (index, item) in server_values.iter().enumerate() {
        exact_keys(item, &["id", "index", "service_rate_per_minute", "source_path"], "plan.servers")?;
        let id = item["id"].as_str().unwrap_or("").to_string();
        if id.is_empty() || !seen.insert(id.clone()) || item["index"] != index as i64 {
            bail!("invalid or duplicate server identity");
        }
        if item["source_path"] != format!("servers[{index}]") {
            bail!("server source path does not match its position");
        }
        let rate = item["service_rate_per_minute"].as_f64().ok_or_else(|| anyhow::anyhow!("invalid service rate"))?;
        if !(rate.is_finite() && rate > 0.0) {
            bail!("invalid service rate");
        }
        servers.push(ServerSpec {
            id,
            index,
            rate,
            source_path: item["source_path"].as_str().unwrap_or("").to_string(),
        });
    }
    exact_keys(
        &raw["priority_rule"],
        &["discipline", "id", "ordering", "server_choice", "source_path"],
        "plan.priority_rule",
    )?;
    let rule = &raw["priority_rule"];
    if rule["discipline"] != "nonpreemptive-priority"
        || rule["ordering"] != json!(["priority_descending", "arrival_time", "customer_id"])
        || rule["server_choice"] != "lowest_index_idle"
        || rule["source_path"] != "priority_rule"
        || seen.contains(rule["id"].as_str().unwrap_or(""))
    {
        bail!("unsupported priority rule");
    }
    Ok(Plan {
        profile: "multi-server-queue-v1".to_string(),
        semantic_profile: "event-time-queue-v1".to_string(),
        business_fingerprint: raw["business_fingerprint"].as_str().unwrap().to_string(),
        core_fingerprint: raw["core_fingerprint"].as_str().unwrap().to_string(),
        horizon,
        arrival_rate,
        classes,
        servers,
    })
}

fn expovariate(rng: &mut PythonRandom, rate: f64) -> f64 {
    -(1.0 - rng.random()).ln() / rate
}

fn customer_id(number: i64) -> String {
    format!("customer-{number:04}")
}

struct Engine {
    rng: PythonRandom,
    requests: Vec<Value>,
    trace: Vec<Value>,
    ordered: Vec<Class>,
    weights: Value,
    total_weight: i64,
}

impl Engine {
    fn draw_exp(&mut self, stream_id: &str, rate: f64, time: f64, purpose: &str) -> f64 {
        let value = expovariate(&mut self.rng, rate);
        self.requests.push(json!({
            "sequence": self.requests.len() + 1,
            "stream_id": stream_id,
            "distribution": "exponential",
            "rate_per_minute": rate,
            "value_minutes": value,
            "time_minutes": time,
            "purpose": purpose,
        }));
        value
    }

    fn draw_class(&mut self, stream_id: &str, time: f64) -> Class {
        let uniform = self.rng.random();
        let point = uniform * self.total_weight as f64;
        let mut cumulative = 0i64;
        let mut chosen = self.ordered.last().unwrap().clone();
        for item in &self.ordered {
            cumulative += item.weight;
            if point < cumulative as f64 {
                chosen = item.clone();
                break;
            }
        }
        self.requests.push(json!({
            "sequence": self.requests.len() + 1,
            "stream_id": stream_id,
            "distribution": "weighted_class",
            "u": uniform,
            "value": chosen.id,
            "weights": self.weights,
            "time_minutes": time,
            "purpose": "class",
        }));
        chosen
    }

    fn emit(&mut self, kind: &str, rule_id: &str, entity: &str, source_path: &str, time: f64, phase: &str, details: Value) {
        self.trace.push(json!({
            "sequence": self.trace.len() + 1,
            "time": time,
            "phase": phase,
            "kind": kind,
            "rule_id": rule_id,
            "entity": entity,
            "source_path": source_path,
            "details": details,
        }));
    }
}

fn execute(plan: &Plan, fingerprint: String, seed: u64, sample_index: i64, observation: &str, until: Option<i64>) -> Result<RunResult> {
    if observation != "full" && observation != "summary" {
        bail!("observation must be full or summary");
    }
    let mut horizon = plan.horizon;
    if let Some(until) = until {
        if until < 0 || until > plan.horizon {
            bail!("until is outside the plan horizon");
        }
        horizon = until;
    }
    let mut ordered = plan.classes.clone();
    ordered.sort_by(|left, right| left.id.cmp(&right.id));
    let weights = Value::Array(
        ordered.iter().map(|item| json!([item.id, item.weight])).collect(),
    );
    let total_weight: i64 = ordered.iter().map(|item| item.weight).sum();
    let mut engine = Engine {
        rng: PythonRandom::from_u64(seed),
        requests: Vec::new(),
        trace: Vec::new(),
        ordered,
        weights,
        total_weight,
    };
    let mut servers: Vec<ServerState> = plan
        .servers
        .iter()
        .cloned()
        .map(|spec| ServerState { spec, customer: None, busy_until: None })
        .collect();
    let mut waiting: Vec<Customer> = Vec::new();
    let mut waits: Vec<f64> = Vec::new();
    let mut completed: Vec<String> = Vec::new();
    let mut arrivals = 0i64;
    let mut starts = 0i64;
    let mut completions = 0i64;
    let mut ordinal = 1i64;

    let fill = |engine: &mut Engine, servers: &mut [ServerState], waiting: &mut Vec<Customer>, waits: &mut Vec<f64>, starts: &mut i64, now: f64| {
        loop {
            let idle = servers.iter().any(|server| server.customer.is_none());
            if waiting.is_empty() || !idle {
                break;
            }
            waiting.sort_by(|left, right| {
                right.priority.cmp(&left.priority)
                    .then(left.arrival.partial_cmp(&right.arrival).unwrap_or(Ordering::Equal))
                    .then(left.id.cmp(&right.id))
            });
            let mut customer = waiting.remove(0);
            let server_index = servers.iter().position(|server| server.customer.is_none()).unwrap();
            let service = engine.draw_exp(&format!("service:{}", customer.id), servers[server_index].spec.rate, now, "service");
            customer.service = service;
            let wait = now - customer.arrival;
            waits.push(wait);
            *starts += 1;
            let server_id = servers[server_index].spec.id.clone();
            let source_path = servers[server_index].spec.source_path.clone();
            let class_id = customer.class_id.clone();
            let priority = customer.priority;
            let entity = customer.id.clone();
            engine.emit(
                "service_started",
                "queue.nonpreemptive_priority_seize/v1",
                &entity,
                &source_path,
                now,
                "service",
                json!({
                    "server_id": server_id,
                    "class_id": class_id,
                    "priority": priority,
                    "wait_minutes": wait,
                    "service_minutes": service,
                }),
            );
            servers[server_index].busy_until = Some(now + service);
            servers[server_index].customer = Some(customer);
        }
    };

    let first_id = customer_id(ordinal);
    ordinal += 1;
    let mut next_arrival = engine.draw_exp(
        &format!("interarrival:{first_id}"),
        plan.arrival_rate,
        0.0,
        "interarrival",
    );
    let mut next_id = first_id;
    let mut steps = 0i64;
    loop {
        steps += 1;
        if steps > MAX_LOOP_STEPS {
            bail!("queue step limit exceeded");
        }
        let mut best: Option<(f64, i64, i64, u8)> = None;
        if next_arrival < horizon as f64 {
            best = Some((next_arrival, 1, -1, 0));
        }
        for server in &servers {
            if server.customer.is_some() && server.busy_until.unwrap() <= horizon as f64 {
                let candidate = (server.busy_until.unwrap(), 0, server.spec.index as i64, 1);
                best = Some(match best {
                    None => candidate,
                    Some(current) => {
                        let order = candidate.0.partial_cmp(&current.0).unwrap()
                            .then(candidate.1.cmp(&current.1))
                            .then(candidate.2.cmp(&current.2));
                        if order == Ordering::Less { candidate } else { current }
                    }
                });
            }
        }
        let Some((when, _rank, index, kind)) = best else { break };
        if kind == 0 {
            if arrivals >= MAX_ADMITTED_ARRIVALS {
                bail!("admitted arrival limit exceeded");
            }
            let chosen = engine.draw_class(&format!("class:{next_id}"), when);
            let customer = Customer {
                id: next_id.clone(),
                class_id: chosen.id.clone(),
                priority: chosen.priority,
                arrival: when,
                service: 0.0,
            };
            waiting.push(customer);
            arrivals += 1;
            engine.emit(
                "customer_arrived",
                "queue.poisson_arrival/v1",
                &next_id,
                "arrivals",
                when,
                "arrival",
                json!({"class_id": chosen.id, "priority": chosen.priority, "arrival_time": when}),
            );
            fill(&mut engine, &mut servers, &mut waiting, &mut waits, &mut starts, when);
            if ordinal > MAX_ADMITTED_ARRIVALS {
                bail!("admitted arrival limit exceeded");
            }
            let upcoming = customer_id(ordinal);
            ordinal += 1;
            next_arrival = when + engine.draw_exp(
                &format!("interarrival:{upcoming}"),
                plan.arrival_rate,
                when,
                "interarrival",
            );
            next_id = upcoming;
        } else {
            let server = &mut servers[index as usize];
            let customer = server.customer.take().unwrap();
            let busy_until = server.busy_until.take();
            let _ = busy_until;
            let server_id = server.spec.id.clone();
            let source_path = server.spec.source_path.clone();
            engine.emit(
                "service_completed",
                "queue.exponential_service/v1",
                &customer.id,
                &source_path,
                when,
                "service",
                json!({
                    "server_id": server_id,
                    "class_id": customer.class_id,
                    "service_minutes": customer.service,
                }),
            );
            completions += 1;
            completed.push(customer.id);
            fill(&mut engine, &mut servers, &mut waiting, &mut waits, &mut starts, when);
        }
    }
    engine.emit(
        "simulation_stopped",
        "stop.horizon",
        "simulation",
        "horizon",
        horizon as f64,
        "stop",
        json!({"reason": "horizon"}),
    );
    let mean = if waits.is_empty() {
        Value::Null
    } else {
        json!(waits.iter().sum::<f64>() / waits.len() as f64)
    };
    let terminal_servers: Vec<Value> = servers
        .iter()
        .map(|server| {
            json!({
                "id": server.spec.id,
                "index": server.spec.index,
                "state": if server.customer.is_none() { "idle" } else { "busy" },
                "customer_id": server.customer.as_ref().map(|customer| customer.id.clone()),
                "remaining_minutes": if server.customer.is_none() { 0.0 } else { server.busy_until.unwrap() - horizon as f64 },
            })
        })
        .collect();
    let terminal_waiting: Vec<Value> = waiting
        .iter()
        .map(|customer| {
            json!({
                "id": customer.id,
                "class_id": customer.class_id,
                "priority": customer.priority,
                "arrival_time": customer.arrival,
            })
        })
        .collect();
    Ok(RunResult {
        plan_fingerprint: fingerprint,
        business_fingerprint: plan.business_fingerprint.clone(),
        core_fingerprint: plan.core_fingerprint.clone(),
        profile: plan.profile.clone(),
        semantic_profile: plan.semantic_profile.clone(),
        seed,
        sample_index,
        time: horizon,
        stop_reason: "horizon".to_string(),
        sample_requests: engine.requests,
        trace: if observation == "summary" { Vec::new() } else { engine.trace },
        metrics: json!({
            "mean_wait": mean,
            "wait_count": waits.len(),
            "arrival_count": arrivals,
            "service_start_count": starts,
            "service_completion_count": completions,
        }),
        terminal_state: json!({
            "waiting": terminal_waiting,
            "servers": terminal_servers,
            "completed_customer_ids": completed,
        }),
    })
}

pub fn run_queue_plan_json(plan_json: &str, seed: u64, sample_index: i64, until: Option<i64>, observation: &str) -> Result<String> {
    let raw: Value = serde_json::from_str(plan_json)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    let plan = parse_plan(&raw)?;
    let result = execute(&plan, fingerprint, seed, sample_index, observation, until)?;
    Ok(serde_json::to_string(&result)?)
}

pub fn run_queue_batch_json(plan_json: &str, seeds: &[u64], worker_threads: Option<usize>, until: Option<i64>, observation: &str) -> Result<String> {
    if seeds.is_empty() {
        bail!("at least one seed is required");
    }
    let threads = worker_threads.unwrap_or(1);
    if threads == 0 {
        bail!("worker_threads must be positive");
    }
    let raw: Value = serde_json::from_str(plan_json)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    let plan = parse_plan(&raw)?;
    let mut samples = Vec::with_capacity(seeds.len());
    for (sample_index, seed) in seeds.iter().copied().enumerate() {
        samples.push(BatchSample {
            sample_index,
            seed,
            result: execute(&plan, fingerprint.clone(), seed, sample_index as i64, observation, until)?,
        });
    }
    let result = BatchResult {
        plan_fingerprint: fingerprint,
        sample_count: seeds.len(),
        worker_threads: threads,
        until,
        samples,
    };
    Ok(serde_json::to_string(&result)?)
}

pub fn is_queue_plan(value: &Value) -> bool {
    value.get("plan_version").and_then(Value::as_str) == Some(QUEUE_PLAN_VERSION)
}

#[cfg(test)]
mod tests {
    use super::{parse_plan, run_queue_plan_json};
    use crate::plan::ExecutionPlan;
    use serde_json::{Value, json};

    #[test]
    fn fixture_plan_draws_real_requests_and_repeats() {
        let bytes = include_str!("../../../tests/fixtures/queue/plan.json");
        let raw: Value = serde_json::from_str(bytes).unwrap();
        parse_plan(&raw).unwrap();
        let fingerprint = ExecutionPlan::fingerprint(&raw).unwrap();
        assert_eq!(fingerprint, "a5ded517114641e591acf91e328537d72614caf5f2ae01cb80d204203a8be3a1");
        let first = run_queue_plan_json(bytes, 0, 0, None, "full").unwrap();
        let second = run_queue_plan_json(bytes, 0, 0, None, "full").unwrap();
        assert_eq!(first, second);
        let parsed: Value = serde_json::from_str(&first).unwrap();
        assert!(parsed["sample_requests"].as_array().unwrap().len() > 1);
        assert_eq!(parsed["sample_requests"][0]["purpose"], "interarrival");
        assert!(parsed["sample_requests"][0]["value_minutes"].as_f64().unwrap() > 0.0);
        assert!(parsed["metrics"]["arrival_count"].as_i64().unwrap() > 0);
    }

    #[test]
    fn validates_class_weight_bounds() {
        let mut raw: Value =
            serde_json::from_str(include_str!("../../../tests/fixtures/queue/plan.json")).unwrap();
        for weight in [json!(1), json!(1_000_000)] {
            raw["classes"][0]["weight"] = weight;
            parse_plan(&raw).unwrap();
        }
        for weight in [json!(-1), json!(0), json!(1_000_001), json!(true), json!(1.5)] {
            raw["classes"][0]["weight"] = weight;
            let error = parse_plan(&raw).err().expect("invalid weight must be rejected");
            assert_eq!(
                error.to_string(),
                "plan.classes[0].weight must be an integer in [1, 1000000]"
            );
        }
    }

    #[test]
    fn rejects_a_third_server() {
        let mut raw: Value = serde_json::from_str(include_str!("../../../tests/fixtures/queue/plan.json")).unwrap();
        let server = raw["servers"][0].clone();
        raw["servers"].as_array_mut().unwrap().push(server);
        assert!(parse_plan(&raw).is_err());
    }
}
