cmake_minimum_required(VERSION 3.20)
project(elpis_fms_file_assets_r0 LANGUAGES C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
find_package(Threads REQUIRED)
# Additive bridge over unchanged ABI-v2 FMS. No checkpoint bridge changes.
add_library(elpis_fms_file_assets_r0 SHARED
  bridge.c ../src/memory/fms/fms_core.c
  ../src/memory/fms/fms_pal_posix.c ../src/hash/sha256.c)
target_include_directories(elpis_fms_file_assets_r0 PRIVATE ../include)
target_compile_options(elpis_fms_file_assets_r0 PRIVATE -Wall -Wextra -Werror -Wpedantic)
target_link_libraries(elpis_fms_file_assets_r0 PRIVATE Threads::Threads)
