/* SPDX-License-Identifier: Apache-2.0
 * Port of Geodome/geodome_state.py. See ../PROVENANCE.md. */
#include "elpis/geodome_state.h"
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <float.h>
#include <fenv.h>
#include <math.h>
_Static_assert(FLT_RADIX==2 && FLT_MANT_DIG==24 && FLT_MAX_EXP==128 && sizeof(float)==4, "IEEE binary32 required");
_Static_assert(DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 && sizeof(double)==8, "IEEE binary64 required");
struct gds_state {
    uint64_t owner, epoch;
    uint32_t count, capacity, width, precision, free_count;
    size_t stride, bytes;
    unsigned char *values, *stage;
    uint64_t *generation;
    uint32_t *slot_owner, *vertex_slot, *free_slots, *dest;
    unsigned char *seen;
};
/* Monotonic, bounded, volatile identity. Never recycle even after destroy.
 * A single loaded implementation is the scope of owner identity. */
static _Atomic uint64_t last_owner;
static int next_owner(uint64_t *out){
    uint64_t prev=atomic_load_explicit(&last_owner,memory_order_relaxed);
    for(;;){
        if(prev==UINT64_MAX)return 0;
        if(atomic_compare_exchange_weak_explicit(&last_owner,&prev,prev+1,memory_order_relaxed,memory_order_relaxed)){
            *out=prev+1;return 1;
        }
    }
}
static void initialize(gds_state *s){
    memset(s->values,0,s->bytes);memset(s->stage,0,s->bytes);
    memset(s->generation,0,s->capacity*sizeof(*s->generation));
    memset(s->seen,0,s->capacity);memset(s->dest,0,s->capacity*sizeof(*s->dest));
    for(uint32_t i=0;i<GD_VERTICES;i++)s->vertex_slot[i]=GD_NONE;
    for(uint32_t i=0;i<s->capacity;i++){s->slot_owner[i]=GD_NONE;s->free_slots[i]=s->capacity-1-i;}
    s->count=0;s->free_count=s->capacity;
}
gds_status gds_create(uint32_t width,gds_precision precision,uint32_t cap,gds_state **out){
    if(!out||!width||width>GDS_MAX_WIDTH||!cap||cap>GDS_MAX_CAPACITY||(precision!=GDS_F32&&precision!=GDS_F64))return GDS_RANGE;
    gds_state *s=calloc(1,sizeof(*s));if(!s)return GDS_ALLOC;
    s->width=width;s->capacity=cap;s->precision=(uint32_t)precision;
    s->stride=width*(precision==GDS_F32?sizeof(float):sizeof(double));s->bytes=cap*s->stride;
    s->values=malloc(s->bytes);s->stage=malloc(s->bytes);
    s->generation=malloc(cap*sizeof(*s->generation));s->slot_owner=malloc(cap*sizeof(*s->slot_owner));
    s->vertex_slot=malloc(GD_VERTICES*sizeof(*s->vertex_slot));s->free_slots=malloc(cap*sizeof(*s->free_slots));
    s->dest=malloc(cap*sizeof(*s->dest));s->seen=malloc(cap);
    if(!s->values||!s->stage||!s->generation||!s->slot_owner||!s->vertex_slot||!s->free_slots||!s->dest||!s->seen){gds_destroy(s);return GDS_ALLOC;}
    if(!next_owner(&s->owner)){gds_destroy(s);return GDS_EXHAUSTED;}
    initialize(s);*out=s;return GDS_OK;
}
void gds_destroy(gds_state *s){if(s){free(s->values);free(s->stage);free(s->generation);free(s->slot_owner);free(s->vertex_slot);free(s->free_slots);free(s->dest);free(s->seen);free(s);}}
gds_status gds_inspect(const gds_state *s,gds_stats *out){
    if(!s||!out)return GDS_RANGE;
    *out=(gds_stats){s->epoch,sizeof(*s)+2*s->bytes+GD_VERTICES*sizeof(uint32_t)+s->capacity*(sizeof(uint64_t)+3*sizeof(uint32_t)+1),s->bytes,s->count*s->stride,s->bytes,s->count,s->capacity,s->width,s->precision};return GDS_OK;
}
static gds_handle make_handle(const gds_state *s,uint32_t v,uint32_t slot){return (gds_handle){s->owner,s->epoch,s->generation[slot],v,slot};}
static gds_status validate(const gds_state *s,const gds_handle *h){
    if(!s||!h)return GDS_RANGE;
    if(h->owner!=s->owner||h->epoch!=s->epoch||h->vertex>=GD_VERTICES||h->slot>=s->capacity||s->vertex_slot[h->vertex]!=h->slot||s->slot_owner[h->slot]!=h->vertex||s->generation[h->slot]!=h->generation)return GDS_STALE;
    return GDS_OK;
}
gds_status gds_handle_of(const gds_state *s,uint32_t v,gds_handle *out){
    if(!s||!out||v>=GD_VERTICES)return GDS_RANGE;
    uint32_t slot=s->vertex_slot[v];if(slot==GD_NONE)return GDS_NONRESIDENT;
    if(slot>=s->capacity||s->slot_owner[slot]!=v)return GDS_INVARIANT;
    *out=make_handle(s,v,slot);return GDS_OK;
}
gds_status gds_acquire(gds_state *s,uint32_t v,gds_handle *out){
    if(!s||!out||v>=GD_VERTICES)return GDS_RANGE;
    if(s->vertex_slot[v]!=GD_NONE)return GDS_ALREADY;
    if(s->count>=s->capacity)return GDS_LIMIT;
    if(!s->free_count)return GDS_INVARIANT;
    uint32_t slot=s->free_slots[s->free_count-1];
    if(slot>=s->capacity||s->slot_owner[slot]!=GD_NONE)return GDS_INVARIANT;
    if(s->generation[slot]==UINT64_MAX)return GDS_EXHAUSTED;
    s->free_count--;s->vertex_slot[v]=slot;s->slot_owner[slot]=v;s->generation[slot]++;s->count++;
    *out=make_handle(s,v,slot);return GDS_OK;
}
gds_status gds_acquire_code(gds_state *s,const gd_index *idx,uint32_t code,gds_handle *out){
    uint32_t v;gd_status rc=gd_resolve_code(idx,code,&v);
    if(rc!=GD_OK)return rc==GD_UNOCCUPIED?GDS_NONRESIDENT:GDS_RANGE;
    return gds_acquire(s,v,out);
}
gds_status gds_read(const gds_state *s,const gds_handle *h,double *out,uint32_t width){
    if(!s||!out||width!=s->width)return GDS_RANGE;
    gds_status rc=validate(s,h);if(rc!=GDS_OK)return rc;
    const unsigned char *src=s->values+h->slot*s->stride;
    if(s->precision==GDS_F64)memcpy(out,src,s->stride);
    else for(uint32_t j=0;j<width;j++){float f;memcpy(&f,src+j*sizeof(f),sizeof(f));out[j]=(double)f;}
    return GDS_OK;
}
static gds_status convert(const gds_state *s,unsigned char *dst,const double *row){
    for(uint32_t j=0;j<s->width;j++){
        double x=row[j];if(!isfinite(x))return GDS_NONFINITE;
        if(s->precision==GDS_F64)memcpy(dst+j*sizeof(x),&x,sizeof(x));
        else{
            /* Overflow rounds to infinity at the binary32 midpoint under nearest/even.
             * Avoid an out-of-range C conversion even when rounding to FLT_MAX is valid. */
            if(fabs(x)>=0x1.ffffffp127)return GDS_NONFINITE;
            float f=fabs(x)>FLT_MAX?(signbit(x)?-FLT_MAX:FLT_MAX):(float)x;
            if(!isfinite(f))return GDS_NONFINITE;
            memcpy(dst+j*sizeof(f),&f,sizeof(f));
        }
    }
    return GDS_OK;
}
gds_status gds_commit(gds_state *s,const gds_handle *handles,const double *rows,uint32_t count,uint32_t width){
    if(!s||!handles||!rows||!count||count>GDS_MAX_BATCH||width!=s->width)return GDS_RANGE;
    if(s->precision==GDS_F32&&fegetround()!=FE_TONEAREST)return GDS_FP_ENV;
    gds_status rc=GDS_OK;
    /* No valid batch can have more distinct destinations than capacity. */
    if(count>s->capacity)return GDS_DUPLICATE;
    for(uint32_t i=0;i<count;i++){
        rc=validate(s,&handles[i]);if(rc!=GDS_OK)goto done;
        uint32_t slot=handles[i].slot;
        if(s->seen[slot]){rc=GDS_DUPLICATE;goto done;}
        s->seen[slot]=1;s->dest[i]=slot;
        rc=convert(s,s->stage+i*s->stride,rows+(size_t)i*width);if(rc!=GDS_OK)goto done;
    }
    for(uint32_t i=0;i<count;i++)memcpy(s->values+s->dest[i]*s->stride,s->stage+i*s->stride,s->stride);
done:
    memset(s->seen,0,s->capacity);memset(s->dest,0,count*sizeof(*s->dest));memset(s->stage,0,count*s->stride);return rc;
}
gds_status gds_release(gds_state *s,const gds_handle *h){
    gds_status rc=validate(s,h);if(rc!=GDS_OK)return rc;
    if(s->free_count>=s->capacity||!s->count)return GDS_INVARIANT;
    memset(s->values+h->slot*s->stride,0,s->stride);s->slot_owner[h->slot]=GD_NONE;s->vertex_slot[h->vertex]=GD_NONE;s->free_slots[s->free_count++]=h->slot;s->count--;return GDS_OK;
}
gds_status gds_reset(gds_state *s){if(!s)return GDS_RANGE;if(s->epoch==UINT64_MAX)return GDS_EXHAUSTED;initialize(s);s->epoch++;return GDS_OK;}
