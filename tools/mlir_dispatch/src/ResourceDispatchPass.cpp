#include "SimDialect.h"

#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/Operation.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Tools/Plugins/PassPlugin.h"
#include "llvm/ADT/SmallSet.h"
#include "llvm/ADT/STLExtras.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/WithColor.h"
#include "llvm/Support/raw_ostream.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

using namespace mlir;

namespace {

constexpr llvm::StringLiteral kIndexSchema = "resource-dispatch-index/v1";
constexpr llvm::StringLiteral kPassName = "sim-build-resource-dependency-index";
constexpr llvm::StringLiteral kCanonicalPhaseOrder[] = {
    "transport_arrivals",
    "mission_returns",
    "job_progress_and_completions",
    "failures",
    "operations_postflight_before_preparation",
    "preventive_generation",
    "preflight_generation",
    "resource_dispatch",
    "mission_dispatch",
    "operations_postflight_after_dispatch",
    "mission_success",
    "daily_readiness",
    "operational_availability",
    "downtime",
    "stop",
};

struct StepRef {
  int64_t activityIndex;
  int64_t stepIndex;
  std::string activityId;
  std::string stepCode;
  std::string sourcePath;
  std::string productFilter;

  auto key() const {
    return std::tie(activityIndex, stepIndex, productFilter, activityId, stepCode,
                    sourcePath);
  }
  bool operator<(const StepRef &other) const { return key() < other.key(); }
};

struct ResourceKey {
  std::string kind;
  int64_t nodeIndex;
  std::string productId;

  auto key() const { return std::tie(kind, nodeIndex, productId); }
  bool operator<(const ResourceKey &other) const { return key() < other.key(); }
};

struct ActivityInfo {
  int64_t nodeIndex = -1;
  int64_t stepCount = 0;
  std::string activityId;
  bool hasStaticSpares = false;
  bool permitsReplacement = false;
  bool onlyReplacement = false;
  double replacementRatio = 0.0;
};

struct RouteInfo {
  int64_t sourceNode = -1;
  int64_t destinationNode = -1;
  std::string productId;
};

static FailureOr<int64_t> integerAttr(Operation *op, llvm::StringRef name) {
  auto attr = op->getAttrOfType<IntegerAttr>(name);
  if (!attr) {
    op->emitError() << "requires integer attribute '" << name << "'";
    return failure();
  }
  return attr.getInt();
}

static FailureOr<std::string> stringAttr(Operation *op, llvm::StringRef name) {
  auto attr = op->getAttrOfType<StringAttr>(name);
  if (!attr) {
    op->emitError() << "requires string attribute '" << name << "'";
    return failure();
  }
  return attr.getValue().str();
}

static bool containsString(ArrayAttr values, llvm::StringRef expected) {
  if (!values)
    return false;
  return llvm::any_of(values, [&](Attribute value) {
    auto item = dyn_cast<StringAttr>(value);
    return item && item.getValue() == expected;
  });
}

static bool containsOnlyStrings(ArrayAttr values,
                                std::initializer_list<llvm::StringRef> allowed) {
  if (!values)
    return false;
  return llvm::all_of(values, [&](Attribute value) {
    auto item = dyn_cast<StringAttr>(value);
    return item && llvm::is_contained(allowed, item.getValue());
  });
}

static bool hasCanonicalPhaseOrder(ArrayAttr phases) {
  if (!phases || phases.size() != sizeof(kCanonicalPhaseOrder) /
                                      sizeof(kCanonicalPhaseOrder[0]))
    return false;
  for (size_t index = 0; index < phases.size(); ++index) {
    auto phase = dyn_cast<StringAttr>(phases[index]);
    if (!phase || phase.getValue() != kCanonicalPhaseOrder[index])
      return false;
  }
  return true;
}

static bool hasOnlyAttributes(
    Operation *op, std::initializer_list<llvm::StringRef> allowed) {
  return llvm::all_of(op->getAttrs(), [&](NamedAttribute attribute) {
    return llvm::is_contained(allowed, attribute.getName().getValue());
  });
}

static std::string lowercase(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
    return static_cast<char>(std::tolower(c));
  });
  return value;
}

