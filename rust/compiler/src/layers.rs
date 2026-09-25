//! Persisted Business/Core contracts and symbol layout shared with Python.
use std::collections::{BTreeMap, HashSet};
use anyhow::{Result, bail, Context};
use serde::{Serialize, Deserialize};
use serde_json::{Value, Map, json};
use sha2::{Digest, Sha256};
use sim_engine_runtime::plan::{ExecutionPlan, PLAN_VERSION, EVENT_TIME_V2_PHASES};

pub const BUSINESS_VERSION: &str = "aircraft-business-ir/v1";
pub const CORE_VERSION: &str = "simulation-core-ir/v1";
const TABLES: &[(&str, &str)] = &[("aircraft","tail_number"),("missions","mission_id"),("activities","activity_id"),("resource_nodes","node_id"),("components","component_id"),("preventive_cycles","source_path"),("supply_routes","route_id")];
fn refs(table: &str) -> Vec<(&'static str, &'static str, bool)> {
    match table {
        "activities" => vec![("resource_node_index","resource_nodes",false),("equipment_component_index","components",true)],
        "components" => vec![("parent_index","components",true),("aircraft_indexes","aircraft",false),("repair_activity_index","activities",true)],
        "preventive_cycles" => vec![("aircraft_index","aircraft",false),("activity_index","activities",false)],
        "supply_routes" => vec![("source_node_index","resource_nodes",false),("destination_node_index","resource_nodes",false)],
        _ => vec![],
    }
}
pub fn digest(value: &Value) -> Result<String> {
    Ok(format!("{:x}", Sha256::digest(ExecutionPlan::python_canonical(value)?.as_bytes())))
}
fn operations() -> Value { serde_json::from_str(include_str!("../../../src/sim_engine_compiler/ir/compatibility_operations.json")).unwrap() }
fn keys(value: &Value, expected: &[&str], path: &str) -> Result<()> {
    let object = value.as_object().with_context(|| format!("{path}: expected object"))?;
    if object.len()!=expected.len() || expected.iter().any(|key| !object.contains_key(*key)) { bail!("{path}: unknown or missing field"); }
    Ok(())
}
fn sequence<'a>(v: &'a Value, path: &str) -> Result<&'a Vec<Value>> { v.as_array().with_context(|| format!("{path}: expected ordered list")) }
fn symbol(v: &Value) -> Result<&str> { v.as_str().filter(|s| !s.is_empty()).context("missing stable symbol") }

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Artifact { pub version: String, pub fingerprint: String, pub payload: Value }
impl Artifact {
    fn seal(version: &str, payload: Value) -> Result<Self> {
        let fingerprint=digest(&json!({"version":version,"payload":payload}))?;
        Ok(Self{version:version.into(),fingerprint,payload})
    }
    pub fn check(&self, version: &str) -> Result<()> {
        if self.version != version || self.fingerprint != digest(&json!({"version":self.version,"payload":self.payload}))? { bail!("IR version or checksum mismatch"); }
        Ok(())
    }
}

pub fn import_business(inputs: &Value, profile: &str) -> Result<Artifact> {
    if inputs["schema_version"] != "aircraft-support-v1-input-v1" { bail!("unsupported canonical input schema"); }
    if !matches!(profile,"legacy-minute-v1"|"event-time-v2") { bail!("unsupported time profile"); }
    let input=inputs.as_object().context("canonical input must be object")?;
    crate::aircraft_support::validation::validate_canonical_work(input)?;
    let mut sections=Map::new(); let mut root=Map::new();
    for (key,value) in input {
        let Some(props)=value.as_object() else {root.insert(key.clone(),value.clone());continue;};
        let mut properties=props.clone(); let mut collections=Map::new();
        let fields: &[&str]=match key.as_str() {
            "aircraft"=> &["assets"], "equipment_tree"=> &["components"],
            "support_activities"=> &["activities"],"support_network"=> &["nodes"],
            "mission_profile"=> &["basic_missions","composite_tasks","mission_calendar","mission_phases","airports"],_=> &[],
        };
        for field in fields {
            if !properties.get(*field).is_some_and(Value::is_array) {continue;}
            let rows=properties.remove(*field).unwrap(); let mut entities=vec![];
            for (index,definition) in rows.as_array().unwrap().iter().enumerate() {
                if !definition.is_object() {bail!("{key}.{field}[{index}]: canonical entity must be an object");}
                let path=format!("{key}.{field}[{index}]");
                let identity=["id","tail_number","missionId"].iter().find_map(|f| definition[*f].as_str().filter(|s| !s.is_empty())).unwrap_or(&path);
                entities.push(json!({"business_id":identity,"source_path":path,"definition":definition}));
            }
            collections.insert((*field).into(),Value::Array(entities));
        }
        sections.insert(key.clone(),json!({"properties":properties,"collections":collections}));
    }
    sections.insert("$root".into(),json!({"properties":root,"collections":{}}));
    let artifact=Artifact::seal(BUSINESS_VERSION,json!({"semantic_profile":profile,"source":{"schema_version":"aircraft-support-v1-input-v1","canonical_sha256":digest(inputs)?},"sections":sections}))?;
    canonical_view(&artifact)?; Ok(artifact)
}

