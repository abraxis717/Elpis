# P9 — hybrid retrieval opt-in residency, ABI-V1 compatibility

**Publication scope:** bounded C/C++ retrieval interface adaptation, not an independent runtime or an exact DEV import.

## Preserved public compatibility

- `ELPIS_HYBRID_ABI_VERSION` remains **1**, and the published `elpis_hybrid_query` structure remains byte-for-byte unchanged. Existing callers and their allocation/field offsets are unaffected.
- `elpis_hybrid_retrieve()` remains the original bounded-wait/retry entry point. No implicit change to its vector-residency choice was made.
- The new **opt-in** `elpis_hybrid_retrieve_with_residency(retriever, query, residency, bundle_out)` accepts `ELPIS_HYBRID_RESIDENCY_NOWAIT` (0) and `ELPIS_HYBRID_RESIDENCY_BOUNDED_WAIT` (1). Other values are rejected.
- Both public entry points call **one** retrieval implementation. Fusion, manifest binding, filtering, retrieval-bundle identity, and semantic query structure remain common. The policy selects between the existing `elpis_vector_index_search()` and published `elpis_vector_index_search_nowait()`.
- "NOWAIT" means no bounded retry/wait for another shard's residency movement; a cold shard **may still be synchronously promoted and read**. It is **not** an I/O-free, mutex-nonblocking, real-time, or end-to-end latency guarantee.

## Independent qualification boundary

At pinned public main `5bf25ff4f25672a7c4380b2f5124527bec9e7d9f` and DEV main `2c7588733180d1ab2e8e978cf277c30f9e4ab371`, P9 R0 qualified this two-file source adaptation with **114/114 normal CTests and 1/1 focused ASan/UBSan test**. The one-off CMake/test overlay was used only for qualification and is not imported into this publication. This release does not claim independent qualification of any broader DEV component.

## Explicit migration debt (do not silently discard)

DEV currently adds `uint32_t residency` *inside* `elpis_hybrid_query` without changing the V1 ABI number, and defaults that in-struct field to NOWAIT. Directly importing the DEV header/implementation would therefore change the published binary structure and legacy default semantics. Public P9 instead exposes an **explicit parameter**, preserving the public V1 layout and original default.

The two interfaces are intentionally **not byte-identical**. A future **separately authorized DEV migration** must reconcile them at this seam, ideally by retaining the single parameterized retrieval implementation and adding the explicit API in DEV, while restricting any larger query structure to a clearly versioned type/ABI. Preserve legacy bounded-wait compatibility. Do not copy the public adaptation back to DEV or bump ABI implicitly as part of this publication.

**Stop condition:** No further public-only hybrid ABI adaptations until this divergence is reviewed upstream. No new Python sources, runtime authority, independent semantic admission or autonomy are included.