class ResourceDispatchIndexPass final
    : public PassWrapper<ResourceDispatchIndexPass,
                         OperationPass<ModuleOp>> {
public:
  ResourceDispatchIndexPass() = default;
  ResourceDispatchIndexPass(const ResourceDispatchIndexPass &other)
      : PassWrapper(other) {}

  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(ResourceDispatchIndexPass)

  StringRef getArgument() const final { return kPassName; }
  StringRef getDescription() const final {
    return "Build a complete static resource-to-work-step dependency index";
  }

  Option<std::string> jsonOutput{
      *this, "json-output",
      llvm::cl::desc("Write the verified dependency index as JSON"),
      llvm::cl::init("")};
  Option<bool> buildIndex{
      *this, "build-index",
      llvm::cl::desc("Build and export the resource dependency index"),
      llvm::cl::init(true)};

  void runOnOperation() override {
    ModuleOp module = getOperation();
    auto moduleVersion = module->getAttrOfType<StringAttr>("sim.schema");
    auto semanticProfile = module->getAttrOfType<StringAttr>("sim.semantic_profile");
    auto phases = module->getAttrOfType<ArrayAttr>("sim.phases");
    auto workPolicy = module->getAttrOfType<StringAttr>("sim.work_policy");
    auto rngProfile = module->getAttrOfType<StringAttr>("sim.rng_profile");
    auto baseFingerprint =
        module->getAttrOfType<StringAttr>("sim.base_plan_fingerprint");
    if (!hasOnlyAttributes(module,
                           {"sim.schema", "sim.semantic_profile", "sim.phases", "sim.work_policy",
                            "sim.rng_profile", "sim.base_plan_fingerprint"}) ||
        !moduleVersion || moduleVersion.getValue() != "aircraft-support-core/v1" ||
        !semanticProfile ||
        (semanticProfile.getValue() != "legacy-minute-v1" &&
         semanticProfile.getValue() != "event-time-v2") ||
        !hasCanonicalPhaseOrder(phases) ||
        !workPolicy || workPolicy.getValue() != "stable-topological-serial" ||
        !rngProfile || rngProfile.getValue() != "legacy-sequential-v1" ||
        !baseFingerprint || baseFingerprint.getValue().size() != 64) {
      module.emitError("unsupported or incomplete sim module contract");
      signalPassFailure();
      return;
    }

    std::map<int64_t, ActivityInfo> activities;
    std::map<int64_t, std::vector<StepRef>> stepsByActivity;
    std::map<int64_t, std::vector<StepRef>> stepsByIndex;
    std::vector<std::pair<int64_t, std::string>> components;
    std::vector<RouteInfo> routes;
    bool passFailed = false;

    module.walk([&](Operation *op) {
      if (passFailed)
        return WalkResult::interrupt();
      if (op == module.getOperation() ||
          op->getName().getStringRef() == "builtin.module_terminator")
        return WalkResult::advance();
      auto name = op->getName().getStringRef();
      if (op->getBlock() != module.getBody() || op->getNumOperands() != 0 ||
          op->getNumResults() != 0 || op->getNumRegions() != 0) {
        op->emitError("sim pilot operations must be top-level attribute-only records");
        passFailed = true;
        return WalkResult::interrupt();
      }
      if (!name.starts_with("sim.")) {
        op->emitError("non-sim operation is outside the closed pilot Core IR schema");
        passFailed = true;
        return WalkResult::interrupt();
      }
      if (name == "sim.activity") {
        if (!hasOnlyAttributes(
                op, {"activity_index", "resource_node_index", "step_count", "activity_id",
                     "has_static_spares", "replacement_ratio", "maintenance_methods"})) {
          op->emitError("sim.activity contains an unsupported attribute");
          passFailed = true;
          return WalkResult::interrupt();
        }
        auto index = integerAttr(op, "activity_index");
        auto node = integerAttr(op, "resource_node_index");
        auto count = integerAttr(op, "step_count");
        auto id = stringAttr(op, "activity_id");
        if (failed(index) || failed(node) || failed(count) || failed(id)) {
          passFailed = true;
          return WalkResult::interrupt();
        }
        ActivityInfo info;
        info.nodeIndex = *node;
        info.stepCount = *count;
        info.activityId = *id;
        auto hasStaticSpares = op->getAttrOfType<BoolAttr>("has_static_spares");
        auto methods = op->getAttrOfType<ArrayAttr>("maintenance_methods");
        auto ratio = op->getAttrOfType<FloatAttr>("replacement_ratio");
        if (!hasStaticSpares || !methods || !ratio) {
          op->emitError("activity requires static-spare, method, and replacement-ratio attributes");
          passFailed = true;
          return WalkResult::interrupt();
        }
        info.hasStaticSpares = hasStaticSpares.getValue();
        info.replacementRatio = ratio ? ratio.getValueAsDouble() : 0.0;
        info.permitsReplacement = containsString(methods, "replacement");
        info.onlyReplacement = methods.size() == 1 && info.permitsReplacement;
        if (info.onlyReplacement)
          info.replacementRatio = 1.0;
        if (*index < 0 || *node < 0 || *count < 0 ||
            !activities.emplace(*index, std::move(info)).second) {
          op->emitError("invalid or duplicate sim.activity identity");
          passFailed = true;
          return WalkResult::interrupt();
        }
      } else if (name == "sim.work_step") {
        if (!hasOnlyAttributes(
                op, {"activity_index", "step_index", "resource_node_index", "personnel",
                     "equipment", "activity_id", "step_code", "source_path", "spares",
                     "reads", "effects"})) {
          op->emitError("sim.work_step contains an unsupported attribute");
          passFailed = true;
          return WalkResult::interrupt();
        }
        auto activity = integerAttr(op, "activity_index");
        auto step = integerAttr(op, "step_index");
        auto node = integerAttr(op, "resource_node_index");
        auto personnel = integerAttr(op, "personnel");
        auto equipment = integerAttr(op, "equipment");
        auto activityId = stringAttr(op, "activity_id");
        auto stepCode = stringAttr(op, "step_code");
        auto sourcePath = stringAttr(op, "source_path");
        auto reads = op->getAttrOfType<ArrayAttr>("reads");
        auto effects = op->getAttrOfType<ArrayAttr>("effects");
        if (failed(activity) || failed(step) || failed(node) || failed(personnel) ||
            failed(equipment) || failed(activityId) || failed(stepCode) ||
            failed(sourcePath) || !reads || !effects ||
            reads.size() != 6 || effects.size() != 4 ||
            !containsString(reads, "personnel_capacity") ||
            !containsString(reads, "equipment_capacity") ||
            !containsString(reads, "local_inventory") ||
            !containsString(reads, "job_reservations") ||
            !containsString(reads, "route_source_inventory") ||
            !containsString(reads, "active_shipment") ||
            !containsOnlyStrings(reads, {"personnel_capacity", "equipment_capacity",
                                         "local_inventory", "job_reservations",
                                         "route_source_inventory", "active_shipment"}) ||
            !containsString(effects, "reserve_capacity") ||
            !containsString(effects, "consume_inventory") ||
            !containsString(effects, "request_remote_spares") ||
            !containsString(effects, "emit_dispatch_trace") ||
            !containsOnlyStrings(effects, {"reserve_capacity", "consume_inventory",
                                           "request_remote_spares", "emit_dispatch_trace"})) {
          op->emitError("unsupported or incomplete work-step read/effect contract");
          passFailed = true;
          return WalkResult::interrupt();
        }
        if (*activity < 0 || *step < 0 || *node < 0 || *personnel < 0 ||
            *equipment < 0) {
          op->emitError("work-step indexes and resource quantities must be non-negative");
          passFailed = true;
          return WalkResult::interrupt();
        }
        StepRef ref{*activity, *step, *activityId, *stepCode, *sourcePath, ""};
        stepsByActivity[*activity].push_back(ref);
        stepsByIndex[*activity].push_back(ref);
        (void)node;
        (void)personnel;
        (void)equipment;
      } else if (name == "sim.component") {
        if (!hasOnlyAttributes(op, {"repair_activity_index", "product_type", "product_id"})) {
          op->emitError("sim.component contains an unsupported attribute");
          passFailed = true;
          return WalkResult::interrupt();
        }
        auto repairActivity = integerAttr(op, "repair_activity_index");
        auto productType = stringAttr(op, "product_type");
        auto productId = stringAttr(op, "product_id");
        if (failed(repairActivity) || failed(productType) || failed(productId)) {
          passFailed = true;
          return WalkResult::interrupt();
        }
        if (*repairActivity >= 0 && lowercase(*productType) == "lru" &&
            !productId->empty())
          components.emplace_back(*repairActivity, *productId);
      } else if (name == "sim.supply_route") {
        if (!hasOnlyAttributes(
                op, {"source_node_index", "destination_node_index", "product_id"})) {
          op->emitError("sim.supply_route contains an unsupported attribute");
          passFailed = true;
          return WalkResult::interrupt();
        }
        auto source = integerAttr(op, "source_node_index");
        auto destination = integerAttr(op, "destination_node_index");
        auto product = stringAttr(op, "product_id");
        if (failed(source) || failed(destination) || failed(product)) {
          passFailed = true;
          return WalkResult::interrupt();
        }
        if (*source < 0 || *destination < 0) {
          op->emitError("supply-route node indexes must be non-negative");
          passFailed = true;
          return WalkResult::interrupt();
        }
        routes.push_back({*source, *destination, *product});
      } else {
        op->emitError() << "unknown operation in closed sim dialect: " << name;
        passFailed = true;
        return WalkResult::interrupt();
      }
      return WalkResult::advance();
    });
    if (passFailed) {
      signalPassFailure();
      return;
    }

    for (auto &[activityIndex, info] : activities) {
      auto found = stepsByActivity.find(activityIndex);
      const size_t actualCount = found == stepsByActivity.end() ? 0 : found->second.size();
      if (info.stepCount != static_cast<int64_t>(actualCount)) {
        module.emitError() << "activity " << activityIndex
                           << " step_count does not match its sim.work_step rows";
        signalPassFailure();
        return;
      }
    }
    for (const auto &[activityIndex, refs] : stepsByActivity) {
      if (!activities.contains(activityIndex)) {
        module.emitError() << "work steps reference unknown activity " << activityIndex;
        signalPassFailure();
        return;
      }
      std::set<int64_t> seen;
      for (const auto &ref : refs) {
        if (!seen.insert(ref.stepIndex).second) {
          module.emitError() << "duplicate step index in activity " << activityIndex;
          signalPassFailure();
          return;
        }
      }
    }

    if (!buildIndex)
      return;

    std::map<ResourceKey, std::set<StepRef>> dependencies;
    auto addInventory = [&](int64_t destination, const std::string &product,
                            const StepRef &ref) {
      dependencies[{"inventory", destination, product}].insert(ref);
      for (const auto &route : routes) {
        if (route.destinationNode == destination &&
            (route.productId.empty() || route.productId == product))
          dependencies[{"inventory", route.sourceNode, product}].insert(ref);
      }
    };

    for (Operation &operation : module.getBody()->getOperations()) {
      Operation *op = &operation;
      if (op->getName().getStringRef() != "sim.work_step")
        continue;
      auto activity = op->getAttrOfType<IntegerAttr>("activity_index").getInt();
      auto step = op->getAttrOfType<IntegerAttr>("step_index").getInt();
      auto node = op->getAttrOfType<IntegerAttr>("resource_node_index").getInt();
      auto personnel = op->getAttrOfType<IntegerAttr>("personnel").getInt();
      auto equipment = op->getAttrOfType<IntegerAttr>("equipment").getInt();
      StepRef ref{activity, step,
                  op->getAttrOfType<StringAttr>("activity_id").getValue().str(),
                  op->getAttrOfType<StringAttr>("step_code").getValue().str(),
                  op->getAttrOfType<StringAttr>("source_path").getValue().str(), ""};
      auto activityInfo = activities.find(activity);
      if (activityInfo == activities.end() || activityInfo->second.nodeIndex != node ||
          activityInfo->second.activityId != ref.activityId ||
          step >= activityInfo->second.stepCount) {
        op->emitError("work-step activity, node, or stable identity mismatch");
        signalPassFailure();
        return;
      }
      if (personnel > 0)
        dependencies[{"personnel_capacity", node, ""}].insert(ref);
      if (equipment > 0)
        dependencies[{"equipment_capacity", node, ""}].insert(ref);
      auto spares = op->getAttrOfType<ArrayAttr>("spares");
      for (Attribute spareAttr : spares) {
        auto spare = dyn_cast<DictionaryAttr>(spareAttr);
        if (!spare) {
          op->emitError("spares must be an array of {product_id, quantity} dictionaries");
          signalPassFailure();
          return;
        }
        auto product = spare.getAs<StringAttr>("product_id");
        auto quantity = spare.getAs<IntegerAttr>("quantity");
        if (!product || product.getValue().empty() || !quantity || quantity.getInt() <= 0) {
          op->emitError("spare product_id and positive quantity are required");
          signalPassFailure();
          return;
        }
        addInventory(node, product.getValue().str(), ref);
      }
    }

    for (const auto &[activityIndex, productId] : components) {
      auto activity = activities.find(activityIndex);
      auto refs = stepsByActivity.find(activityIndex);
      if (activity == activities.end() || refs == stepsByActivity.end() ||
          refs->second.empty() || activity->second.hasStaticSpares ||
          !activity->second.permitsReplacement || activity->second.replacementRatio <= 0.0)
        continue;
      auto finalStep = *std::max_element(
          refs->second.begin(), refs->second.end(),
          [](const StepRef &left, const StepRef &right) {
            return left.stepIndex < right.stepIndex;
          });
      finalStep.productFilter = productId;
      addInventory(activity->second.nodeIndex, productId, finalStep);
    }

    OpBuilder builder(module.getContext());
    SmallVector<Attribute> serializedDependencies;
    llvm::json::Array jsonDependencies;
    for (const auto &[key, refs] : dependencies) {
      llvm::json::Object jsonKey;
      jsonKey["kind"] = key.kind;
      jsonKey["node_index"] = key.nodeIndex;
      if (!key.productId.empty())
        jsonKey["product_id"] = key.productId;
      llvm::json::Array jsonCandidates;
      SmallVector<Attribute> candidateAttrs;
      for (const StepRef &ref : refs) {
        llvm::json::Object candidate;
        candidate["activity_index"] = ref.activityIndex;
        candidate["step_index"] = ref.stepIndex;
        candidate["activity_id"] = ref.activityId;
        candidate["step_code"] = ref.stepCode;
        candidate["source_path"] = ref.sourcePath;
        if (!ref.productFilter.empty())
          candidate["product_filter"] = ref.productFilter;
        jsonCandidates.push_back(std::move(candidate));

        NamedAttrList attrs;
        attrs.set("activity_index", builder.getI64IntegerAttr(ref.activityIndex));
        attrs.set("step_index", builder.getI64IntegerAttr(ref.stepIndex));
        attrs.set("activity_id", builder.getStringAttr(ref.activityId));
        attrs.set("step_code", builder.getStringAttr(ref.stepCode));
        attrs.set("source_path", builder.getStringAttr(ref.sourcePath));
        if (!ref.productFilter.empty())
          attrs.set("product_filter", builder.getStringAttr(ref.productFilter));
        candidateAttrs.push_back(DictionaryAttr::get(module.getContext(), attrs));
      }
      jsonDependencies.push_back(llvm::json::Object{
          {"key", std::move(jsonKey)}, {"candidates", std::move(jsonCandidates)}});

      NamedAttrList entryAttrs;
      entryAttrs.set("kind", builder.getStringAttr(key.kind));
      entryAttrs.set("node_index", builder.getI64IntegerAttr(key.nodeIndex));
      if (!key.productId.empty())
        entryAttrs.set("product_id", builder.getStringAttr(key.productId));
      entryAttrs.set("candidates", builder.getArrayAttr(candidateAttrs));
      serializedDependencies.push_back(
          DictionaryAttr::get(module.getContext(), entryAttrs));
    }

    module->setAttr("sim.resource_dependencies",
                    builder.getArrayAttr(serializedDependencies));
    llvm::json::Object result;
    result["schema_version"] = kIndexSchema.str();
    result["mlir_version"] = SIM_MLIR_VERSION;
    result["pass_name"] = kPassName.str();
    result["base_plan_fingerprint"] = baseFingerprint.getValue().str();
    result["dependencies"] = std::move(jsonDependencies);
    size_t candidateRuleCount = 0;
    for (const auto &[key, refs] : dependencies) {
      (void)key;
      candidateRuleCount += refs.size();
    }
    result["candidate_rule_count"] = static_cast<int64_t>(candidateRuleCount);
    if (!jsonOutput.empty()) {
      std::error_code error;
      llvm::raw_fd_ostream output(jsonOutput, error, llvm::sys::fs::OF_Text);
      if (error) {
        module.emitError() << "cannot open resource-index JSON output: "
                           << error.message();
        signalPassFailure();
        return;
      }
      output << llvm::formatv("{0:2}\n", llvm::json::Value(std::move(result)));
    }
  }
};

} // namespace

extern "C" ::mlir::PassPluginLibraryInfo LLVM_ATTRIBUTE_WEAK
mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "sim-resource-dispatch-pass", SIM_MLIR_VERSION,
          []() { PassRegistration<ResourceDispatchIndexPass>(); }};
}
