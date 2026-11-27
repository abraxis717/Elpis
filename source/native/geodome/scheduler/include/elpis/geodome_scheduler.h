/* SPDX-License-Identifier: Apache-2.0
 * Native port of HexaFlake Geodome v1.0.0 synchronous sparse scheduler. */
#ifndef ELPIS_GEODOME_SCHEDULER_H
#define ELPIS_GEODOME_SCHEDULER_H
#include "elpis/geodome_state.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GSC_MAX_ENROLLED GDS_MAX_CAPACITY
#define GSC_MAX_ARCS 24576u
#define GSC_MAX_ROUNDS 256u
#define GSC_MAX_VISITS (GSC_MAX_ARCS*GSC_MAX_ROUNDS)
#define GSC_PAYLOAD_LIMIT (16u*1024u*1024u)
typedef struct gsc_scheduler gsc_scheduler;
typedef enum { GSC_OK=0,GSC_RANGE=1,GSC_ALLOC=2,GSC_AUTHORITY=3,GSC_SESSION=4,GSC_STALE=5,GSC_CALLBACK=6,GSC_NONFINITE=7,GSC_FP_ENV=8,GSC_INVARIANT=9 } gsc_rc;
typedef enum { GSC_NEW=0,GSC_RUNNING=1,GSC_QUIESCENT=2,GSC_ROUND_BUDGET=3,GSC_ACTIVE_BUDGET=4,GSC_ARC_BUDGET=5 } gsc_status;
typedef struct {uint32_t max_active,max_rounds,max_visits;} gsc_limits;
typedef struct {uint32_t status,sources,arcs,destinations,changed,touched;} gsc_round;
typedef struct {uint32_t status,rounds,visits,frontier_count,enrolled,arcs;size_t payload_bytes;} gsc_stats;
typedef struct {uint32_t arc;const double *row;} gsc_message;
/* Trusted, pure callbacks. Return zero on success; fill every output component.
 * Inputs are read-only, transient, and cannot be retained. No mutation, reentry,
 * destruction, FP-environment changes, nonlocal exits or concurrency. */
typedef int (*gsc_transport)(void *,uint32_t,uint32_t,uint32_t,const double *,uint32_t,double *);
typedef int (*gsc_update)(void *,uint32_t,const double *,const gsc_message *,uint32_t,uint32_t,double *);
/* Borrow state until destroy; index required only during creation. All calls serialized.
 * Admission copies handles and arcs. No implicit acquisition, no whole-run rollback.
 * Errors leave logical state, frontier, counters and output unchanged. Budget stops
 * publish terminal status only. Callback side effects are outside this contract. */
gsc_rc gsc_create(gds_state *,const gd_index *,const gds_handle *,uint32_t,const uint32_t *,uint32_t,gsc_limits,gsc_scheduler **);
void gsc_destroy(gsc_scheduler *);
gsc_rc gsc_start(gsc_scheduler *,const uint32_t *,uint32_t);
gsc_rc gsc_step(gsc_scheduler *,gsc_transport,gsc_update,void *,gsc_round *);
gsc_rc gsc_inspect(const gsc_scheduler *,gsc_stats *);
gsc_rc gsc_frontier(const gsc_scheduler *,uint32_t *,uint32_t,uint32_t *);
#ifdef __cplusplus
}
#endif
#endif
