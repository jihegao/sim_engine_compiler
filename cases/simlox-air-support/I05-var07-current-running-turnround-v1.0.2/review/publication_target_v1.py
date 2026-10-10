"""Explicit publication identity gate; no simulation or mutable-tip defaults."""
import json
import re


class BindingError(ValueError):
    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code = code


def require(ok, code, detail):
    if not ok:
        raise BindingError(code, detail)


def sha(value, length=40):
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def load_json(path):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_BINDING_KEY", key)
            result[key] = value
        return result
    with open(path, encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=unique)


def parse_refs(text):
    result = {}
    for line in text.splitlines():
        fields = line.split()
        require(len(fields) == 2 and sha(fields[0]), "INVALID_REF_RESPONSE", line)
        commit, ref = fields
        require(ref not in result, "DUPLICATE_REMOTE_REF", ref)
        result[ref] = commit
    return result


def validate_binding(binding):
    require(binding.get("schema") == "simlox-publication-binding/v1", "BINDING_SCHEMA", "unsupported schema")
    require(binding.get("repository") == "jihegao/sim_engine_compiler", "REPOSITORY", "wrong repository")
    require(binding.get("remote") == "origin" and binding.get("ref") == "refs/heads/simlox/main", "TARGET_REF", "wrong remote/ref")
    require(binding.get("product_ref") == "refs/heads/main" and sha(binding.get("product_commit")), "PRODUCT_REF", "invalid product binding")
    publication = binding.get("publication", {})
    require(type(publication.get("pr")) is int and publication["pr"] > 0, "PUBLICATION_PR", "invalid PR")
    require(sha(publication.get("commit")) and sha(publication.get("tree")), "PUBLICATION_IDENTITY", "invalid commit/tree")
    parents = publication.get("parents")
    require(isinstance(parents, list) and len(parents) == 2 and all(sha(x) for x in parents), "PUBLICATION_PARENTS", "expected merge parents")
    for name in ("package", "case_version", "run_id"):
        require(isinstance(binding.get(name), str) and binding[name], "SOURCE_IDENTITY", name)
    for name in ("input", "manifest", "inherited_reader", "publication_index"):
        source = binding.get(name, {})
        path = source.get("path", "")
        require(isinstance(path, str) and path and not path.startswith(("/", "\\")) and ":" not in path and ".." not in path.replace("\\", "/").split("/"), "SOURCE_PATH", name)
        require(sha(source.get("sha256"), 64), "SOURCE_SHA", name)


def validate_target(target, binding, binding_sha256):
    require(target.get("schema") == "simlox-expected-publication-target/v1", "TARGET_SCHEMA", "unsupported schema")
    require(target.get("publication_binding_sha256") == binding_sha256, "TARGET_SOURCE_BINDING", "wrong original publication binding")
    for name in ("repository", "remote", "ref", "package", "case_version", "run_id"):
        require(target.get(name) == binding[name], "TARGET_PROVENANCE", name)
    require(sha(target.get("commit")) and sha(target.get("tree")), "TARGET_IDENTITY", "invalid commit/tree")
    require(isinstance(target.get("provenance"), str) and target["provenance"].strip(), "TARGET_PROVENANCE", "missing explicit evidence locator")


def validate_product_target(target, binding, binding_sha256):
    require(target.get("schema") == "simlox-expected-product-reference/v1", "PRODUCT_SCHEMA", "unsupported schema")
    require(target.get("publication_binding_sha256") == binding_sha256, "PRODUCT_SOURCE_BINDING", "wrong original publication binding")
    for name in ("repository", "remote"):
        require(target.get(name) == binding[name], "PRODUCT_PROVENANCE", name)
    require(target.get("ref") == binding["product_ref"], "PRODUCT_PROVENANCE", "wrong product ref")
    require(sha(target.get("commit")) and sha(target.get("tree")), "PRODUCT_IDENTITY", "invalid commit/tree")
    for name in ("provenance", "independent_receipt"):
        require(isinstance(target.get(name), str) and target[name].strip(), "PRODUCT_PROVENANCE", name)


