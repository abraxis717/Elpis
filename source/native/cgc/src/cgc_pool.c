#include "elpis/cgc_pool.h"
#include "cgc_cell_internal.h"
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <fenv.h>

typedef struct { cgr_cell cell; uint64_t generation; uint32_t key, occupied; } cgp_slot;
struct cgp_pool { uint64_t owner, epoch; uint32_t capacity, resident; cgp_slot slots[]; };
static _Atomic uint64_t owner_counter;
static uint64_t next_owner(void){
    uint64_t n=atomic_load_explicit(&owner_counter,memory_order_relaxed);
    do { if(n==UINT64_MAX)return 0; }
    while(!atomic_compare_exchange_weak_explicit(&owner_counter,&n,n+1,memory_order_relaxed,memory_order_relaxed));
    return n+1;
}
static size_t bytes(uint32_t capacity){return sizeof(cgp_pool)+(size_t)capacity*sizeof(cgp_slot);}
static int valid(const cgp_pool *p,const cgp_handle *h){
    if(!p||!h||h->owner!=p->owner||h->epoch!=p->epoch||h->slot>=p->capacity)return 0;
    const cgp_slot *s=&p->slots[h->slot];
    return s->occupied&&s->key==h->key&&s->generation==h->generation;
}
static cgp_handle handle(const cgp_pool *p,uint32_t i){
    const cgp_slot *s=&p->slots[i];return (cgp_handle){p->owner,p->epoch,s->generation,i,s->key};
}
/* Explicit release/reset destroys logical state. Volatile byte writes avoid
 * optimizing away destruction; this is not a physical RAM erasure claim. */
static void wipe(void *ptr,size_t n){volatile unsigned char *b=ptr;while(n--)*b++=0;}
cgr_status cgp_create(uint32_t capacity,cgp_pool **out){
    if(!out||!capacity||capacity>CGP_MAX_CAPACITY)return CGR_INVALID;
    cgp_pool *p=calloc(1,bytes(capacity));if(!p)return CGR_NOMEM;
    p->owner=next_owner();if(!p->owner){free(p);return CGR_LIMIT;}
    p->capacity=capacity;*out=p;return CGR_OK;
}
void cgp_destroy(cgp_pool *p){if(p){wipe(p,bytes(p->capacity));free(p);}}
cgr_status cgp_stats_read(const cgp_pool *p,cgp_stats *out){
    if(!p||!out)return CGR_INVALID;
    *out=(cgp_stats){p->epoch,bytes(p->capacity),p->capacity,p->resident};return CGR_OK;
}
cgr_status cgp_handle_of(const cgp_pool *p,uint32_t key,cgp_handle *out){
    if(!p||!out)return CGR_INVALID;
    for(uint32_t i=0;i<p->capacity;i++)if(p->slots[i].occupied&&p->slots[i].key==key){*out=handle(p,i);return CGR_OK;}
    return CGR_STATE;
}
cgr_status cgp_acquire(cgp_pool *p,uint32_t key,const double *initial,cgp_handle *out){
    if(!p||!out||!initial||fegetround()!=FE_TONEAREST)return CGR_INVALID;
    for(size_t j=0;j<CGR_PARAMS;j++)if(!isfinite(initial[j]))return CGR_NONFINITE;
    uint32_t free_slot=p->capacity;
    for(uint32_t i=0;i<p->capacity;i++){
        const cgp_slot *s=&p->slots[i];
        if(s->occupied&&s->key==key)return CGR_STATE;
        if(!s->occupied&&s->generation!=UINT64_MAX&&free_slot==p->capacity)free_slot=i;
    }
    if(free_slot==p->capacity)return CGR_LIMIT;
    cgp_slot *s=&p->slots[free_slot];
    memset(&s->cell,0,sizeof s->cell);
    memcpy(s->cell.initial,initial,sizeof s->cell.initial);
    memcpy(s->cell.slow,initial,sizeof s->cell.slow);
    memcpy(s->cell.fast,initial,sizeof s->cell.fast);
    s->generation++;s->key=key;s->occupied=1;p->resident++;
    *out=handle(p,free_slot);return CGR_OK;
}
cgr_status cgp_release(cgp_pool *p,const cgp_handle *h){
    if(!valid(p,h))return CGR_STATE;
    cgp_slot *s=&p->slots[h->slot];if(s->cell.active)return CGR_STATE;
    wipe(&s->cell,sizeof s->cell);s->key=0;s->occupied=0;p->resident--;return CGR_OK;
}
cgr_status cgp_reset(cgp_pool *p){
    if(!p)return CGR_INVALID;
    if(p->epoch==UINT64_MAX)return CGR_LIMIT;
    for(uint32_t i=0;i<p->capacity;i++)if(p->slots[i].occupied&&p->slots[i].cell.active)return CGR_STATE;
    wipe(p->slots,(size_t)p->capacity*sizeof(cgp_slot));p->resident=0;p->epoch++;return CGR_OK;
}
#define MUTATE(name) cgr_status cgp_##name(cgp_pool *p,const cgp_handle *h){if(!valid(p,h))return CGR_STATE;return cgr_##name(&p->slots[h->slot].cell);}
MUTATE(begin)
MUTATE(propose_update)
MUTATE(learn)
MUTATE(consolidate)
MUTATE(reset_fast)
MUTATE(commit)
MUTATE(abort)
#undef MUTATE
cgr_status cgp_observe(cgp_pool *p,const cgp_handle *h,uint64_t observation,const double *x,const double *y){if(!valid(p,h))return CGR_STATE;return cgr_observe(&p->slots[h->slot].cell,observation,x,y);}
cgr_status cgp_query(const cgp_pool *p,const cgp_handle *h,cgr_bank bank,const double *x,size_t rows,double *y){if(!valid(p,h))return CGR_STATE;return cgr_query(&p->slots[h->slot].cell,bank,x,rows,y);}
cgr_status cgp_inspect(const cgp_pool *p,const cgp_handle *h,cgr_info *out){if(!valid(p,h))return CGR_STATE;return cgr_inspect(&p->slots[h->slot].cell,out);}
cgr_status cgp_copy_bank(const cgp_pool *p,const cgp_handle *h,cgr_bank bank,double *out){if(!valid(p,h))return CGR_STATE;return cgr_copy_bank(&p->slots[h->slot].cell,bank,out);}
#ifdef CGP_TEST
/* Only compiled into the test executable, never into candidate library. */
void cgp_test_owner(uint64_t n){atomic_store(&owner_counter,n);}
void cgp_test_epoch(cgp_pool *p,uint64_t n){p->epoch=n;}
void cgp_test_generation(cgp_pool *p,uint32_t i,uint64_t n){p->slots[i].generation=n;}
void cgp_test_revision(cgp_pool *p,uint32_t i,uint64_t n){p->slots[i].cell.revision=n;}
#endif
