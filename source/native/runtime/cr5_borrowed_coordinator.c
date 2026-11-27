/* SPDX-License-Identifier: Apache-2.0 */
#include "borrowed.h"
#include "reusable_scheduler.h"
#include "turn_budget.h"
#include "shadow.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include "elpis/sha256.h"
/* Bounded volatile ledger, included in the derived coordinator owning TU. */
static const ct_turn_budget tb_ceiling={{64,256,64,2048,512,4096,65536,393216,65536,256,GSC_MAX_VISITS,262144}};
typedef struct {uint8_t id[32];uint32_t count;} tb_source;
typedef struct {
    uint32_t open,n_sources;
    ct_turn_budget limit,used;
    elpis_ecs_c_session_coordinate pin;
    tb_source sources[256];
} tb_ledger;

struct ct_runtime {
    gd_index *index; elpis_ecs_c_session *session; eve_store *evidence;
    gds_state *state[2]; cgp_pool *pool[2];
    gsc_workspace *transport_workspace;
    uint32_t live,failed,width,mode,owns_session; uint64_t token; size_t payload;
    elpis_ecs_c_session_coordinate borrowed_pin;
    tb_ledger ledger; tb_ledger *budget;
};
int ct_budget_open(const ct_runtime*r){return r&&r->ledger.open;}
int ct_budget_start(ct_runtime*r,const ct_turn_budget*limit){
    if(!r||!limit)return CT_INVALID;
    if(r->token||r->ledger.open)return CT_BUSY;
    for(unsigned i=0;i<TB_N;i++)if(limit->v[i]>tb_ceiling.v[i])return CT_FUEL;
    elpis_ecs_c_session_coordinate pin;int rc=elpis_ecs_c_session_read_coordinate(r->session,&pin);if(rc)return rc;
    memset(&r->ledger,0,sizeof r->ledger);r->ledger.limit=*limit;r->ledger.pin=pin;r->ledger.open=1;return 0;
}
int ct_budget_end(ct_runtime*r){if(!r||!r->ledger.open)return CT_INVALID;if(r->token)return CT_BUSY;memset(&r->ledger,0,sizeof r->ledger);return 0;}
int ct_budget_usage(const ct_runtime*r,ct_turn_budget*out){if(!r||!out||!r->ledger.open)return CT_INVALID;*out=r->ledger.used;return 0;}
/* Pointer to ledger is intentionally mutable through a const cognitive view:
 * queries do not mutate cognitive data but must charge the owning turn. */
static int tb_charge(const ct_runtime*r,ct_turn_budget cost){
    tb_ledger*b=r->budget;
    if(!b->open){
#if defined(CR5_REGRESSION_ALLOW_UNMETERED)
        return 0;
#else
        return CT_FUEL;
#endif
    }
    elpis_ecs_c_session_coordinate c;int rc=elpis_ecs_c_session_read_coordinate(r->session,&c);if(rc)return rc;
    if(c.instance!=b->pin.instance||c.generation!=b->pin.generation||memcmp(c.session,b->pin.session,32)||memcmp(c.state_root,b->pin.state_root,32))return CT_STALE;
    for(unsigned i=0;i<TB_N;i++)if(cost.v[i]>b->limit.v[i]-b->used.v[i])return CT_FUEL;
    for(unsigned i=0;i<TB_N;i++)b->used.v[i]+=cost.v[i];
    return 0;
}
static int tb_admit(ct_runtime*r,const eve_record*rec){
    int rc=tb_charge(r,(ct_turn_budget){.v={[TB_ADMISSIONS]=1}});if(rc||!r->ledger.open)return rc;
    if(!rec)return CT_INVALID;
    uint32_t limit=0;rc=elpis_ecs_c_session_check_evidence(r->session,rec->key.source,rec->source_version,rec->key.scope,&limit);if(rc)return rc;
    tb_ledger*b=&r->ledger;uint32_t i=0;for(;i<b->n_sources;i++)if(!memcmp(b->sources[i].id,rec->key.source,32))break;
    if(i==b->n_sources){if(i>=256)return CT_FUEL;memcpy(b->sources[i].id,rec->key.source,32);b->n_sources++;}
    if(b->sources[i].count>=limit)return EVE_TURN_LIMIT;
    b->sources[i].count++;return 0;
}

