/* SPDX-License-Identifier: Apache-2.0
 * Private owning translation unit: compile instead of (not alongside) the
 * pinned geodome_state.c. The original implementation is included verbatim. */
#include "geodome_state.c"
#include "shadow.h"
int ct_gds_copy(gds_state *d,const gds_state *s){
    if(!d||!s||d==s||d->capacity!=s->capacity||d->width!=s->width||d->precision!=s->precision||d->bytes!=s->bytes)return 0;
    d->owner=s->owner;d->epoch=s->epoch;d->count=s->count;d->free_count=s->free_count;
    memcpy(d->values,s->values,s->bytes);memcpy(d->stage,s->stage,s->bytes);
    memcpy(d->generation,s->generation,s->capacity*sizeof(*s->generation));
    memcpy(d->slot_owner,s->slot_owner,s->capacity*sizeof(*s->slot_owner));
    memcpy(d->vertex_slot,s->vertex_slot,GD_VERTICES*sizeof(*s->vertex_slot));
    memcpy(d->free_slots,s->free_slots,s->capacity*sizeof(*s->free_slots));
    memcpy(d->dest,s->dest,s->capacity*sizeof(*s->dest));memcpy(d->seen,s->seen,s->capacity);
    return 1;
}
