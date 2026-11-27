/* SPDX-License-Identifier: Apache-2.0
 * Private owning translation unit: replaces (never accompanies) the exact
 * sealed ecs_c_enrollment.c. Only updates a locator's adaptive revision. */
#include "ecs_c_enrollment.c"
#include "shadow.h"
int ct_eve_rebind(eve_store *s,uint64_t t,const eve_locator *old,const eve_locator *next){
    int rc=tx_ok(s,t);if(rc)return rc;
    if(!old||!next||old->cell_revision==UINT64_MAX||next->cell_revision!=old->cell_revision+1)return INVALID;
    eve_locator normalized=*next;normalized.cell_revision=old->cell_revision;
    if(!valid_locator(old)||!same_locator(old,&normalized))return INVALID;
    bank *b=&s->staged;unsigned n=0;
    for(uint32_t i=0;i<s->lc;i++)if(b->links[i].record_plus_one&&b->links[i].locator.vertex==old->vertex){
        if(!same_locator(&b->links[i].locator,old)||b->links[i].record_plus_one>s->rc||!b->records[b->links[i].record_plus_one-1].source_version)return ELPIS_ECS_C_CORRUPT;
        n++;
    }
    if(!n)return EVE_NOT_FOUND;
    /* No fallible operation after the full scan. This includes suspended and
     * retired evidence: binding maintenance does not change semantic liveness. */
    for(uint32_t i=0;i<s->lc;i++)if(b->links[i].record_plus_one&&b->links[i].locator.vertex==old->vertex)b->links[i].locator.cell_revision=next->cell_revision;
    return OK;
}