def verify(binding, refs_text, describe_commit, is_ancestor, mode, target=None, binding_sha256=None, product_target=None):
    """Callbacks inspect Git objects/ancestry; tests inject observations, never native runs."""
    validate_binding(binding)
    require(mode in ("current-target", "historical-publication"), "VALIDATION_MODE", mode)
    require(not (mode == "historical-publication" and target is not None), "AMBIGUOUS_TARGET", "historical mode has no current-target binding")
    refs = parse_refs(refs_text)
    ref = binding["ref"]
    require(ref in refs, "MISSING_TARGET_REF", ref)
    if product_target is not None:
        validate_product_target(product_target, binding, binding_sha256)
    expected_product = product_target["commit"] if product_target else binding["product_commit"]
    require(refs.get(binding["product_ref"]) == expected_product, "PRODUCT_REF_MISMATCH", binding["product_ref"])
    product = describe_commit(expected_product)
    if product_target is not None:
        require(product["tree"] == product_target["tree"], "PRODUCT_TREE_MISMATCH", expected_product)
        require(is_ancestor(binding["product_commit"], expected_product), "PRODUCT_BASE_NOT_REACHABLE", expected_product)
    publication = binding["publication"]
    original = describe_commit(publication["commit"])
    require(original["tree"] == publication["tree"], "PUBLICATION_TREE_MISMATCH", publication["commit"])
    require(original["parents"] == publication["parents"], "PUBLICATION_PARENT_MISMATCH", publication["commit"])
    if mode == "current-target":
        if target is not None:
            validate_target(target, binding, binding_sha256)
        expected = target or publication
        require(refs[ref] == expected["commit"], "TARGET_COMMIT_MISMATCH", f"expected {expected['commit']}, observed {refs[ref]}")
        actual = describe_commit(refs[ref])
        require(actual["tree"] == expected["tree"], "TARGET_TREE_MISMATCH", refs[ref])
        require(is_ancestor(publication["commit"], refs[ref]), "PUBLICATION_NOT_REACHABLE", refs[ref])
        decision = "CURRENT_TARGET_IDENTITY_VERIFIED"
    else:
        require(is_ancestor(publication["commit"], refs[ref]), "PUBLICATION_NOT_REACHABLE", refs[ref])
        actual = describe_commit(refs[ref])
        decision = "HISTORICAL_PUBLICATION_IDENTITY_VERIFIED"
    return {"decision": decision, "mode": mode, "repository": binding["repository"], "remote": binding["remote"], "ref": ref,
            "publication_commit": publication["commit"], "publication_tree": publication["tree"],
            "observed_target_commit": refs[ref], "observed_target_tree": actual["tree"],
            "expected_current_commit": (target or publication)["commit"] if mode == "current-target" else None,
            "expected_current_tree": (target or publication)["tree"] if mode == "current-target" else None,
            "publication_pr": publication["pr"], "package": binding["package"], "case_version": binding["case_version"], "run_id": binding["run_id"],
            "original_product_commit": binding["product_commit"], "expected_product_commit": expected_product,
            "observed_product_tree": product["tree"], "explicit_product_binding": product_target is not None}


def require_stable_refs(before, subordinate, after):
    require(parse_refs(before) == parse_refs(subordinate) == parse_refs(after), "REMOTE_REF_CHANGED", "before/raw/after observations disagree")


def published_index(binding, read_blob):
    """Immutable original index only; caller has already verified the actual commit/tree."""
    import hashlib
    source = binding["publication_index"]
    data = read_blob(binding["publication"]["commit"], source["path"])
    require(hashlib.sha256(data).hexdigest() == source["sha256"], "PUBLISHED_INDEX_MISMATCH", source["path"])
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_INDEX_KEY", key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def derive_snapshot_reader(original_text):
    """Three reviewed replacements; all native/raw/oracle assertions retained."""
    text = original_text.replace("\r\n", "\n")
    old = "oldindex=parse(archived);liveindex=parse(W/'cases/simlox-air-support/publication-index-v1.json');entry=parse(C/'publication-entry.json')"
    new = """from publication_target_v1 import published_index
publication_binding=json.loads((Path(__file__).parent/'publication-binding-v1.json').read_bytes())
def read_index_blob(commit,path):
 return subprocess.run(['git','--no-replace-objects','show',commit+':'+path],cwd=W,capture_output=True,check=True).stdout
oldindex=parse(archived);liveindex=published_index(publication_binding,read_index_blob);entry=parse(C/'publication-entry.json')"""
    decision = "'decision':'GO_BOUNDED_POSTPUBLICATION_READONLY_REPLAY'"
    product_assertion = ";assert 'a1a44c72f64d754b711abe4095f1111f8a5ba896\\trefs/heads/main' in refs"
    require(text.count(old) == 1 and text.count(decision) == 1 and text.count(product_assertion) == 1, "RAW_DERIVATION_SOURCE_CHANGED", "expected exactly three replacement sites")
    return text.replace(old, new).replace(decision, "'decision':'GO_BOUNDED_PUBLISHED_SNAPSHOT_RAW_REPLAY'").replace(product_assertion, "")
