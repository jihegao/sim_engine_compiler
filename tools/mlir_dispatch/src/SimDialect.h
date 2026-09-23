#ifndef SIM_ENGINE_COMPILER_SIM_DIALECT_H
#define SIM_ENGINE_COMPILER_SIM_DIALECT_H

#include "mlir/IR/Dialect.h"

namespace sim_engine::mlir_dispatch {

class SimDialect final : public mlir::Dialect {
public:
  explicit SimDialect(mlir::MLIRContext *context)
      : Dialect(getDialectNamespace(), context, mlir::TypeID::get<SimDialect>()) {
    // The pilot uses generic operation syntax. The pass below enforces the
    // closed operation and attribute schema before it emits any index.
    allowUnknownOperations();
  }

  static llvm::StringRef getDialectNamespace() { return "sim"; }
};

} // namespace sim_engine::mlir_dispatch

#endif
