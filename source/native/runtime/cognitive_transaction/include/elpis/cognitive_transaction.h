/* SPDX-License-Identifier: Apache-2.0 */
#ifndef ELPIS_COGNITIVE_TRANSACTION_H
#define ELPIS_COGNITIVE_TRANSACTION_H
#include "elpis/cognitive_binding.h"
#include "elpis/geodome_scheduler.h"
/* Exclusive, serialized owner. No raw component pointers or speculative handles
 * escape. An operation failure with the active token poisons that transaction;
 * explicit abort is then mandatory. No session transitions while a turn is open.
 * Supports enrollment/attachment OR one evidence-authorized R97W episode
 * OR one explicit bounded frozen-weight transport pass. An adaptation may
 * be followed by exactly one CGC transport pass in the same transaction. */
typedef struct ct_runtime ct_runtime;
enum { CT_INVALID=300,CT_BUSY=301,CT_TOKEN=302,CT_POISONED=303,CT_STALE=304,CT_INVARIANT=305,CT_AUTHORITY=306,CT_MODE=307,CT_FUEL=308 };
typedef struct { uint32_t cells,records,links,width; elpis_ecs_c_session_config session; } ct_config;
typedef struct { uint32_t physical,adaptive,records,links,open,poisoned; size_t component_payload; } ct_stats;
int ct_create(const ct_config *cfg,ct_runtime **out);
void ct_destroy(ct_runtime *r);
int ct_coordinate(const ct_runtime *r,eve_coordinate *out);
int ct_vertex_code(const ct_runtime *r,uint32_t vertex,uint32_t *out);
int ct_stats_read(const ct_runtime *r,ct_stats *out);
int ct_entity_at(const ct_runtime *r,uint32_t i,elpis_ecs_c_entity *out);
int ct_next_entity(const ct_runtime *r,uint8_t kind,const uint8_t label[32],uint8_t out[32]);
int ct_source_transition(ct_runtime *r,const elpis_ecs_c_session_coordinate *expected,const uint8_t event[512]);
int ct_begin(ct_runtime *r,const eve_coordinate *expected,uint64_t *token);
/* New cell and first association are indivisible at publication. Row length=width,
 * initial length=CGR_PARAMS. No outputs from staging. */
int ct_enroll(ct_runtime *r,uint64_t token,uint32_t code,const double *row,const double *initial,const eve_record *record);
int ct_attach(ct_runtime *r,uint64_t token,uint32_t code,const eve_record *record);
/* Exact support batch digest: domain + 32x5 X and 32x3 Y IEEE binary64 LE.
 * Bias must be exactly 1.0; all inputs/targets finite. Evidence target must equal
 * this digest. Only committed, source-live, nonconflicting evidence attached to
 * the requested cell authorizes one explicit eight-step episode. No mixed
 * enrollment/learning transaction. No implicit learning or source admission. */
int ct_support_digest(const double *x,const double *y,uint8_t out[32]);
int ct_adapt(ct_runtime *r,uint64_t token,uint32_t code,const eve_key *key,
             const uint8_t evidence_id[32],const double *x,const double *y);
/* Explicit trusted transport plan; codes identify resident cells; arcs are
 * directed physical arc IDs, not semantic relations. Width must be 3.
 * Identity or frozen CGC slow-bank messages; destination becomes inbox mean.
 * A requested round horizon is not a convergence claim. Active/visit exhaustion
 * poisons the entire transaction. Temporary scheduler allocation is bounded.
 * After ct_adapt, only CGC transport is permitted; it reads staged slow weights.
 * No second adaptation or transport pass is allowed.
 * Result describes successful staging only, not committed state. */
enum { CT_TRANSPORT_IDENTITY=0, CT_TRANSPORT_CGC=1 };
int ct_propagate(ct_runtime *r,uint64_t token,const uint32_t *codes,uint32_t n,
                 const uint32_t *arcs,uint32_t m,const uint32_t *seeds,uint32_t ns,
                 gsc_limits limits,uint32_t mode,gsc_stats *out);
int ct_commit(ct_runtime *r,uint64_t token,eve_receipt *out);
int ct_abort(ct_runtime *r,uint64_t token);
int ct_lookup(const ct_runtime *r,const eve_coordinate *expected,const eve_key *key,eve_answer *out);
int ct_read(const ct_runtime *r,const eve_coordinate *expected,uint32_t code,double *row,uint32_t width,double *slow,double *fast,eve_locator *locator);
#endif
