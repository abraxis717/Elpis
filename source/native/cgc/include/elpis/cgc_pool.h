#ifndef ELPIS_CGC_POOL_H
#define ELPIS_CGC_POOL_H
#include "elpis/cgc_r97w.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Serialized, trusted caller. Handles guard lifetime, not authorization.
 * Keys are caller-assigned local identities; no geometry/evidence authority.
 * All buffers obey the cell API lengths. No pointer to a resident cell escapes.
 * Invalid/stale/foreign handle and duplicate key return CGR_STATE.
 * Release/reset refuse open transactions; explicit abort is required.
 * Release/reset discard both learned banks. No eviction or implicit persistence. */
enum { CGP_MAX_CAPACITY=1024 };
typedef struct cgp_pool cgp_pool;
typedef struct { uint64_t owner, epoch, generation; uint32_t slot, key; } cgp_handle;
typedef struct { uint64_t epoch; size_t payload_bytes; uint32_t capacity, resident; } cgp_stats;
cgr_status cgp_create(uint32_t capacity,cgp_pool **out);
void cgp_destroy(cgp_pool *p);
cgr_status cgp_stats_read(const cgp_pool *p,cgp_stats *out);
cgr_status cgp_acquire(cgp_pool *p,uint32_t key,const double *initial,cgp_handle *out);
cgr_status cgp_handle_of(const cgp_pool *p,uint32_t key,cgp_handle *out);
cgr_status cgp_release(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_reset(cgp_pool *p);
cgr_status cgp_begin(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_observe(cgp_pool *p,const cgp_handle *h,uint64_t observation,const double *x,const double *y);
cgr_status cgp_propose_update(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_learn(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_consolidate(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_reset_fast(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_commit(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_abort(cgp_pool *p,const cgp_handle *h);
cgr_status cgp_query(const cgp_pool *p,const cgp_handle *h,cgr_bank bank,const double *x,size_t rows,double *y);
cgr_status cgp_inspect(const cgp_pool *p,const cgp_handle *h,cgr_info *out);
cgr_status cgp_copy_bank(const cgp_pool *p,const cgp_handle *h,cgr_bank bank,double *out);
#ifdef __cplusplus
}
#endif
#endif
