function(elpis_warnings target)
  if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    if(ELPIS_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE -Werror)
    endif()
  endif()
endfunction()

function(elpis_add_library subsystem name kind)
  add_library(${name} ${kind} ${ARGN})
  elpis_warnings(${name})
endfunction()

function(elpis_add_test_library subsystem name)
  add_library(${name} STATIC ${ARGN})
  elpis_warnings(${name})
  target_compile_options(${name} PRIVATE -UNDEBUG)
endfunction()

function(elpis_add_test subsystem name)
  cmake_parse_arguments(
    T ""
    "TIMEOUT"
    "SOURCES;LIBS;ARGS;INCLUDES;DEFINES"
    ${ARGN}
  )

  add_executable(${name} ${T_SOURCES})

  if(T_LIBS)
    target_link_libraries(${name} PRIVATE ${T_LIBS})
  endif()

  if(T_INCLUDES)
    target_include_directories(${name} PRIVATE ${T_INCLUDES})
  endif()

  if(T_DEFINES)
    target_compile_definitions(${name} PRIVATE ${T_DEFINES})
  endif()

  elpis_warnings(${name})
  target_compile_options(${name} PRIVATE -UNDEBUG)

  add_test(NAME ${subsystem}.${name} COMMAND ${name} ${T_ARGS})

  set(scratch "${CMAKE_CURRENT_BINARY_DIR}/test-state/${name}")
  file(MAKE_DIRECTORY "${scratch}")

  set_tests_properties(
    ${subsystem}.${name}
    PROPERTIES
      LABELS "${subsystem}"
      WORKING_DIRECTORY "${scratch}"
  )

  if(T_TIMEOUT)
    set_tests_properties(
      ${subsystem}.${name}
      PROPERTIES TIMEOUT ${T_TIMEOUT}
    )
  endif()
endfunction()

function(elpis_add_cargo_target subsystem name kind output)
  add_custom_target(${name} ALL DEPENDS "${output}")
endfunction()
