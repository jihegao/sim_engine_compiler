cmake_minimum_required(VERSION 3.24)
project(SimResourceDispatchMLIR LANGUAGES C CXX)

find_package(LLVM 23.1.1 EXACT REQUIRED CONFIG)
find_package(MLIR 23.1.1 EXACT REQUIRED CONFIG)

message(STATUS
  "MLIR plugin toolchain ABI: RTTI=${LLVM_ENABLE_RTTI}, EH=${LLVM_ENABLE_EH}")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(SYSTEM ${LLVM_INCLUDE_DIRS} ${MLIR_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})

function(match_llvm_plugin_abi target)
  if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    if(NOT LLVM_ENABLE_RTTI)
      target_compile_options(${target} PRIVATE -fno-rtti)
    endif()
    if(NOT LLVM_ENABLE_EH)
      target_compile_options(${target} PRIVATE -fno-exceptions)
    endif()
  endif()
endfunction()

function(link_mlir_plugin_runtime target)
  if(TARGET MLIR AND TARGET LLVM)
    get_target_property(MLIR_SHARED_LIBRARY MLIR IMPORTED_LOCATION_RELEASE)
    get_target_property(LLVM_SHARED_LIBRARY LLVM IMPORTED_LOCATION_RELEASE)
    if(EXISTS "${MLIR_SHARED_LIBRARY}" AND EXISTS "${LLVM_SHARED_LIBRARY}")
      target_link_libraries(${target} PRIVATE
        "$<TARGET_LINKER_FILE:MLIR>"
        "$<TARGET_LINKER_FILE:LLVM>"
      )
      return()
    endif()
  endif()

  if(UNIX AND NOT APPLE AND TARGET MLIRIR AND TARGET MLIRPass AND TARGET LLVMSupport)
    if("${target}" STREQUAL "SimDialect")
      target_link_libraries(${target} PRIVATE MLIRIR)
    else()
      target_link_libraries(${target} PRIVATE MLIRPass)
    endif()
    message(STATUS "Linking ${target} against Linux MLIR static component targets")
  else()
    message(STATUS
      "No usable monolithic MLIR/LLVM shared libraries or static component targets were found")
    message(FATAL_ERROR "Cannot link MLIR plugin runtime for ${target}")
  endif()
endfunction()

add_library(SimDialect MODULE src/SimDialect.cpp)
match_llvm_plugin_abi(SimDialect)
link_mlir_plugin_runtime(SimDialect)
target_compile_definitions(SimDialect PRIVATE SIM_MLIR_VERSION="${LLVM_PACKAGE_VERSION}")
set_target_properties(SimDialect PROPERTIES PREFIX "")

add_library(SimResourceDispatchPass MODULE src/ResourceDispatchPass.cpp)
match_llvm_plugin_abi(SimResourceDispatchPass)
link_mlir_plugin_runtime(SimResourceDispatchPass)
target_compile_definitions(SimResourceDispatchPass PRIVATE SIM_MLIR_VERSION="${LLVM_PACKAGE_VERSION}")
set_target_properties(SimResourceDispatchPass PROPERTIES PREFIX "")

message(STATUS "Building sim dialect and resource-index pass against LLVM/MLIR ${LLVM_PACKAGE_VERSION}")