pub fn canonical_view(business: &Artifact) -> Result<Value> {
    business.check(BUSINESS_VERSION)?;
    let payload=&business.payload;
    keys(payload,&["semantic_profile","source","sections"],"business")?;
    keys(&payload["source"],&["schema_version","canonical_sha256"],"business.source")?;
    if payload["source"]["schema_version"]!="aircraft-support-v1-input-v1" || !matches!(payload["semantic_profile"].as_str(),Some("legacy-minute-v1"|"event-time-v2")) {bail!("unsupported Business IR contract");}
    let mut values=Map::new();
    for (section,content) in payload["sections"].as_object().context("business.sections must be object")? {
        keys(content,&["properties","collections"],"business.section")?;
        let mut props=content["properties"].as_object().context("section properties must be object")?.clone();
        for (collection,entities) in content["collections"].as_object().context("collections must be object")? {
            if props.contains_key(collection) {bail!("duplicate Business collection");}
            let mut seen=HashSet::new(); let mut rows=vec![];
            for entity in sequence(entities,"business.entities")? {
                keys(entity,&["business_id","source_path","definition"],"business.entity")?;
                if !seen.insert(symbol(&entity["business_id"])?) || !entity["definition"].is_object() || !entity["source_path"].is_string() {bail!("invalid Business entity identity/definition/source");}
                rows.push(entity["definition"].clone());
            }
            props.insert(collection.clone(),Value::Array(rows));
        }
        values.insert(section.clone(),Value::Object(props));
    }
    let root=values.remove("$root").unwrap_or(json!({}));
    for (key,value) in root.as_object().context("invalid root section")? {
        if values.insert(key.clone(),value.clone()).is_some() {bail!("duplicate canonical section");}
    }
    Ok(Value::Object(values))
}

fn dependencies(activity:&Value,step:&Value,tables:&Value)->Result<Value>{
    let node=&activity["references"]["resource_node_index"];
    let mut products=std::collections::BTreeSet::new();
    for pair in sequence(&step["attributes"]["spares"],"step.spares")? {products.insert(symbol(&pair[0])?.to_owned());}
    if activity["attributes"]["kind"]=="repair" {
        for c in sequence(&tables["components"],"components")? {
            if c["references"]["repair_activity_index"]==activity["id"] && c["attributes"]["product_type"]=="LRU" {
                if let Some(p)=c["attributes"]["product_id"].as_str().filter(|p| !p.is_empty()) {products.insert(p.to_owned());}
            }
        }
    }
    let mut routes=vec![];
    for route in sequence(&tables["supply_routes"],"routes")? {
        let product=route["attributes"]["product_id"].as_str().context("route product must be string")?;
        if route["references"]["destination_node_index"]==*node && (product.is_empty()||products.contains(product)) {routes.push(route["id"].clone());}
    }
    Ok(json!({"capacity_node":node,"inventory_products":products,"supply_routes":routes,"dynamic_state":["job_reservations","active_shipment","job_step","job_status"],"wakeups":["resource_change","job_change","canonical_dispatch_phase"]}))
}

