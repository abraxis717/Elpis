/* SPDX-License-Identifier: Apache-2.0
 * Bounded sparse state port of HexaFlake Geodome v1.0.0. */
#ifndef ELPIS_GEODOME_STATE_H
#define ELPIS_GEODOME_STATE_H
#include "elpis/geodome.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GDS_MAX_CAPACITY 1024u
#define GDS_MAX_WIDTH 256u
#define GDS_MAX_BATCH 1024u
typedef struct gds_state gds_state;
typedef enum { GDS_OK=0, GDS_RANGE=1, GDS_ALLOC=2, GDS_NONRESIDENT=3,
 GDS_ALREADY=4, GDS_LIMIT=5, GDS_STALE=6, GDS_DUPLICATE=7,
 GDS_NONFINITE=8, GDS_EXHAUSTED=9, GDS_INVARIANT=10, GDS_FP_ENV=11 } gds_status;
typedef enum { GDS_F32=1, GDS_F64=2 } gds_precision;
/* Lifecycle guards, not unforgeable capabilities. Never dereference a destroyed state.
 * All calls on a state must be serialized; input/output arrays must be valid and
 * non-overlapping with state storage. Owner identity is process/library-instance local. */
typedef struct { uint64_t owner, epoch, generation; uint32_t vertex, slot; } gds_handle;
typedef struct { uint64_t epoch; size_t payload_bytes, reserved_value_bytes,
 resident_value_bytes, staging_bytes; uint32_t resident, capacity, width, precision; } gds_stats;
/* Fixed v1 geometry domain; state has no borrowed geometry lifetime. */
gds_status gds_create(uint32_t width, gds_precision precision, uint32_t capacity, gds_state **out);
void gds_destroy(gds_state *s);
gds_status gds_inspect(const gds_state *s, gds_stats *out);
gds_status gds_handle_of(const gds_state *s, uint32_t vertex, gds_handle *out);
gds_status gds_acquire(gds_state *s, uint32_t vertex, gds_handle *out);
gds_status gds_acquire_code(gds_state *s, const gd_index *idx, uint32_t code, gds_handle *out);
gds_status gds_read(const gds_state *s, const gds_handle *h, double *out, uint32_t width);
/* Double input rows, packed row-major, quantized to configured precision. Complete
 * validation before publication; all failures leave logical state unchanged. */
gds_status gds_commit(gds_state *s, const gds_handle *handles, const double *rows,
                      uint32_t count, uint32_t width);
gds_status gds_release(gds_state *s, const gds_handle *h);
gds_status gds_reset(gds_state *s);
#ifdef __cplusplus
}
#endif
#endif
