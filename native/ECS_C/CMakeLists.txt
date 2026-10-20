# ECS_C: published independent model-free typed memory; no continuity authority yet.
# Publication R0: bounded, model-free ECS memory mechanics, standalone only.

# No composite, runtime, scientific or durable-authority admission follows from this target.
elpis_add_library(ECS_C elpis_ecs_memory SHARED memory/src/ecs_memory.c)
target_include_directories(elpis_ecs_memory PUBLIC memory/include)
target_link_libraries(elpis_ecs_memory PRIVATE elpis_hash)
elpis_add_test(ECS_C test_ecs_memory SOURCES memory/tests/test_ecs_memory.c LIBS elpis_ecs_memory elpis_hash TIMEOUT 120)
elpis_add_test(ECS_C test_ecs_memory_capability SOURCES memory/tests/test_ecs_memory_capability.c
  LIBS elpis_ecs_memory elpis_hash TIMEOUT 60)
elpis_add_test(ECS_C test_ecs_memory_snapshot SOURCES memory/tests/test_ecs_memory_snapshot.c
  LIBS elpis_ecs_memory elpis_hash TIMEOUT 600)
elpis_add_test(ECS_C test_ecs_memory_concurrency SOURCES memory/tests/test_ecs_memory_concurrency.c
  LIBS elpis_ecs_memory elpis_hash Threads::Threads TIMEOUT 300)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT (ELPIS_ENABLE_ASAN OR ELPIS_ENABLE_UBSAN OR ELPIS_ENABLE_TSAN))
  elpis_add_test(ECS_C test_ecs_memory_alloc SOURCES memory/tests/test_ecs_memory_alloc.c memory/src/ecs_memory.c
    INCLUDES memory/include LIBS elpis_hash TIMEOUT 300)
  target_link_options(test_ecs_memory_alloc PRIVATE
    "LINKER:--wrap=malloc,--wrap=calloc,--wrap=realloc,--wrap=aligned_alloc,--wrap=free")
endif()
