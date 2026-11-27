/* SPDX-License-Identifier: Apache-2.0 */
#ifndef ELPIS_COGNITIVE_BINDING_H
#define ELPIS_COGNITIVE_BINDING_H
#include "elpis/geodome_state.h"
#include "elpis/cgc_pool.h"
#include "elpis/ecs_c_enrollment.h"
/* Borrowed, serialized trusted caller. All components must outlive the call.
 * One adaptive key per physical vertex, selected by policy (key=vertex).
 * Strict current-revision locator policy for this gate only. Never use revision
 * or generation to select semantic resolution. No ownership or commit authority. */
typedef struct { const gd_index *index; const gds_state *state; const cgp_pool *pool; eve_store *evidence; } cb_view;
#define CB_INVALID 200
#define CB_PHYSICAL 201
#define CB_ADAPTIVE 202
#define CB_STALE_LOCATOR 203
#define CB_INVARIANT 204
#define CB_BUSY 205
int cb_locator(const cb_view *v, uint32_t code, eve_locator *out);
int cb_validate(const cb_view *v, const eve_locator *l);
/* Validate an actual resident locator before staging; not a commit guarantee. */
int cb_admit(const cb_view *v, uint64_t tx, const eve_record *r, const eve_locator *l);
/* Whole-obligation fail-closed validation; output unchanged on any refusal.
 * Source liveness remains entirely ECS_C's law. No stale link is dropped. */
int cb_lookup(const cb_view *v, const eve_coordinate *c, const eve_key *k, eve_answer *out);
#endif