static cb_view view(const ct_runtime *r,unsigned i){return (cb_view){r->index,r->state[i],r->pool[i],r->evidence};}
static int current(const ct_runtime *r,const eve_coordinate *expected){
    if(!r||!expected)return CT_INVALID;
    eve_coordinate c;int rc=eve_coordinate_read(r->evidence,&c);if(rc)return rc;
    return c.store_instance==expected->store_instance&&c.revision==expected->revision&&
        c.session.instance==expected->session.instance&&c.session.generation==expected->session.generation&&
        !memcmp(c.session.session,expected->session.session,32)&&!memcmp(c.session.state_root,expected->session.state_root,32)?0:CT_STALE;
}
void ct_destroy(ct_runtime *r){if(r){gsc_workspace_destroy(r->transport_workspace);eve_destroy(r->evidence);for(unsigned i=0;i<2;i++){gds_destroy(r->state[i]);cgp_destroy(r->pool[i]);}gd_destroy(r->index);if(r->owns_session&&r->session)elpis_ecs_c_session_destroy(r->session);free(r);}}
static int create_common(const ct_config *c,elpis_ecs_c_session *borrow,ct_runtime **out){
    if(!c||!out||!c->cells||c->cells>1024||!c->records||c->records>EVE_MAX_RECORDS||!c->links||c->links>EVE_MAX_LINKS||!c->width||c->width>GDS_MAX_WIDTH)return CT_INVALID;
    ct_runtime *r=calloc(1,sizeof *r);if(!r)return ELPIS_ECS_C_NOMEM;
    r->budget=&r->ledger;
    int rc=gd_create(&r->index);if(rc)goto fail;
    if(borrow){r->session=borrow;}else{r->owns_session=1;rc=elpis_ecs_c_session_create(&c->session,&r->session);if(rc)goto fail;}
    rc=eve_create(r->session,c->records,c->links,&r->evidence);if(rc)goto fail;
    r->width=c->width;r->payload=sizeof *r+gd_payload_bytes(r->index);
    for(unsigned i=0;i<2;i++){
        rc=gds_create(c->width,GDS_F64,c->cells,&r->state[i]);if(rc)goto fail;
        rc=cgp_create(c->cells,&r->pool[i]);if(rc)goto fail;
        gds_stats g;cgp_stats p;rc=gds_inspect(r->state[i],&g);if(rc)goto fail;rc=cgp_stats_read(r->pool[i],&p);if(rc)goto fail;r->payload+=g.payload_bytes+p.payload_bytes;
    }
    eve_stats e;rc=eve_inspect(r->evidence,&e);if(rc)goto fail;r->payload+=e.payload_bytes;
    if(c->width==3){
        rc=gsc_workspace_reserve(c->cells,c->width,&r->transport_workspace);if(rc)goto fail;
        r->payload+=gsc_workspace_bytes(r->transport_workspace);
    }
    *out=r;return 0;
fail:ct_destroy(r);return rc;
}
int ct_create(const ct_config *c,ct_runtime **out){return create_common(c,NULL,out);}
int ct_create_borrowed(elpis_ecs_c_session *session,uint32_t cells,uint32_t records,uint32_t links,uint32_t width,ct_runtime **out){
    if(!session)return CT_INVALID;
    ct_config c={.cells=cells,.records=records,.links=links,.width=width};
    return create_common(&c,session,out);
}
int ct_coordinate(const ct_runtime *r,eve_coordinate *out){return r?eve_coordinate_read(r->evidence,out):CT_INVALID;}
int ct_vertex_code(const ct_runtime *r,uint32_t vertex,uint32_t *out){return r?gd_vertex_code(r->index,vertex,out):CT_INVALID;}
int ct_stats_read(const ct_runtime *r,ct_stats *out){
    if(!r||!out)return CT_INVALID;
    gds_stats g;cgp_stats p;eve_stats e;int rc=gds_inspect(r->state[r->live],&g);if(rc)return rc;
    rc=cgp_stats_read(r->pool[r->live],&p);if(rc)return rc;rc=eve_inspect(r->evidence,&e);if(rc)return rc;
    *out=(ct_stats){g.resident,p.resident,e.records,e.locators,r->token!=0,r->failed,r->payload};return 0;
}
int ct_entity_at(const ct_runtime *r,uint32_t i,elpis_ecs_c_entity *out){return r&&out?elpis_ecs_c_session_entity_at(r->session,i,out):CT_INVALID;}
int ct_next_entity(const ct_runtime *r,uint8_t k,const uint8_t l[32],uint8_t out[32]){return r&&l&&out?elpis_ecs_c_session_next_entity_id(r->session,k,l,out):CT_INVALID;}
int ct_source_transition(ct_runtime *r,const elpis_ecs_c_session_coordinate *e,const uint8_t event[512]){
    if(!r||!e||!event)return CT_INVALID;
    if(!r->owns_session)return CT_AUTHORITY;
    if(r->token||r->ledger.open)return CT_BUSY;
    /* No cognition anchors or retired persistence operations in this assay. */
    if(event[1]||!(event[0]==2||event[0]==3||event[0]==4||event[0]==14))return CT_INVALID;
    return elpis_ecs_c_session_transition(r->session,e,event,NULL);
}
int ct_begin(ct_runtime *r,const eve_coordinate *e,uint64_t *out){
    if(!r||!out)return CT_INVALID;
    if(r->token)return CT_BUSY;
    int rc=tb_charge(r,(ct_turn_budget){.v={[TB_TX]=1}});if(rc)return rc;
    rc=current(r,e);if(rc)return rc;
    uint64_t t;rc=eve_begin(r->evidence,e,&t);if(rc)return rc;
    unsigned j=r->live^1u;
    if(!ct_gds_copy(r->state[j],r->state[r->live])||!ct_cgp_copy(r->pool[j],r->pool[r->live])){(void)eve_abort(r->evidence,t);return CT_INVARIANT;}
    r->borrowed_pin=e->session;r->token=t;r->failed=0;r->mode=0;*out=t;return 0;
}
static int active(ct_runtime *r,uint64_t t){
    if(!r)return CT_INVALID;
    if(!t||t!=r->token)return CT_TOKEN;
#if !defined(CR5_REGRESSION_ALLOW_UNMETERED)
    if(!r->ledger.open){r->failed=1;return CT_FUEL;}
#endif
    if(r->failed)return CT_POISONED;
    if(!r->owns_session){
        elpis_ecs_c_session_coordinate c;int rc=elpis_ecs_c_session_read_coordinate(r->session,&c);
        if(!rc&&(c.instance!=r->borrowed_pin.instance||c.generation!=r->borrowed_pin.generation||memcmp(c.session,r->borrowed_pin.session,32)||memcmp(c.state_root,r->borrowed_pin.state_root,32)))rc=ELPIS_ECS_C_STALE;
        if(rc){r->failed=1;return rc;}
    }
    return 0;
}
static int poison(ct_runtime *r,int rc){if(rc)r->failed=1;return rc;}
int ct_enroll(ct_runtime *r,uint64_t t,uint32_t code,const double *row,const double *initial,const eve_record *rec){
    int rc=active(r,t);if(rc)return rc;
    if(r->mode>=2)return poison(r,CT_MODE);
    r->mode=1;
    rc=tb_admit(r,rec);if(rc)return poison(r,rc);
    if(!row||!initial||!rec)return poison(r,CT_INVALID);
    unsigned j=r->live^1u;uint32_t vertex;gds_handle g;cgp_handle c;eve_locator loc;
    rc=gd_resolve_code(r->index,code,&vertex);if(rc)return poison(r,rc);
    rc=gds_acquire(r->state[j],vertex,&g);if(rc)return poison(r,rc);
    rc=gds_commit(r->state[j],&g,row,1,r->width);if(rc)return poison(r,rc);
    rc=cgp_acquire(r->pool[j],vertex,initial,&c);if(rc)return poison(r,rc);
    cb_view v=view(r,j);rc=cb_locator(&v,code,&loc);if(rc)return poison(r,rc);
    return poison(r,cb_admit(&v,t,rec,&loc));
}
int ct_attach(ct_runtime *r,uint64_t t,uint32_t code,const eve_record *rec){
    int rc=active(r,t);if(rc)return rc;
    if(r->mode>=2)return poison(r,CT_MODE);
    r->mode=1;
    rc=tb_admit(r,rec);if(rc)return poison(r,rc);
    cb_view v=view(r,r->live^1u);eve_locator l;rc=cb_locator(&v,code,&l);if(rc)return poison(r,rc);
    return poison(r,cb_admit(&v,t,rec,&l));
}
_Static_assert(sizeof(double)==8 && DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 && FLT_RADIX==2,"binary64 required");
int ct_support_digest(const double *x,const double *y,uint8_t out[32]){
    if(!x||!y||!out)return CT_INVALID;
    for(unsigned i=0;i<CGR_SUPPORT;i++)if(x[i*CGR_INPUTS+4]!=1.0)return CT_INVALID;
    static const char domain[]="elpis.cgc.r97w.support.v1";
    elpis_sha256_ctx h;elpis_sha256_init(&h);elpis_sha256_update(&h,domain,sizeof domain-1);
    for(unsigned b=0;b<2;b++){
        const double *p=b?y:x;unsigned n=CGR_SUPPORT*(b?CGR_OUTPUTS:CGR_INPUTS);
        for(unsigned i=0;i<n;i++){
            if(!isfinite(p[i]))return CGR_NONFINITE;
            uint64_t bits;uint8_t le[8];memcpy(&bits,p+i,8);
            for(unsigned j=0;j<8;j++)le[j]=(uint8_t)(bits>>(8*j));
            elpis_sha256_update(&h,le,8);
        }
    }
    uint8_t digest[32];elpis_sha256_final(&h,digest);memcpy(out,digest,32);return 0;
}
int ct_adapt(ct_runtime *r,uint64_t t,uint32_t code,const eve_key *key,const uint8_t id[32],const double *x,const double *y){
    int rc=active(r,t);if(rc)return rc;
    if(r->mode)return poison(r,CT_MODE);
    if(!key||!id||!x||!y)return poison(r,CT_INVALID);
    rc=tb_charge(r,(ct_turn_budget){.v={[TB_EPISODES]=1,[TB_ROWS]=CGR_SUPPORT,[TB_STEPS]=CGR_STEPS}});if(rc)return poison(r,rc);
    uint8_t digest[32];rc=ct_support_digest(x,y,digest);if(rc)return poison(r,rc);
    cb_view live=view(r,r->live),stage=view(r,r->live^1u);
    eve_coordinate c;eve_locator old,next;eve_answer a;
    rc=eve_coordinate_read(r->evidence,&c);if(rc)return poison(r,rc);
    rc=cb_locator(&live,code,&old);if(rc)return poison(r,rc);
    rc=cb_lookup(&live,&c,key,&a);if(rc)return poison(r,rc);
    if(!a.records||a.distinct_conflict||memcmp(a.target,digest,32))return poison(r,CT_AUTHORITY);
    unsigned found=0;
    for(uint32_t offset=0;offset<a.locators;){
        eve_member page[16];uint32_t n=0,limit=a.locators-offset;if(limit>16)limit=16;
        rc=eve_page(r->evidence,&c,key,offset,limit,page,&n);if(rc)return poison(r,rc);
        if(n!=limit)return poison(r,CT_INVARIANT);
        for(uint32_t j=0;j<n;j++)if(page[j].locator.vertex==old.vertex&&!memcmp(page[j].record.id,id,32))found++;
        offset+=n;
    }
    if(found!=1)return poison(r,CT_AUTHORITY);
    rc=cb_validate(&stage,&old);if(rc)return poison(r,rc);
    cgp_handle handle;rc=cgp_handle_of(stage.pool,old.vertex,&handle);if(rc)return poison(r,rc);
    rc=cgp_begin(r->pool[r->live^1u],&handle);if(rc)return poison(r,rc);
    rc=cgp_observe(r->pool[r->live^1u],&handle,t,x,y);if(rc)return poison(r,rc);
    for(unsigned i=0;i<CGR_STEPS;i++){
        rc=cgp_propose_update(r->pool[r->live^1u],&handle);if(rc)return poison(r,rc);
        rc=cgp_learn(r->pool[r->live^1u],&handle);if(rc)return poison(r,rc);
    }
    rc=cgp_consolidate(r->pool[r->live^1u],&handle);if(rc)return poison(r,rc);
    rc=cgp_reset_fast(r->pool[r->live^1u],&handle);if(rc)return poison(r,rc);
    rc=cgp_commit(r->pool[r->live^1u],&handle);if(rc)return poison(r,rc);
    rc=cb_locator(&stage,code,&next);if(rc)return poison(r,rc);
    rc=ct_eve_rebind(r->evidence,t,&old,&next);if(rc)return poison(r,rc);
    r->mode=2;return 0;
}
typedef struct {const cgp_pool *pool;uint32_t mode;} ct_transport_context;
static int ct_message(void *opaque,uint32_t arc,uint32_t u,uint32_t v,const double *row,uint32_t w,double *out){
    (void)arc;(void)v;
    const ct_transport_context *ctx=opaque;
    if(w!=3)return CT_INVALID;
    if(ctx->mode==CT_TRANSPORT_IDENTITY){memcpy(out,row,3*sizeof(double));return 0;}
    cgp_handle h;int rc=cgp_handle_of(ctx->pool,u,&h);if(rc)return rc;
    const double x[5]={row[0],row[1],row[2],0.0,1.0};
    return cgp_query(ctx->pool,&h,CGR_SLOW,x,1,out);
}
static int ct_inbox(void *opaque,uint32_t vertex,const double *old,const gsc_message *messages,uint32_t n,uint32_t w,double *out){
    (void)opaque;(void)vertex;(void)old;
    if(!n||w!=3)return CT_INVALID;
    for(uint32_t j=0;j<w;j++){double sum=0.0;for(uint32_t i=0;i<n;i++)sum+=messages[i].row[j];out[j]=sum/(double)n;}
    return 0;
}
int ct_propagate(ct_runtime *r,uint64_t t,const uint32_t *codes,uint32_t n,
                 const uint32_t *arcs,uint32_t m,const uint32_t *seeds,uint32_t ns,
                 gsc_limits limits,uint32_t mode,gsc_stats *out){
    int rc=active(r,t);if(rc)return rc;
    if(r->mode && (r->mode!=2 || mode!=CT_TRANSPORT_CGC))return poison(r,CT_MODE);
    if(!codes||!seeds||!out||!n||n>GSC_MAX_ENROLLED||!ns||ns>n||m>6*n||(!arcs&&m)||r->width!=3||mode>CT_TRANSPORT_CGC)return poison(r,CT_INVALID);
    if(r->ledger.open){
        if(!limits.max_active||limits.max_active>GSC_MAX_ENROLLED||!limits.max_rounds||limits.max_rounds>GSC_MAX_ROUNDS||!limits.max_visits||limits.max_visits>GSC_MAX_VISITS)return poison(r,CT_FUEL);
        rc=tb_charge(r,(ct_turn_budget){.v={[TB_PANEL]=n,[TB_ARCS]=m,[TB_SEEDS]=ns,[TB_ROUNDS]=limits.max_rounds,[TB_VISITS]=limits.max_visits,[TB_ACTIVE_ROUNDS]=(uint64_t)limits.max_active*limits.max_rounds}});if(rc)return poison(r,rc);
    }
    unsigned j=r->live^1u;cb_view v=view(r,j);
    gds_handle hs[GSC_MAX_ENROLLED];uint32_t vertices[GSC_MAX_ENROLLED];
    for(uint32_t i=0;i<n;i++){
        eve_locator l;rc=cb_locator(&v,codes[i],&l);if(rc)return poison(r,rc);
        rc=gds_handle_of(v.state,l.vertex,&hs[i]);if(rc)return poison(r,rc);
    }
    for(uint32_t i=0;i<ns;i++){rc=gd_resolve_code(r->index,seeds[i],&vertices[i]);if(rc)return poison(r,rc);}
    gsc_scheduler *s=NULL;rc=gsc_workspace_bind(r->transport_workspace,r->state[j],r->index,hs,n,arcs,m,limits,&s);if(rc)return poison(r,rc);
    rc=gsc_start(s,vertices,ns);if(rc)goto done;
    ct_transport_context ctx={v.pool,mode};gsc_stats result;
    for(uint32_t i=0;i<limits.max_rounds;i++){
        gsc_round round;rc=gsc_step(s,ct_message,ct_inbox,&ctx,&round);if(rc)goto done;
        if(round.status==GSC_ACTIVE_BUDGET||round.status==GSC_ARC_BUDGET){rc=CT_FUEL;goto done;}
        if(round.status==GSC_QUIESCENT)break;
        if(round.status!=GSC_RUNNING){rc=CT_INVARIANT;goto done;}
    }
    rc=gsc_inspect(s,&result);if(rc)goto done;
done:{gsc_rc clear=gsc_workspace_clear(r->transport_workspace);if(clear&&!rc)rc=CT_INVARIANT;}
    if(rc)return poison(r,rc);
    r->mode=(r->mode==2)?4:3;*out=result;return 0;
}
int ct_commit(ct_runtime *r,uint64_t t,eve_receipt *out){
    int rc=active(r,t);if(rc)return rc;if(!out)return poison(r,CT_INVALID);
    /* All staging work is done, no external access or concurrent callbacks.
     * Evidence commit is the last fallible call. Nothing after it can refuse. */
    eve_receipt receipt;rc=eve_commit(r->evidence,t,&receipt);if(rc)return poison(r,rc);
    r->live^=1u;r->token=0;r->failed=0;r->mode=0;*out=receipt;return 0;
}
int ct_abort(ct_runtime *r,uint64_t t){
    if(!r||!t||r->token!=t)return CT_TOKEN;
    int rc=eve_abort(r->evidence,t);if(rc)return rc;
    r->token=0;r->failed=0;r->mode=0;return 0;
}
int ct_lookup(const ct_runtime *r,const eve_coordinate *e,const eve_key *k,eve_answer *out){if(!r)return CT_INVALID;int rc=tb_charge(r,(ct_turn_budget){.v={[TB_READS]=1}});if(rc)return rc;cb_view v=view(r,r->live);return cb_lookup(&v,e,k,out);}
int ct_read(const ct_runtime *r,const eve_coordinate *e,uint32_t code,double *row,uint32_t width,double *slow,double *fast,eve_locator *loc){
    if(!r||!row||!slow||!fast||!loc||width!=r->width)return CT_INVALID;
    int rc=tb_charge(r,(ct_turn_budget){.v={[TB_READS]=1}});if(rc)return rc;
    rc=current(r,e);if(rc)return rc;
    cb_view v=view(r,r->live);eve_locator l;rc=cb_locator(&v,code,&l);if(rc)return rc;
    gds_handle g; cgp_handle c;double tmp[GDS_MAX_WIDTH],s[CGR_PARAMS],f[CGR_PARAMS];
    rc=gds_handle_of(v.state,l.vertex,&g);if(rc)return rc;rc=cgp_handle_of(v.pool,l.vertex,&c);if(rc)return rc;
    rc=gds_read(v.state,&g,tmp,width);if(rc)return rc;rc=cgp_copy_bank(v.pool,&c,CGR_SLOW,s);if(rc)return rc;rc=cgp_copy_bank(v.pool,&c,CGR_FAST,f);if(rc)return rc;
    memcpy(row,tmp,width*sizeof(double));memcpy(slow,s,sizeof s);memcpy(fast,f,sizeof f);*loc=l;return 0;
}
