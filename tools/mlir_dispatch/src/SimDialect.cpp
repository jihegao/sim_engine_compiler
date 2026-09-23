#include "SimDialect.h"

#include "mlir/Tools/Plugins/DialectPlugin.h"

using sim_engine::mlir_dispatch::SimDialect;

extern "C" ::mlir::DialectPluginLibraryInfo LLVM_ATTRIBUTE_WEAK
mlirGetDialectPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "sim-resource-dispatch", SIM_MLIR_VERSION,
          [](mlir::DialectRegistry *registry) {
            registry->insert<SimDialect>();
          }};
}
