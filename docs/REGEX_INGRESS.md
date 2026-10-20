# Bounded native Regex ingress — publication scope

**Classification:** independent native lexical/execution mechanics only. No
semantic reasoning, continuity authority, cognitive qualification, hosted model,
trained parameter, HACF query integration or autonomous state publication.

## Public interface

* `native/pipeline/ingress/include/streaming_regex_ingress.h` publishes a V1
  bounded whole-input lexical parser and immutable result accessors.
* `native/pipeline/ingress/include/streaming_regex_ingress_v2.h` publishes V2
  create/feed/finalize/destroy streaming operations with per-stream source and
  evidence limits. Failed streams are terminal; feed does not publish results.
  Each live handle requires caller-side synchronization.
* `native/pipeline/ingress/include/regex_execution.h` exposes the opt-in
  `elpis_regex_execute` adapter to the independently published native execution
  substrate. Results are canonical JSON buffers, bounded by caller output cap.

A successful lexical match or exact source digest is not a semantic proof.
V1's carry profile requires the complete input to fit the caller's bounded
carry window. V2 does not promise constant compute time for arbitrary inputs.

## Source and dependency boundary

The 17 source/header/fixture/test files were copied byte-identically from
`abraxis717/Elpis_DEV`, commit `2c7588733180d1ab2e8e978cf277c30f9e4ab371`. The new
`native/pipeline/CMakeLists.txt` is a public-only minimal composition. Public
root CMake is modified only to add `native/pipeline`.

Runtime dependencies are the repository's existing `elpis_hash`,
`elpis_execution`, threads already required by the native foundation, and the
system-provided PCRE2 8-bit library found with `pkg-config` (`libpcre2-8`).
PCRE2 source and binary are **not** vendored in this repository. PCRE2 has its
own license: `BSD-3-Clause WITH PCRE2-exception`:
https://pcre2project.github.io/pcre2/project/licence/
Distribution of bundled downstream binaries must separately account for the
PCRE2 copyright and license conditions where applicable.

The following DEV components are deliberately absent: query-local proposal
registry/batches, Regex-to-HACF query bridge, ingress environment bridge,
semantic overlay, ECS_C authority, RuntimeCore, Python pipeline and model
weights. Their tests, data and evidence are not republished through this slice.

## Mechanical test boundary

Seven focused CTest cases cover ordered execution, differential lexer
reference, bounded parsing, stream lifecycle, allocation fault handling,
C ABI and measured memory growth. The isolated publication intake qualified
against public commit `c5920fe45e89fab5096368107418ea7363edda43` with all 110 registered normal tests passing;
seven Regex tests passed independently with ASan and UBSan enabled (the
sanitizer build registers 109 tests, because `ECS_C.test_ecs_memory_alloc`
is intentionally excluded). No claim is made that all 109 sanitizer tests ran.

These results are specific to the pinned source/ABI and evidence. They do not
qualify open-ended cognition or the separately unpublished runtime. The
complete machine-local evidence remains outside this public source release.

## Licensing and authority boundary

The root repository carries Apache-2.0, but contributor identities and Git
history alone do not establish source copyright or authorization. Confirm the
rights to redistribute the selected DEV contribution set under the intended
terms independently before public push. The `UNLICENSED` DEV ECS_C authority
is not included or relicensed in this component.
