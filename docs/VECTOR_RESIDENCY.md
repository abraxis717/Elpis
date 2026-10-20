# HACF exact-vector residency — native publication boundary

**Classification:** an additive native C ABI entry point on the existing C++
exact-vector search library. The change is an active runtime mechanism, not a
trained model, authority service, semantic proof or scientific result.

## Contract and use

`elpis_vector_index_search_nowait()` is declared in
`native/structure/hacf/include/elpis/vector_index.h`. It executes the same
exact vector search as `elpis_vector_index_search()` and returns the same
ordered hits and digest when residency permits completion.

The new entry point makes **one residency acquisition attempt per shard**.
It does not sleep or retry while another owner moves a shard or while pinned
objects exhaust the WARM budget. On these conditions it refuses with
`ELPIS_VEC_E_RESIDENCY`, retains the native FMS cause and does not publish a
partial hit set. The existing `elpis_vector_index_search()` retains its
explicit bounded-wait behavior.

**"Nowait" is not a diskless or guaranteed nonblocking operation.** The
single acquisition attempt may synchronously promote a COLD shard into WARM,
including filesystem I/O and digest verification. The contract concerns waits
for *other residency owners*; it is not a wall-clock or I/O isolation promise.
Callers requiring no cold I/O must establish resident state separately.

## Exact source scope

Only these files were imported byte-for-byte from
`abraxis717/Elpis_DEV` commit
`2c7588733180d1ab2e8e978cf277c30f9e4ab371`:

* `native/structure/hacf/include/elpis/vector_index.h`
* `native/structure/hacf/src/retrieval/vector/vector_index.cpp`
* `native/structure/hacf/tests/vector/test_vector_fms.cpp`

There are no build-system changes. The new native C symbol is
`elpis_vector_index_search_nowait`; no existing vector C export is removed.
The public hybrid query structure is **not** modified. In particular, DEV's
additional hybrid retrieval policy and its ABI-layout change are excluded,
as are its Python adapters, retrieval bridge, ECS_C authority and RuntimeCore.

## Mechanical admission and qualification limits

The isolated P4 qualification used public base commit
`77dccd7a7cf0d20c31153e98f96f5f1b6fd90342`, source patch SHA-256
`8cdee8997779aedf4128dec2f57a55a798beb6bf1263ebc7c28137b1cd783e8b`.
It reported 110/110 normal CTests and the focused vector residency regression
under combined ASan/UBSan (1/1). The regression checks equivalent output,
refusal under pinned pressure, bounded waiting by the original entry point,
and pin cleanup. It does not establish universal latency, diskless operation,
scientific efficacy, general safety or qualification of unreleased components.

Full test evidence stays in the local `/mnt/primesauce/` P4 qualification
workspace, not in this public source repository.
