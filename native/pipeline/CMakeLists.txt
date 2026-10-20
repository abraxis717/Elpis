# P3 intake: ONLY bounded Regex lexer and execution. No query or authority graph.
find_package(PkgConfig REQUIRED)
pkg_check_modules(PCRE2 REQUIRED IMPORTED_TARGET libpcre2-8)
set(ING "${CMAKE_CURRENT_SOURCE_DIR}/ingress")

elpis_add_library(pipeline elpis_regex_ingress STATIC
  ${ING}/src/streaming_regex_ingress.cpp
  ${ING}/src/incremental_lexer.cpp)
target_include_directories(elpis_regex_ingress PUBLIC ${ING}/include PRIVATE ${ING}/src)
target_link_libraries(elpis_regex_ingress PUBLIC elpis_hash PRIVATE PkgConfig::PCRE2)

elpis_add_library(pipeline elpis_regex_execution STATIC ${ING}/src/regex_execution.c)
target_include_directories(elpis_regex_execution PUBLIC ${ING}/include)
target_link_libraries(elpis_regex_execution PUBLIC elpis_execution elpis_regex_ingress)

# The reference is test-only; no frozen oracle enters a production archive.
elpis_add_test_library(pipeline elpis_regex_lexer_reference
  ${ING}/tests/reference/incremental_lexer_r0.cpp)
target_include_directories(elpis_regex_lexer_reference PUBLIC ${ING}/tests/reference)
target_link_libraries(elpis_regex_lexer_reference PUBLIC elpis_hash PRIVATE PkgConfig::PCRE2)

elpis_add_test(pipeline test_regex_execution SOURCES ${ING}/tests/test_regex_execution.cpp
  LIBS elpis_regex_execution TIMEOUT 600)
elpis_add_test(pipeline test_regex_lexer_equivalence
  SOURCES ${ING}/tests/test_regex_lexer_equivalence.cpp
  LIBS elpis_regex_ingress elpis_regex_lexer_reference INCLUDES ${ING}/src TIMEOUT 300)
elpis_add_test(pipeline test_regex_bounded_profile
  SOURCES ${ING}/tests/test_regex_bounded_profile.cpp LIBS elpis_regex_ingress)
elpis_add_test(pipeline test_regex_stream
  SOURCES ${ING}/tests/test_regex_stream.cpp
  LIBS elpis_regex_ingress elpis_hash ${CMAKE_DL_LIBS})
elpis_add_test(pipeline test_regex_allocation
  SOURCES ${ING}/tests/test_regex_allocation.cpp LIBS elpis_regex_ingress)
elpis_add_test(pipeline test_regex_c_abi
  SOURCES ${ING}/tests/test_regex_c_abi.c LIBS elpis_regex_ingress)
elpis_add_test(pipeline test_regex_memory
  SOURCES ${ING}/tests/test_regex_memory.cpp LIBS elpis_regex_ingress)
