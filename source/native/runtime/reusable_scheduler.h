/* SPDX-License-Identifier: Apache-2.0 */
#ifndef ELPIS_CR5_REUSABLE_SCHEDULER_H
#define ELPIS_CR5_REUSABLE_SCHEDULER_H
#include "elpis/geodome_scheduler.h"
typedef struct gsc_workspace gsc_workspace;
/* Private, serialized API. Reserve once, borrow a scheduler during bind/clear.
 * Do not call gsc_destroy on the borrowed scheduler. State must outlive binding.
 * No allocations, frees, qsort, or caller callbacks during bind/clear. */
gsc_rc gsc_workspace_reserve(uint32_t capacity,uint32_t width,gsc_workspace **out);
void gsc_workspace_destroy(gsc_workspace *w);
size_t gsc_workspace_bytes(const gsc_workspace *w);
gsc_rc gsc_workspace_bind(gsc_workspace *w,gds_state *st,const gd_index *idx,const gds_handle *hs,uint32_t n,const uint32_t *arcs,uint32_t m,gsc_limits lim,gsc_scheduler **out);
gsc_rc gsc_workspace_clear(gsc_workspace *w);
#endif