pub fn core_from_records(business:&Artifact, mut records:Value)->Result<Artifact>{
    let mut symbols=BTreeMap::new();
    for (name,id) in TABLES {symbols.insert(*name,sequence(&records[*name],name)?.iter().map(|r|r[*id].clone()).collect::<Vec<_>>());}
    let mut tables=Map::new();
    for (name,id) in TABLES {
        let rows=records.as_object_mut().unwrap().remove(*name).context("missing lowering table")?;
        let mut output=vec![];
        for row in rows.as_array().unwrap() {
            let mut attrs=row.as_object().unwrap().clone();attrs.remove("index");
            let steps=attrs.remove("steps").unwrap_or(json!([]));let mut references=Map::new();
            for (field,target,optional) in refs(name) {
                let value=attrs.remove(field).context("missing lowering reference")?;
                let resolved=if field=="aircraft_indexes" {Value::Array(value.as_array().unwrap().iter().map(|v|symbols[target][v.as_u64().unwrap() as usize].clone()).collect())}
                else if optional && value.as_i64().unwrap()<0 {Value::Null}
                else {symbols[target][value.as_u64().unwrap() as usize].clone()};
                references.insert(field.into(),resolved);
            }
            let codes=steps.as_array().unwrap().iter().map(|s|s["code"].clone()).collect::<Vec<_>>();
            let mut core_steps=vec![];
            for step in steps.as_array().unwrap() {
                let mut fields=step.as_object().unwrap().clone();fields.remove("index");
                let predecessors=fields.remove("predecessors").unwrap().as_array().unwrap().iter().map(|v|codes[v.as_u64().unwrap() as usize].clone()).collect::<Vec<_>>();
                core_steps.push(json!({"id":step["code"],"attributes":fields,"predecessors":predecessors,"dependencies":{}}));
            }
            output.push(json!({"id":row[*id],"attributes":attrs,"references":references,"steps":core_steps}));
        }
        tables.insert((*name).into(),Value::Array(output));
    }
    let mut tables=Value::Object(tables);let mut activities=tables["activities"].clone();
    for activity in activities.as_array_mut().unwrap() {
        let mut steps=activity["steps"].clone();
        for step in steps.as_array_mut().unwrap() {step["dependencies"]=dependencies(activity,step,&tables)?;}
        activity["steps"]=steps;
    }
    tables["activities"]=activities;
    let core=Artifact::seal(CORE_VERSION,json!({"source":{"business_fingerprint":business.fingerprint,"canonical_sha256":digest(&canonical_view(business)?)?,"origin_canonical_sha256":business.payload["source"]["canonical_sha256"]},"contract":records,"operations":operations(),"tables":tables}))?;
    validate_core(&core)?;Ok(core)
}

pub fn validate_core(core:&Artifact)->Result<()> {
    core.check(CORE_VERSION)?;
    keys(&core.payload,&["source","contract","operations","tables"],"core")?;
    keys(&core.payload["source"],&["business_fingerprint","canonical_sha256","origin_canonical_sha256"],"core.source")?;
    for value in core.payload["source"].as_object().unwrap().values() {
        if !value.as_str().is_some_and(|s|s.len()==64&&s.bytes().all(|c| c.is_ascii_digit()||(b'a'..=b'f').contains(&c))) {bail!("core.source: expected SHA-256");}
    }
    let contract=&core.payload["contract"];
    keys(contract,&["domain","semantic_profile","work_policy","rng_profile","duration_minutes","natural_completion_enabled","phases","unsupported_features"],"core.contract")?;
    if contract["domain"]!="aircraft-support" || !matches!(contract["semantic_profile"].as_str(),Some("legacy-minute-v1"|"event-time-v2")) || contract["phases"]!=json!(EVENT_TIME_V2_PHASES) || contract["work_policy"]!="stable-topological-serial" || contract["rng_profile"]!="legacy-sequential-v1" || contract["unsupported_features"]!=json!([]) {bail!("unsupported Core compatibility contract");}
    if !contract["duration_minutes"].as_i64().is_some_and(|v|v>0) || !contract["natural_completion_enabled"].is_boolean() {bail!("core.contract: invalid duration or termination type");}
    if core.payload["operations"]!=operations() {bail!("core.operations: unknown operation or incomplete dependency/backend contract");}
    let tables=&core.payload["tables"];
    keys(tables,&TABLES.iter().map(|v|v.0).collect::<Vec<_>>(),"core.tables")?;
    let mut ids=BTreeMap::new();
    for (name,id) in TABLES {
        let mut set=HashSet::new();
        for row in sequence(&tables[*name],name)? {
            keys(row,&["id","attributes","references","steps"],name)?;
            validate_attributes(&row["attributes"],name)?;
            let identity=symbol(&row["id"])?;
            if !set.insert(identity) || row["attributes"][*id]!=row["id"] {bail!("{name}: duplicate or inconsistent symbol");}
            keys(&row["references"],&refs(name).iter().map(|r|r.0).collect::<Vec<_>>(),"core.references")?;
            if *name!="activities" && row["steps"]!=json!([]) {bail!("unexpected work steps");}
        }
        ids.insert(*name,set);
    }
    for (name,_) in TABLES {
        for row in sequence(&tables[*name],name)? {
            for (field,target,optional) in refs(name) {
                let value=&row["references"][field];
                let values=if field=="aircraft_indexes" {sequence(value,field)?.iter().collect::<Vec<_>>()}else{vec![value]};
                for v in values {if !(optional&&v.is_null()) && !v.as_str().is_some_and(|s|ids[target].contains(s)) {bail!("core.{name}.{field}: unresolved symbol {v}");}}
            }
            if *name=="activities" {
                let mut seen=HashSet::new();
                for step in sequence(&row["steps"],"steps")? {
                    keys(step,&["id","attributes","predecessors","dependencies"],"core.step")?;
                    validate_attributes(&step["attributes"],"steps")?;
                    if step["attributes"]["code"]!=step["id"] || !seen.insert(symbol(&step["id"])?) {bail!("invalid step identity");}
                    for pred in sequence(&step["predecessors"],"predecessors")? {if pred==&step["id"]||!seen.contains(symbol(pred)?) {bail!("unknown/cyclic step predecessor");}}
                    if step["dependencies"]!=dependencies(row,step,tables)? {bail!("core.steps.dependencies: incomplete resource/wakeup contract");}
                }
            }
        }
    }
    Ok(())
}

