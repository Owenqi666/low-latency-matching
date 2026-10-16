cmake_minimum_required(VERSION 3.24)
project(llmatch VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(LLMATCH_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)

add_library(llmatch_options INTERFACE)
target_compile_options(llmatch_options INTERFACE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
if(LLMATCH_SANITIZERS)
  target_compile_options(llmatch_options INTERFACE -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer)
  target_link_options(llmatch_options INTERFACE -fsanitize=address,undefined -fno-sanitize-recover=all)
endif()

add_library(llmatch_contract INTERFACE)
target_include_directories(llmatch_contract INTERFACE ${PROJECT_SOURCE_DIR}/include)
add_library(llmatch_core src/order_book.cpp src/matching_engine.cpp)
target_link_libraries(llmatch_core PUBLIC llmatch_contract PRIVATE llmatch_options)
add_library(llmatch_reference reference/reference_engine.cpp)
target_include_directories(llmatch_reference PUBLIC ${PROJECT_SOURCE_DIR}/reference)
target_link_libraries(llmatch_reference PUBLIC llmatch_contract PRIVATE llmatch_options)
add_library(llmatch_trace tools/trace_io.cpp)
target_include_directories(llmatch_trace PUBLIC ${PROJECT_SOURCE_DIR}/tools)
target_link_libraries(llmatch_trace PUBLIC llmatch_contract PRIVATE llmatch_options)
add_library(llmatch_validation tools/differential.cpp tools/random_commands.cpp)
target_include_directories(llmatch_validation PUBLIC ${PROJECT_SOURCE_DIR}/tools)
target_link_libraries(llmatch_validation PUBLIC llmatch_core llmatch_reference llmatch_trace PRIVATE llmatch_options)

add_executable(replay apps/replay_main.cpp)
target_link_libraries(replay PRIVATE llmatch_validation llmatch_options)
add_executable(generate_workload tools/workload_generator.cpp)
target_link_libraries(generate_workload PRIVATE llmatch_validation llmatch_options)
add_executable(shrink_failure tools/shrink_failure.cpp)
target_link_libraries(shrink_failure PRIVATE llmatch_validation llmatch_options)
add_executable(bench_core bench/core_bench.cpp)
target_link_libraries(bench_core PRIVATE llmatch_core llmatch_reference llmatch_trace llmatch_options)
add_executable(clock_probe bench/clock_probe.cpp)
target_link_libraries(clock_probe PRIVATE llmatch_options)

include(CTest)
if(BUILD_TESTING)
  find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
  include(cmake/Dependencies.cmake)
  add_executable(llmatch_tests tests/contract_test.cpp tests/engine_test.cpp tests/order_book_test.cpp tests/reference_test.cpp tests/trace_io_test.cpp tests/differential_test.cpp)
  target_link_libraries(llmatch_tests PRIVATE llmatch_validation llmatch_options GTest::gtest_main)
  include(GoogleTest)
  gtest_discover_tests(llmatch_tests DISCOVERY_TIMEOUT 30)
  foreach(fixture basic capacity reverse rejections)
    if(fixture STREQUAL "capacity")
      set(fixture_config capacity)
    else()
      set(fixture_config basic)
    endif()
    add_test(NAME replay_${fixture} COMMAND replay --engine compare
      --config ${PROJECT_SOURCE_DIR}/data/fixtures/${fixture_config}.config
      --input ${PROJECT_SOURCE_DIR}/data/fixtures/${fixture}.trace
      --output-dir ${PROJECT_BINARY_DIR}/replays/${fixture})
  endforeach()
  add_test(NAME regression_maker_price COMMAND replay --engine compare
    --config ${PROJECT_SOURCE_DIR}/data/regressions/maker-price.config
    --input ${PROJECT_SOURCE_DIR}/data/regressions/maker-price.trace
    --output-dir ${PROJECT_BINARY_DIR}/replays/maker-price)
  add_test(NAME cli_contract COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/cli_test.py
    $<TARGET_FILE:replay> $<TARGET_FILE:shrink_failure> $<TARGET_FILE:generate_workload>
    ${PROJECT_SOURCE_DIR}/data/fixtures)
  if(CMAKE_BUILD_TYPE STREQUAL "Release" AND NOT LLMATCH_SANITIZERS)
    add_test(NAME benchmark_pipeline COMMAND ${Python3_EXECUTABLE}
      ${PROJECT_SOURCE_DIR}/tests/benchmark_pipeline_test.py
      $<TARGET_FILE:bench_core> $<TARGET_FILE:clock_probe>)
  endif()
endif()
