/* SPDX-License-Identifier: Apache-2.0
 * Private owning translation unit, replacing cgc_pool.c in this candidate only. */
#include "cgc_pool.c"
#include "shadow.h"
int ct_cgp_copy(cgp_pool *d,const cgp_pool *s){
    if(!d||!s||d==s||d->capacity!=s->capacity)return 0;
    memcpy(d,s,bytes(s->capacity));return 1;
}
