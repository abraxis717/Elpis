cmake_minimum_required(VERSION 3.20)
project(elpis LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(
  ELPIS_WARNINGS_AS_ERRORS
  "Treat warnings in Elpis native targets as errors"
  ON
)

option(ELPIS_ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(ELPIS_ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)
option(ELPIS_ENABLE_TSAN "Enable ThreadSanitizer" OFF)

if(ELPIS_ENABLE_TSAN AND (ELPIS_ENABLE_ASAN OR ELPIS_ENABLE_UBSAN))
  message(
    FATAL_ERROR
    "ThreadSanitizer cannot be combined with ASan/UBSan."
  )
endif()

if(ELPIS_ENABLE_ASAN OR ELPIS_ENABLE_UBSAN OR ELPIS_ENABLE_TSAN)
  if(NOT (
      CMAKE_C_COMPILER_ID MATCHES "GNU|Clang"
      AND
      CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang"
  ))
    message(
      FATAL_ERROR
      "Sanitizers require GCC- or Clang-compatible C/C++ compilers."
    )
  endif()

  if(ELPIS_ENABLE_TSAN)
    set(_elpis_sanitizer thread)
  elseif(ELPIS_ENABLE_ASAN AND ELPIS_ENABLE_UBSAN)
    set(_elpis_sanitizer address,undefined)
  elseif(ELPIS_ENABLE_ASAN)
    set(_elpis_sanitizer address)
  else()
    set(_elpis_sanitizer undefined)
  endif()

  add_compile_options(
    -g
    -fno-omit-frame-pointer
    -fno-optimize-sibling-calls
    -fsanitize=${_elpis_sanitizer}
  )

  add_link_options(-fsanitize=${_elpis_sanitizer})

  if(ELPIS_ENABLE_UBSAN)
    add_compile_options(-fno-sanitize-recover=undefined)
  endif()
endif()

enable_testing()
find_package(Threads REQUIRED)

include(native/elpis.cmake)

add_subdirectory(native/substrate)
add_subdirectory(native/structure)
add_subdirectory(native/ECS)
add_subdirectory(native/continuity)