pub fn compile_core(core:&Artifact)->Result<ExecutionPlan> {
    validate_core(core)?;
    let tables=&core.payload["tables"];
    let mut ids=BTreeMap::new();
    for (name,_) in TABLES {ids.insert(*name,sequence(&tables[*name],name)?.iter().enumerate().map(|(i,r)|(r["id"].as_str().unwrap(),i)).collect::<BTreeMap<_,_>>());}
    let mut value=core.payload["contract"].as_object().unwrap().clone();
    value.insert("plan_version".into(),json!(PLAN_VERSION));value.insert("source_inputs_sha256".into(),core.payload["source"]["canonical_sha256"].clone());
    for (name,_) in TABLES {
        let mut rows=vec![];
        for (i,row) in sequence(&tables[*name],name)?.iter().enumerate() {
            let mut attrs=row["attributes"].as_object().context("attributes must be object")?.clone();attrs.insert("index".into(),json!(i));
            for (field,target,optional) in refs(name) {
                let reference=&row["references"][field];
                let resolved=if field=="aircraft_indexes" {json!(reference.as_array().unwrap().iter().map(|v|ids[target][v.as_str().unwrap()]).collect::<Vec<_>>())}
                    else if optional&&reference.is_null(){json!(-1)}else{json!(ids[target][reference.as_str().unwrap()])};
                attrs.insert(field.into(),resolved);
            }
            if *name=="activities" {
                let steps=sequence(&row["steps"],"steps")?;
                let map=steps.iter().enumerate().map(|(i,s)|(s["id"].as_str().unwrap(),i)).collect::<BTreeMap<_,_>>();
                let mut out=vec![];
                for (i,s) in steps.iter().enumerate() {
                    let mut a=s["attributes"].as_object().context("step attributes must be object")?.clone();a.insert("index".into(),json!(i));
                    a.insert("predecessors".into(),json!(s["predecessors"].as_array().unwrap().iter().map(|p|map[p.as_str().unwrap()]).collect::<Vec<_>>()));out.push(Value::Object(a));
                }
                attrs.insert("steps".into(),Value::Array(out));
            }
            rows.push(Value::Object(attrs));
        }
        value.insert((*name).into(),Value::Array(rows));
    }
    let raw=Value::Object(value);
    let plan:ExecutionPlan=serde_json::from_value(raw.clone()).context("invalid Core backend layout")?;
    if serde_json::to_value(&plan)?!=raw {bail!("Core layout contains unknown or missing attributes");}
    plan.validate()?;Ok(plan)
}

fn validate_attributes(value:&Value,table:&str)->Result<()> {
    static SCHEMAS: std::sync::LazyLock<Value> = std::sync::LazyLock::new(|| serde_json::from_str(include_str!("../../../src/sim_engine_compiler/ir/attribute_types.json")).unwrap());
    let schemas = &*SCHEMAS;
    let expected=schemas[table].as_object().context("unknown attribute schema")?;
    keys(value,&expected.keys().map(String::as_str).collect::<Vec<_>>(),table)?;
    fn check(item:&Value,kind:&Value,path:&str)->Result<()> {
        if let Some(kinds)=kind.as_array() {
            let items=sequence(item,path)?;
            if kinds[0]=="tuple" {
                if items.len()!=kinds.len()-1 {bail!("{path}: wrong tuple size");}
                for (v,k) in items.iter().zip(&kinds[1..]) {check(v,k,path)?;}
            } else {for v in items {check(v,&kinds[1],path)?;}}
        } else {
            let valid=match kind.as_str() {
                Some("int")=>item.as_i64().is_some_and(|v|v>=0),
                Some("float")=>item.as_f64().is_some_and(|v|v.is_finite()&&v>=0.0),
                Some("str")=>item.is_string(),Some("bool")=>item.is_boolean(),_=>false,
            };
            if !valid {bail!("{path}: invalid typed Core attribute");}
        }
        Ok(())
    }
    for (field,kind) in expected {check(&value[field],kind,&format!("core.{table}.{field}"))?;}
    Ok(())
}
