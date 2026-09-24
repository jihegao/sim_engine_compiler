//! Experimental domain-neutral execution kernel; see ../SPEC.md.
//! Immutable plans are shared; every sample owns its state and event calendar.
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::cmp::Reverse;
use std::collections::{BTreeMap, BTreeSet, BinaryHeap, HashSet};
use std::io::{self, Read};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};
use std::time::Instant;

const PROFILE: &str = "ir-native-event-v1";
const EVENT_BUDGET: u64 = 10_000_000;
const ACTIVATE: u8 = 0;
const RETRY: u8 = 1;
const COMPLETE: u8 = 2;
const EXPLICIT: u8 = 3;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Asset {
    id: String,
    initial_state: i64,
}
#[derive(Debug, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum ResourceKind {
    Capacity,
    Stock,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Resource {
    id: String,
    kind: ResourceKind,
    initial: i64,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Process {
    id: String,
    candidates: Vec<usize>,
    required_state: i64,
    finish_state: i64,
    needs: Vec<(usize, i64)>,
    duration: [i64; 2],
    after: Vec<usize>,
    release: Option<i64>,
    interruptible: bool,
    #[serde(default)]
    repeat_delay: Option<i64>,
}
#[derive(Debug, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum Operation {
    SetState,
    AddStock,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ExplicitEvent {
    id: String,
    time: i64,
    op: Operation,
    target: usize,
    value: i64,
    trigger: Option<usize>,
    #[serde(default)]
    repeat_every: Option<i64>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Plan {
    schema: String,
    profile: String,
    time_unit: String,
    horizon: i64,
    model_id: String,
    revision: String,
    business_fingerprint: String,
    core_fingerprint: String,
    fingerprint: String,
    source_map: BTreeMap<String, String>,
    assets: Vec<Asset>,
    resources: Vec<Resource>,
    processes: Vec<Process>,
    events: Vec<ExplicitEvent>,
    successors: Vec<Vec<usize>>,
}
fn one() -> usize {
    1
}
fn yes() -> bool {
    true
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    plan: Plan,
    seeds: Vec<u32>,
    #[serde(default = "one")]
    repeats: usize,
    #[serde(default = "one")]
    threads: usize,
    #[serde(default = "yes")]
    trace: bool,
}

impl Plan {
    fn validate(&self) -> Result<(), String> {
        if self.schema != "plan/v1" || self.profile != PROFILE || self.time_unit != "tick" {
            return Err("unsupported plan schema, profile, or time unit".into());
        }
        if self.horizon < 0
            || self.model_id.is_empty()
            || self.model_id.contains('|')
            || self.revision.is_empty()
            || self.revision.contains('|')
            || self.fingerprint.is_empty()
        {
            return Err("invalid horizon or model identity".into());
        }
        // Metadata is retained by the plan but never consulted for dispatch.
        let _ = (
            &self.revision,
            &self.business_fingerprint,
            &self.core_fingerprint,
            &self.source_map,
        );
        let unique = |ids: Vec<&str>| -> bool {
            let mut seen = HashSet::new();
            ids.into_iter()
                .all(|id| !id.is_empty() && !id.contains('|') && seen.insert(id))
        };
        if !unique(self.assets.iter().map(|x| x.id.as_str()).collect())
            || !unique(self.resources.iter().map(|x| x.id.as_str()).collect())
            || !unique(self.processes.iter().map(|x| x.id.as_str()).collect())
            || !unique(self.events.iter().map(|x| x.id.as_str()).collect())
        {
            return Err("duplicate or empty stable identity".into());
        }
        if self
            .assets
            .iter()
            .any(|a| !(0..=1).contains(&a.initial_state))
            || self.resources.iter().any(|r| r.initial < 0)
        {
            return Err("invalid initial state or quantity".into());
        }
        let n = self.processes.len();
        let mut expected = vec![Vec::new(); n];
        for (i, p) in self.processes.iter().enumerate() {
            if p.duration[0] < 0
                || p.duration[1] < p.duration[0]
                || p.release.is_some_and(|t| t < 0)
                || p.repeat_delay.is_some_and(|t| t <= 0)
                || !(0..=1).contains(&p.required_state)
                || !(0..=1).contains(&p.finish_state)
                || p.candidates.iter().any(|&a| a >= self.assets.len())
                || p.candidates.iter().collect::<HashSet<_>>().len() != p.candidates.len()
            {
                return Err(format!("invalid process {}", p.id));
            }
            let mut seen = HashSet::new();
            for &(r, q) in &p.needs {
                if r >= self.resources.len()
                    || q <= 0
                    || !seen.insert(r)
                    || (self.resources[r].kind == ResourceKind::Capacity
                        && q > self.resources[r].initial)
                {
                    return Err(format!("invalid resource need in {}", p.id));
                }
            }
            let mut seen = HashSet::new();
            for &a in &p.after {
                if a >= n || a == i || !seen.insert(a) {
                    return Err("invalid predecessor".into());
                }
                expected[a].push(i);
            }
        }
        if self.successors != expected {
            return Err("invalid compiled successor index".into());
        }
        let mut degree: Vec<usize> = self.processes.iter().map(|p| p.after.len()).collect();
        let mut ready: Vec<usize> = degree
            .iter()
            .enumerate()
            .filter_map(|(i, &n)| if n == 0 { Some(i) } else { None })
            .collect();
        let mut visited = 0;
        while let Some(i) = ready.pop() {
            visited += 1;
            for &j in &expected[i] {
                degree[j] -= 1;
                if degree[j] == 0 {
                    ready.push(j);
                }
            }
        }
        if visited != n {
            return Err("cyclic predecessor graph".into());
        }
        for e in &self.events {
            if e.time < 0
                || e.repeat_every.is_some_and(|x| x <= 0)
                || e.trigger.is_some_and(|p| p >= n)
            {
                return Err("invalid explicit event".into());
            }
            match e.op {
                Operation::SetState
                    if e.target >= self.assets.len() || !(0..=1).contains(&e.value) =>
                {
                    return Err("invalid state event".into())
                }
                Operation::AddStock
                    if e.target >= self.resources.len()
                        || self.resources[e.target].kind != ResourceKind::Stock
                        || e.value <= 0
                        || e.trigger.is_some() =>
                {
                    return Err("invalid stock event".into())
                }
                _ => (),
            }
        }
        Ok(())
    }
}

#[derive(Default, Serialize)]
struct Diagnostics {
    events: u64,
    attempts: u64,
    waiter_inspections: u64,
    stale_completions: u64,
    max_queue: usize,
}
type TraceEntry = (i64, &'static str, String, String, i64);
#[derive(Serialize)]
struct RunResult {
    profile: &'static str,
    fingerprint: String,
    seed: u32,
    assets: Vec<i64>,
    owners: Vec<i64>,
    resources: Vec<i64>,
    status: Vec<i64>,
    selected: Vec<i64>,
    started: Vec<i64>,
    finished: Vec<i64>,
    sampled: Vec<i64>,
    generation: Vec<u64>,
    completed: Vec<u64>,
    trace: Vec<TraceEntry>,
    diagnostics: Diagnostics,
}
type Event = (i64, u64, u8, usize, u64);
struct State<'a> {
    plan: &'a Plan,
    result: RunResult,
    heap: BinaryHeap<Reverse<Event>>,
    sequence: u64,
    asset_waiters: Vec<BTreeSet<usize>>,
    resource_waiters: Vec<BTreeSet<usize>>,
    pending: Vec<bool>,
    trace_enabled: bool,
}
impl<'a> State<'a> {
    fn new(plan: &'a Plan, seed: u32, trace_enabled: bool) -> Self {
        let n = plan.processes.len();
        let mut state = Self {
            plan,
            result: RunResult {
                profile: PROFILE,
                fingerprint: plan.fingerprint.clone(),
                seed,
                assets: plan.assets.iter().map(|x| x.initial_state).collect(),
                owners: vec![-1; plan.assets.len()],
                resources: plan.resources.iter().map(|x| x.initial).collect(),
                status: vec![0; n],
                selected: vec![-1; n],
                started: vec![-1; n],
                finished: vec![-1; n],
                sampled: vec![-1; n],
                generation: vec![0; n],
                completed: vec![0; n],
                trace: Vec::new(),
                diagnostics: Diagnostics::default(),
            },
            heap: BinaryHeap::new(),
            sequence: 0,
            asset_waiters: vec![BTreeSet::new(); plan.assets.len()],
            resource_waiters: vec![BTreeSet::new(); plan.resources.len()],
            pending: vec![false; n],
            trace_enabled,
        };
        for (i, p) in plan.processes.iter().enumerate() {
            if let Some(t) = p.release {
                state.push(t, ACTIVATE, i, 0);
            }
        }
        for (i, e) in plan.events.iter().enumerate() {
            state.push(e.time, EXPLICIT, i, 0);
        }
        state
    }
    fn push(&mut self, time: i64, kind: u8, target: usize, generation: u64) {
        if time > self.plan.horizon {
            return;
        }
        self.heap
            .push(Reverse((time, self.sequence, kind, target, generation)));
        self.sequence += 1;
        self.result.diagnostics.max_queue = self.result.diagnostics.max_queue.max(self.heap.len());
    }
    fn push_after(&mut self, now: i64, delay: i64, kind: u8, target: usize, generation: u64) {
        // All times and delays are nonnegative. Overflow is necessarily past
        // the inclusive i64 horizon, so the event cannot be observed.
        if let Some(time) = now.checked_add(delay) {
            self.push(time, kind, target, generation);
        }
    }
    fn trace(&mut self, t: i64, kind: &'static str, id: &str, asset: &str, value: i64) {
        if self.trace_enabled {
            self.result
                .trace
                .push((t, kind, id.into(), asset.into(), value));
        }
    }
    fn trace_process(&mut self, t: i64, kind: &'static str, p: usize, value: i64) {
        let selected = self.result.selected[p];
        let asset = if selected < 0 {
            ""
        } else {
            self.plan.assets[selected as usize].id.as_str()
        };
        self.trace(t, kind, &self.plan.processes[p].id, asset, value);
    }
    fn register(&mut self, p: usize) {
        for &a in &self.plan.processes[p].candidates {
            self.asset_waiters[a].insert(p);
        }
        for &(r, _) in &self.plan.processes[p].needs {
            self.resource_waiters[r].insert(p);
        }
    }
    fn unregister(&mut self, p: usize) {
        for &a in &self.plan.processes[p].candidates {
            self.asset_waiters[a].remove(&p);
        }
        for &(r, _) in &self.plan.processes[p].needs {
            self.resource_waiters[r].remove(&p);
        }
    }
    fn notify(&mut self, t: i64, waiters: BTreeSet<usize>) {
        for p in waiters {
            self.result.diagnostics.waiter_inspections += 1;
            if self.result.status[p] == 1 && !self.pending[p] {
                self.pending[p] = true;
                self.push(t, RETRY, p, 0);
            }
        }
    }
    fn activate(&mut self, t: i64, p: usize) -> Result<(), String> {
        match self.result.status[p] {
            0 => (),
            3 | 4 => {
                self.result.generation[p] += 1;
                self.result.selected[p] = -1;
                self.result.started[p] = -1;
                self.result.finished[p] = -1;
                self.result.sampled[p] = -1;
            }
            _ => return Ok(()),
        }
        self.result.status[p] = 1;
        self.attempt(t, p)
    }
    fn attempt(&mut self, t: i64, p: usize) -> Result<(), String> {
        if self.result.status[p] != 1 {
            return Ok(());
        }
        self.result.diagnostics.attempts += 1;
        let process = &self.plan.processes[p];
        let predecessors_ready = process.after.iter().all(|&i| self.result.completed[i] > 0);
        let asset = process
            .candidates
            .iter()
            .find(|&&a| {
                self.result.assets[a] == process.required_state && self.result.owners[a] == -1
            })
            .copied();
        let resources_ready = process
            .needs
            .iter()
            .all(|&(r, q)| self.result.resources[r] >= q);
        if !predecessors_ready
            || (!process.candidates.is_empty() && asset.is_none())
            || !resources_ready
        {
            self.register(p);
            return Ok(());
        }
        self.unregister(p);
        for &(r, q) in &process.needs {
            self.result.resources[r] -= q;
        }
        if let Some(a) = asset {
            self.result.owners[a] = p as i64;
            self.result.selected[p] = a as i64;
        }
        let [lo, hi] = process.duration;
        let duration = if lo == hi {
            lo
        } else {
            sample(
                self.result.seed,
                &process.id,
                self.result.generation[p],
                lo,
                hi,
            )
        };
        self.result.sampled[p] = duration;
        self.result.started[p] = t;
        self.result.status[p] = 2;
        if lo != hi {
            self.trace_process(t, "random", p, duration);
        }
        self.trace_process(t, "start", p, duration);
        self.push_after(t, duration, COMPLETE, p, self.result.generation[p]);
        Ok(())
    }
    fn release(&mut self, p: usize) -> Result<BTreeSet<usize>, String> {
        let mut waiters = BTreeSet::new();
        for &(r, q) in &self.plan.processes[p].needs {
            if self.plan.resources[r].kind == ResourceKind::Capacity {
                self.result.resources[r] = self.result.resources[r]
                    .checked_add(q)
                    .ok_or("resource overflow")?;
                if self.result.resources[r] > self.plan.resources[r].initial {
                    return Err("capacity conservation violation".into());
                }
                waiters.extend(&self.resource_waiters[r]);
            }
        }
        let a = self.result.selected[p];
        if a >= 0 {
            let a = a as usize;
            if self.result.owners[a] != p as i64 {
                return Err("asset ownership violation".into());
            }
            self.result.owners[a] = -1;
            waiters.extend(&self.asset_waiters[a]);
        }
        Ok(waiters)
    }
    fn complete(&mut self, t: i64, p: usize, generation: u64) -> Result<(), String> {
        if self.result.status[p] != 2 || self.result.generation[p] != generation {
            self.result.diagnostics.stale_completions += 1;
            return Ok(());
        }
        let mut waiters = self.release(p)?;
        self.result.status[p] = 3;
        self.result.finished[p] = t;
        self.result.completed[p] += 1;
        if self.result.selected[p] >= 0 {
            self.result.assets[self.result.selected[p] as usize] =
                self.plan.processes[p].finish_state;
        }
        self.trace_process(t, "complete", p, 0);
        if let Some(delay) = self.plan.processes[p].repeat_delay {
            self.push_after(t, delay, ACTIVATE, p, 0);
        }
        waiters.extend(&self.plan.successors[p]);
        self.notify(t, waiters);
        Ok(())
    }
    fn explicit(&mut self, t: i64, index: usize) -> Result<(), String> {
        let event = &self.plan.events[index];
        if let Some(delay) = event.repeat_every {
            self.push_after(t, delay, EXPLICIT, index, 0);
        }
        match event.op {
            Operation::AddStock => {
                let r = event.target;
                self.result.resources[r] = self.result.resources[r]
                    .checked_add(event.value)
                    .ok_or("stock overflow")?;
                self.trace(t, "stock", &event.id, "", self.result.resources[r]);
                self.notify(t, self.resource_waiters[r].clone());
            }
            Operation::SetState => {
                let a = event.target;
                if self.result.assets[a] == event.value {
                    return Ok(());
                }
                let mut waiters = self.asset_waiters[a].clone();
                if self.result.owners[a] >= 0 {
                    let p = self.result.owners[a] as usize;
                    if !self.plan.processes[p].interruptible {
                        return Err(format!(
                            "state change interrupts noninterruptible {}",
                            self.plan.processes[p].id
                        ));
                    }
                    waiters.extend(self.release(p)?);
                    self.result.status[p] = 4;
                    self.trace_process(t, "abort", p, 0);
                }
                self.result.assets[a] = event.value;
                self.trace(t, "state", &event.id, &self.plan.assets[a].id, event.value);
                if let Some(p) = event.trigger {
                    self.push(t, ACTIVATE, p, 0);
                }
                self.notify(t, waiters);
            }
        }
        Ok(())
    }
    fn execute(&mut self) -> Result<(), String> {
        while let Some(Reverse((t, _, kind, target, generation))) = self.heap.pop() {
            if t > self.plan.horizon {
                break;
            }
            self.result.diagnostics.events += 1;
            if self.result.diagnostics.events > EVENT_BUDGET {
                return Err("runtime event budget exceeded".into());
            }
            match kind {
                ACTIVATE => self.activate(t, target)?,
                RETRY => {
                    self.pending[target] = false;
                    self.attempt(t, target)?;
                }
                COMPLETE => self.complete(t, target, generation)?,
                EXPLICIT => self.explicit(t, target)?,
                _ => unreachable!(),
            }
        }
        Ok(())
    }
}
fn sample(seed: u32, id: &str, generation: u64, lo: i64, hi: i64) -> i64 {
    let identity = format!("{seed}|{id}|{generation}");
    let mut x: u32 = 2_166_136_261;
    for byte in identity.bytes() {
        x = (x ^ u32::from(byte)).wrapping_mul(16_777_619);
    }
    x ^= x.wrapping_shl(13);
    x ^= x >> 17;
    x ^= x.wrapping_shl(5);
    lo + (u64::from(x) % (hi as u64 - lo as u64 + 1)) as i64
}

fn run(request: Request) -> Result<Value, String> {
    if request.seeds.is_empty() || request.repeats == 0 || request.threads == 0 {
        return Err("seeds, repeats and threads must be nonzero".into());
    }
    let sample_count = request
        .seeds
        .len()
        .checked_mul(request.repeats)
        .ok_or("sample count overflow")?;
    let n = request.seeds.len();
    let next = AtomicUsize::new(0);
    let plan = Arc::new(request.plan);
    let threads = request.threads.min(sample_count);
    let batch_start = Instant::now();
    let outputs = std::thread::scope(|scope| {
        let mut workers = Vec::new();
        for _ in 0..threads {
            let plan = Arc::clone(&plan);
            let seeds = &request.seeds;
            let next = &next;
            let trace = request.trace;
            workers.push(scope.spawn(move || -> Result<_,String> {
                let mut output = Vec::new(); let mut timings = Vec::new(); let mut init_ns:u128 = 0; let mut execute_ns:u128 = 0;
                loop {
                    let sample_index = next.fetch_add(1,Ordering::Relaxed);
                    if sample_index >= sample_count { break; }
                    let seed = seeds[sample_index % n];
                    let start = Instant::now(); let mut state = State::new(&plan,seed,trace); let initialization_ns = start.elapsed().as_nanos(); init_ns += initialization_ns;
                    let start = Instant::now(); state.execute()?;
                    let result = serde_json::to_value(state.result).map_err(|e|e.to_string())?;
                    let execution_ns = start.elapsed().as_nanos(); execute_ns += execution_ns;
                    timings.push(json!({"sample_index":sample_index,"seed":seed,"initialization_ns":initialization_ns,"execution_ns":execution_ns}));
                    if sample_index >= sample_count - n { output.push((sample_index % n,result)); }
                }
                Ok((output,timings,init_ns,execute_ns))
            }));
        }
        workers
            .into_iter()
            .map(|worker| {
                worker
                    .join()
                    .map_err(|_| "sample worker panicked".to_string())?
            })
            .collect::<Result<Vec<_>, String>>()
    })?;
    let batch_wall_ns = batch_start.elapsed().as_nanos();
    let mut results = Vec::new();
    let mut per_run_timings = Vec::new();
    let mut init_ns: u128 = 0;
    let mut execute_ns: u128 = 0;
    for (mut output, mut timings, init, execution) in outputs {
        results.append(&mut output);
        per_run_timings.append(&mut timings);
        init_ns += init;
        execute_ns += execution;
    }
    results.sort_unstable_by_key(|(index, _)| *index);
    let results: Vec<_> = results.into_iter().map(|(_, result)| result).collect();
    per_run_timings.sort_unstable_by_key(|t| t["sample_index"].as_u64().unwrap());
    Ok(
        json!({"results":results,"timings":per_run_timings,"per_run_timings":per_run_timings,"batch_wall_ns":batch_wall_ns,"timing":{"init_ns":init_ns,"execute_ns":execute_ns,"batch_wall_ns":batch_wall_ns,"samples":sample_count,"threads":threads}}),
    )
}
fn main() {
    let result = (|| -> Result<Value, String> {
        let mut input = String::new();
        io::stdin()
            .read_to_string(&mut input)
            .map_err(|e| e.to_string())?;
        let parse_start = Instant::now();
        let mut raw: Value =
            serde_json::from_str(&input).map_err(|e| format!("request validation: {e}"))?;
        let plan_raw = raw
            .get_mut("plan")
            .and_then(Value::as_object_mut)
            .ok_or("plan must be an object")?;
        let fingerprint = plan_raw
            .remove("fingerprint")
            .ok_or("missing plan fingerprint")?;
        let canonical = serde_json::to_vec(&plan_raw).map_err(|e| e.to_string())?;
        let expected = format!("{:x}", Sha256::digest(&canonical));
        if fingerprint.as_str() != Some(expected.as_str()) {
            return Err("plan fingerprint mismatch".into());
        }
        plan_raw.insert("fingerprint".into(), fingerprint);
        let request: Request =
            serde_json::from_value(raw).map_err(|e| format!("request validation: {e}"))?;
        request.plan.validate()?;
        let parse_validate_ns = parse_start.elapsed().as_nanos();
        let mut result = run(request)?;
        result["timing"]["parse_validate_ns"] = json!(parse_validate_ns);
        result["parse_validate_ns"] = json!(parse_validate_ns);
        Ok(result)
    })();
    match result {
        Ok(output) => println!("{}", output),
        Err(error) => {
            eprintln!("{}", json!({"error":error}));
            std::process::exit(2);
        }
    }
}
