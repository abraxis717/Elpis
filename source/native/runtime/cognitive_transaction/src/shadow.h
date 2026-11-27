/* Private copy operations: source and destination are equal-capacity, allocated,
 * exclusively owned images of ONE logical object. Never use on independent
 * public objects. Only the committed image is externally observable. */
#ifndef CT_SHADOW_H
#define CT_SHADOW_H
#include "elpis/geodome_state.h"
#include "elpis/cgc_pool.h"
int ct_gds_copy(gds_state *dst,const gds_state *src);
int ct_cgp_copy(cgp_pool *dst,const cgp_pool *src);
#include "elpis/ecs_c_enrollment.h"
int ct_eve_rebind(eve_store *s,uint64_t token,const eve_locator *old,const eve_locator *next);
#endif
