cmake_minimum_required(VERSION 3.24)
project(SimResourceDispatchMLIR LANGUAGES C CXX)

find_package(LLVM 23.1.1 EXACT REQUIRED CONFIG)
find_package(MLIR 23.1.1 EXACT REQUIRED CONFIG)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(SYSTEM ${LLVM_INCLUDE_DIRS} ${MLIR_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})

add_library(SimDialect MODULE src/SimDialect.cpp)
target_link_libraries(SimDialect PRIVATE MLIR LLVM)
target_compile_definitions(SimDialect PRIVATE SIM_MLIR_VERSION="${LLVM_PACKAGE_VERSION}")
set_target_properties(SimDialect PROPERTIES PREFIX "")

add_library(SimResourceDispatchPass MODULE src/ResourceDispatchPass.cpp)
target_link_libraries(SimResourceDispatchPass PRIVATE MLIR LLVM)
target_compile_definitions(SimResourceDispatchPass PRIVATE SIM_MLIR_VERSION="${LLVM_PACKAGE_VERSION}")
set_target_properties(SimResourceDispatchPass PROPERTIES PREFIX "")

message(STATUS "Building sim dialect and resource-index pass against LLVM/MLIR ${LLVM_PACKAGE_VERSION}")
