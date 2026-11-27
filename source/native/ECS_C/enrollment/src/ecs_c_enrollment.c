#include "elpis/ecs_c_enrollment.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <stdatomic.h>
#include <string.h>

#define OK ELPIS_ECS_C_OK
#define INVALID ELPIS_ECS_C_INVALID
#define STALE ELPIS_ECS_C_STALE
#define CAPACITY ELPIS_ECS_C_CAPACITY
#define EXHAUSTED ELPIS_ECS_C_EXHAUSTED
#define DUP ELPIS_ECS_C_DUPLICATE
#define MISMATCH ELPIS_ECS_C_SESSION_MISMATCH

typedef struct { uint32_t record_plus_one; eve_locator locator; } link_row;
typedef struct { eve_record *records; link_row *links; uint32_t nr,nl; } bank;
struct eve_store {
    elpis_ecs_c_session *session;
    elpis_ecs_c_session_coordinate identity, pinned;
    uint64_t revision, instance, active;
    uint32_t rc,lc,charges;
    size_t bytes;
    bank committed, staged;
    uint8_t charge[EVE_MAX_ADMISSIONS][32];
};
/* Instance and transaction identities share one saturating process-local
 * counter. Explicit create/begin only; not a durable sequence or authority. */
static _Atomic uint64_t next_identity=0;
static int reserve_identity(uint64_t *out) {
    uint64_t old=atomic_load_explicit(&next_identity,memory_order_relaxed);
    do { if(old==UINT64_MAX)return EXHAUSTED; }
    while(!atomic_compare_exchange_weak_explicit(&next_identity,&old,old+1,memory_order_relaxed,memory_order_relaxed));
    *out=old+1;return OK;
}
static int nonzero(const uint8_t p[32]) { uint8_t x=0; for(unsigned i=0;i<32;i++) x|=p[i]; return x!=0; }
static int same32(const uint8_t a[32], const uint8_t b[32]) { return memcmp(a,b,32)==0; }
static int same_key(const eve_key *a,const eve_key *b) {
    return same32(a->source,b->source)&&same32(a->relation,b->relation)&&same32(a->scope,b->scope);
}
static int valid_key(const eve_key *k) { return k&&nonzero(k->source)&&nonzero(k->relation); }
static int same_locator(const eve_locator *a,const eve_locator *b) {
    return a->state_owner==b->state_owner&&a->state_epoch==b->state_epoch&&a->state_generation==b->state_generation&&
        a->cell_owner==b->cell_owner&&a->cell_epoch==b->cell_epoch&&a->cell_generation==b->cell_generation&&
        a->cell_revision==b->cell_revision&&a->vertex==b->vertex&&a->state_slot==b->state_slot&&
        a->cell_slot==b->cell_slot&&a->cell_key==b->cell_key;
}
static int valid_locator(const eve_locator *l) {
    return l&&l->state_owner&&l->state_generation&&l->cell_owner&&l->cell_generation&&
        l->vertex<144002u&&l->state_slot<1024u&&l->cell_slot<1024u;
}
int eve_record_id(const eve_record *r,uint8_t out[32]) {
    if(!r||!out||!valid_key(&r->key)||!r->source_version||!nonzero(r->target)||!nonzero(r->provenance))return INVALID;
    static const char domain[]="elpis.ecsc.functional-evidence.v1";
    uint8_t le[8];for(unsigned i=0;i<8;i++)le[i]=(uint8_t)(r->source_version>>(8*i));
    elpis_sha256_ctx h;elpis_sha256_init(&h);elpis_sha256_update(&h,domain,sizeof domain-1);
    elpis_sha256_update(&h,r->key.source,32);elpis_sha256_update(&h,r->key.relation,32);elpis_sha256_update(&h,r->key.scope,32);
    elpis_sha256_update(&h,le,8);elpis_sha256_update(&h,r->target,32);elpis_sha256_update(&h,r->provenance,32);elpis_sha256_final(&h,out);return OK;
}
static int same_session(const elpis_ecs_c_session_coordinate *a,const elpis_ecs_c_session_coordinate *b) {
    return a->instance==b->instance&&same32(a->session,b->session);
}
static int same_coord(const elpis_ecs_c_session_coordinate *a,const elpis_ecs_c_session_coordinate *b) {
    return same_session(a,b)&&a->generation==b->generation&&same32(a->state_root,b->state_root);
}
static int now(const eve_store *s,elpis_ecs_c_session_coordinate *out) {
    if(!s||!out)return INVALID;
    int rc=elpis_ecs_c_session_read_coordinate(s->session,out);if(rc)return rc;
    return same_session(&s->identity,out)?OK:MISMATCH;
}
static int expected_ok(const eve_store *s,const eve_coordinate *e) {
    if(!s||!e)return INVALID;
    elpis_ecs_c_session_coordinate c;int rc=now(s,&c);if(rc)return rc;
    if(!same_session(&c,&e->session)||e->store_instance!=s->instance)return MISMATCH;
    return e->revision==s->revision&&same_coord(&c,&e->session)?OK:STALE;
}
static int tx_ok(const eve_store *s,uint64_t t) {
    if(!s)return INVALID;
    if(!t||t!=s->active)return EVE_TX_STATE;
    elpis_ecs_c_session_coordinate c;int rc=now(s,&c);if(rc)return rc;
    return same_coord(&c,&s->pinned)?OK:STALE;
}
int eve_create(elpis_ecs_c_session *session,uint32_t rc,uint32_t lc,eve_store **out) {
    if(!session||!out||!rc||rc>EVE_MAX_RECORDS||!lc||lc>EVE_MAX_LINKS)return INVALID;
    elpis_ecs_c_session_coordinate c;int status=elpis_ecs_c_session_read_coordinate(session,&c);if(status)return status;
    size_t rb=(size_t)rc*sizeof(eve_record),lb=(size_t)lc*sizeof(link_row);
    size_t bytes=sizeof(eve_store)+2*(rb+lb);
    eve_store *s=calloc(1,bytes);if(!s)return ELPIS_ECS_C_NOMEM;
    status=reserve_identity(&s->instance);if(status){free(s);return status;}
    s->session=session;s->identity=c;s->rc=rc;s->lc=lc;s->bytes=bytes;
    unsigned char *p=(unsigned char *)(s+1);
    s->committed.records=(eve_record *)p;p+=rb;s->committed.links=(link_row *)p;p+=lb;
    s->staged.records=(eve_record *)p;p+=rb;s->staged.links=(link_row *)p;
    *out=s;return OK;
}
void eve_destroy(eve_store *s) { if(s){size_t n=s->bytes;volatile unsigned char *p=(volatile unsigned char *)s;while(n--)*p++=0;free(s);} }
int eve_coordinate_read(const eve_store *s,eve_coordinate *out) {
    if(!out)return INVALID;
    eve_coordinate c;int rc=now(s,&c.session);if(rc)return rc;c.store_instance=s->instance;c.revision=s->revision;*out=c;return OK;
}
int eve_inspect(const eve_store *s,eve_stats *out) {
    if(!s||!out)return INVALID;
    eve_stats r={s->rc,s->lc,s->committed.nr,s->committed.nl,s->active!=0,s->revision,s->bytes};*out=r;return OK;
}
int eve_begin(eve_store *s,const eve_coordinate *e,uint64_t *out) {
    if(!s||!out)return INVALID;
    if(s->active)return EVE_TX_STATE;
    int rc=expected_ok(s,e);if(rc)return rc;
    if(s->revision==UINT64_MAX)return EXHAUSTED;
    uint64_t token;rc=reserve_identity(&token);if(rc)return rc;
    memcpy(s->staged.records,s->committed.records,s->rc*sizeof(eve_record));
    memcpy(s->staged.links,s->committed.links,s->lc*sizeof(link_row));
    s->staged.nr=s->committed.nr;s->staged.nl=s->committed.nl;s->pinned=e->session;s->charges=0;s->active=token;*out=s->active;return OK;
}
static int record_index(const eve_store *s,const bank *b,const uint8_t id[32]) {
    for(uint32_t i=0;i<s->rc;i++)if(b->records[i].source_version&&same32(b->records[i].id,id))return (int)i;
    return -1;
}
int eve_admit(eve_store *s,uint64_t t,const eve_record *r,const eve_locator *l) {
    int rc=tx_ok(s,t);if(rc)return rc;
    uint8_t id[32];if(!valid_locator(l)||eve_record_id(r,id))return INVALID;
    if(!same32(id,r->id))return EVE_IDENTITY_CONFLICT;
    uint32_t limit=0;rc=elpis_ecs_c_session_check_evidence(s->session,r->key.source,r->source_version,r->key.scope,&limit);if(rc)return rc;
    if(s->charges==EVE_MAX_ADMISSIONS)return EVE_TURN_LIMIT;
    uint32_t n=0;for(uint32_t i=0;i<s->charges;i++)n+=(uint32_t)same32(s->charge[i],r->key.source);
    if(n>=limit)return EVE_TURN_LIMIT;
    bank *b=&s->staged;int i=record_index(s,b,r->id);int new_record=i<0;
    if(!new_record){const eve_record *old=&b->records[i];if(!same_key(&old->key,&r->key)||old->source_version!=r->source_version||!same32(old->target,r->target)||!same32(old->provenance,r->provenance))return EVE_IDENTITY_CONFLICT;}
    else { if(b->nr==s->rc)return CAPACITY;for(uint32_t j=0;j<s->rc;j++)if(!b->records[j].source_version){i=(int)j;break;} }
    if(i<0)return ELPIS_ECS_C_CORRUPT;
    int free_link=-1;
    for(uint32_t j=0;j<s->lc;j++){
        link_row *q=&b->links[j];if(!q->record_plus_one&&free_link<0)free_link=(int)j;
        if(q->record_plus_one==(uint32_t)i+1&&same_locator(&q->locator,l))return DUP;
    }
    if(free_link<0)return CAPACITY;
    if(new_record){b->records[i]=*r;b->nr++;}
    b->links[free_link].record_plus_one=(uint32_t)i+1;b->links[free_link].locator=*l;b->nl++;
    memcpy(s->charge[s->charges++],r->key.source,32);return OK;
}
int eve_detach(eve_store *s,uint64_t t,const uint8_t id[32],const eve_locator *l) {
    int rc=tx_ok(s,t);if(rc)return rc;if(!id||!valid_locator(l))return INVALID;
    bank *b=&s->staged;int i=record_index(s,b,id);if(i<0)return EVE_NOT_FOUND;
    int found=-1;uint32_t n=0;for(uint32_t j=0;j<s->lc;j++)if(b->links[j].record_plus_one==(uint32_t)i+1){n++;if(same_locator(&b->links[j].locator,l))found=(int)j;}
    if(found<0)return EVE_NOT_FOUND;
    if(n==1)return EVE_LAST_LOCATOR;
    memset(&b->links[found],0,sizeof(link_row));b->nl--;return OK;
}
int eve_prune(eve_store *s,uint64_t t,uint32_t *out) {
    int rc=tx_ok(s,t);if(rc)return rc;if(!out)return INVALID;
    bank *b=&s->staged;uint8_t retired[EVE_MAX_RECORDS]={0};uint32_t n=0;
    for(uint32_t i=0;i<s->rc;i++)if(b->records[i].source_version){
        elpis_ecs_c_entity e;rc=elpis_ecs_c_session_entity_find(s->session,b->records[i].key.source,&e);
        if(rc&&rc!=ELPIS_ECS_C_UNKNOWN_ENTITY)return rc;
        if(rc==ELPIS_ECS_C_UNKNOWN_ENTITY||e.lifecycle==ELPIS_ECS_C_TERMINATED||e.source_version>b->records[i].source_version){retired[i]=1;n++;}
    }
    for(uint32_t j=0;j<s->lc;j++)if(b->links[j].record_plus_one&&retired[b->links[j].record_plus_one-1]){memset(&b->links[j],0,sizeof(link_row));b->nl--;}
    for(uint32_t i=0;i<s->rc;i++)if(retired[i])memset(&b->records[i],0,sizeof(eve_record));
    b->nr-=n;*out=n;return OK;
}
int eve_reset(eve_store *s,uint64_t t) {
    int rc=tx_ok(s,t);if(rc)return rc;
    memset(s->staged.records,0,s->rc*sizeof(eve_record));memset(s->staged.links,0,s->lc*sizeof(link_row));s->staged.nr=0;s->staged.nl=0;return OK;
}
static void clear_stage(eve_store *s){memset(s->staged.records,0,s->rc*sizeof(eve_record));memset(s->staged.links,0,s->lc*sizeof(link_row));s->staged.nr=s->staged.nl=s->charges=0;memset(s->charge,0,sizeof s->charge);memset(&s->pinned,0,sizeof s->pinned);s->active=0;}
int eve_commit(eve_store *s,uint64_t t,eve_receipt *out) {
    int rc=tx_ok(s,t);if(rc)return rc;if(!out)return INVALID;
    eve_receipt receipt={{s->pinned,s->instance,s->revision+1},t};
    bank old=s->committed;s->committed=s->staged;s->staged=old;s->revision++;clear_stage(s);*out=receipt;return OK;
}
int eve_abort(eve_store *s,uint64_t t) {if(!s)return INVALID;if(!t||t!=s->active)return EVE_TX_STATE;clear_stage(s);return OK;}
/* Current authority, not the locator generation, determines source liveness. */
static int live_version(const eve_store *s,const eve_key *k,uint64_t *out) {
    elpis_ecs_c_entity e;int rc=elpis_ecs_c_session_entity_find(s->session,k->source,&e);
    if(rc==ELPIS_ECS_C_UNKNOWN_ENTITY){*out=0;return OK;}if(rc)return rc;
    uint32_t limit;rc=elpis_ecs_c_session_check_evidence(s->session,k->source,e.source_version,k->scope,&limit);
    if(rc==ELPIS_ECS_C_UNKNOWN_ENTITY||rc==ELPIS_ECS_C_UNAUTHORIZED||rc==ELPIS_ECS_C_LIFECYCLE||rc==ELPIS_ECS_C_SOURCE_STALE||rc==ELPIS_ECS_C_SCOPE_CONFLICT){*out=0;return OK;}
    if(rc)return rc;
    *out=e.source_version;return OK;
}
static int matching(const eve_record *r,const eve_key *k,uint64_t v){return v&&r->source_version==v&&same_key(&r->key,k);}
int eve_lookup(const eve_store *s,const eve_coordinate *e,const eve_key *k,eve_answer *out) {
    if(!valid_key(k)||!out)return INVALID;
    int rc=expected_ok(s,e);if(rc)return rc;
    uint64_t v;rc=live_version(s,k,&v);if(rc)return rc;
    eve_answer a={0};const bank *b=&s->committed;
    for(uint32_t i=0;i<s->rc;i++)if(matching(&b->records[i],k,v)){
        if(!a.records)memcpy(a.target,b->records[i].target,32);else if(!same32(a.target,b->records[i].target))a.distinct_conflict=1;a.records++;
    }
    for(uint32_t j=0;j<s->lc;j++)if(b->links[j].record_plus_one&&matching(&b->records[b->links[j].record_plus_one-1],k,v))a.locators++;
    if(a.distinct_conflict)memset(a.target,0,32);
    *out=a;return OK;
}
int eve_page(const eve_store *s,const eve_coordinate *e,const eve_key *k,uint32_t offset,uint32_t limit,eve_member *out,uint32_t *written) {
    if(!valid_key(k)||!out||!written||!limit||limit>EVE_MAX_PAGE)return INVALID;
    eve_answer a;int rc=eve_lookup(s,e,k,&a);if(rc)return rc;if(offset>a.locators)return INVALID;
    uint64_t v;rc=live_version(s,k,&v);if(rc)return rc;
    const bank *b=&s->committed;uint32_t seen=0,n=0;
    for(uint32_t j=0;j<s->lc&&n<limit;j++)if(b->links[j].record_plus_one){const eve_record *r=&b->records[b->links[j].record_plus_one-1];if(matching(r,k,v)&&seen++>=offset){out[n].record=*r;out[n].locator=b->links[j].locator;n++;}}
    *written=n;return OK;
}
