/* SPDX-License-Identifier: Apache-2.0 */
#include "elpis/cognitive_binding.h"
static int valid_view(const cb_view *v){return v&&v->index&&v->state&&v->pool&&v->evidence;}
static int from_vertex(const cb_view *v,uint32_t vertex,eve_locator *out,uint32_t *active){
    uint32_t code, roundtrip;gds_handle g;cgp_handle h;cgr_info i;
    if(gd_vertex_code(v->index,vertex,&code)!=GD_OK||gd_resolve_code(v->index,code,&roundtrip)!=GD_OK||roundtrip!=vertex)return CB_PHYSICAL;
    if(gds_handle_of(v->state,vertex,&g)!=GDS_OK)return CB_PHYSICAL;
    if(cgp_handle_of(v->pool,vertex,&h)!=CGR_OK||cgp_inspect(v->pool,&h,&i)!=CGR_OK)return CB_ADAPTIVE;
    *out=(eve_locator){.state_owner=g.owner,.state_epoch=g.epoch,.state_generation=g.generation,
        .cell_owner=h.owner,.cell_epoch=h.epoch,.cell_generation=h.generation,.cell_revision=i.revision,
        .vertex=g.vertex,.state_slot=g.slot,.cell_slot=h.slot,.cell_key=h.key};
    *active=i.active;return 0;
}
static int same(const eve_locator *a,const eve_locator *b){
    return a->state_owner==b->state_owner&&a->state_epoch==b->state_epoch&&a->state_generation==b->state_generation&&
        a->cell_owner==b->cell_owner&&a->cell_epoch==b->cell_epoch&&a->cell_generation==b->cell_generation&&
        a->cell_revision==b->cell_revision&&a->vertex==b->vertex&&a->state_slot==b->state_slot&&a->cell_slot==b->cell_slot&&a->cell_key==b->cell_key;
}
int cb_locator(const cb_view *v,uint32_t code,eve_locator *out){
    uint32_t vertex,active;eve_locator l;
    if(!valid_view(v)||!out)return CB_INVALID;
    if(gd_resolve_code(v->index,code,&vertex)!=GD_OK)return CB_PHYSICAL;
    int rc=from_vertex(v,vertex,&l,&active);if(rc)return rc;
    if(active)return CB_BUSY;
    *out=l;return 0;
}
static int validate(const cb_view *v,const eve_locator *l,int idle){
    if(!valid_view(v)||!l)return CB_INVALID;
    eve_locator current;uint32_t active;
    int rc=from_vertex(v,l->vertex,&current,&active);if(rc)return rc;
    if(!same(l,&current))return CB_STALE_LOCATOR;
    if(idle&&active)return CB_BUSY;
    return 0;
}
int cb_validate(const cb_view *v,const eve_locator *l){return validate(v,l,0);}
int cb_admit(const cb_view *v,uint64_t tx,const eve_record *r,const eve_locator *l){
    if(!r)return CB_INVALID;
    int rc=validate(v,l,1);if(rc)return rc;
    return eve_admit(v->evidence,tx,r,l);
}
int cb_lookup(const cb_view *v,const eve_coordinate *c,const eve_key *k,eve_answer *out){
    if(!valid_view(v)||!c||!k||!out)return CB_INVALID;
    eve_answer a;int rc=eve_lookup(v->evidence,c,k,&a);if(rc)return rc;
    if(a.locators>EVE_MAX_LINKS||a.records>EVE_MAX_RECORDS)return CB_INVARIANT;
    for(uint32_t offset=0;offset<a.locators;){
        eve_member page[16];uint32_t n=0,limit=a.locators-offset;if(limit>16)limit=16;
        rc=eve_page(v->evidence,c,k,offset,limit,page,&n);if(rc)return rc;
        if(n!=limit)return CB_INVARIANT;
        for(uint32_t j=0;j<n;j++){rc=cb_validate(v,&page[j].locator);if(rc)return rc;}
        offset+=n;
    }
    *out=a;return 0;
}
