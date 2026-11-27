/* SPDX-License-Identifier: Apache-2.0 */
#include "elpis/geodome_scheduler.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <fenv.h>
typedef struct {uint32_t id,u,v;} edge;
typedef struct {uint32_t out[6],in[6],no,ni;} links;
struct gsc_scheduler {
    gds_state *state; uint64_t epoch; uint32_t n,m,w,precision;
    gsc_limits lim; uint32_t status,rounds,visits,nfront,busy;
    size_t payload;
    gds_handle *hs,*changed; edge *es; links *adj;
    uint32_t *front; unsigned char *flags,*active_arc;
    double *rows,*messages;
};
static int hcmp(const void *a,const void *b){uint32_t x=((const gds_handle*)a)->vertex,y=((const gds_handle*)b)->vertex;return (x>y)-(x<y);}
static int ecmp(const void *a,const void *b){uint32_t x=((const edge*)a)->id,y=((const edge*)b)->id;return (x>y)-(x<y);}
static uint32_t find(const gsc_scheduler *s,uint32_t v){uint32_t l=0,r=s->n;while(l<r){uint32_t m=l+(r-l)/2;if(s->hs[m].vertex<v)l=m+1;else r=m;}return l<s->n&&s->hs[l].vertex==v?l:GD_NONE;}
static gsc_rc state_rc(gds_status rc){switch(rc){case GDS_OK:return GSC_OK;case GDS_STALE:case GDS_NONRESIDENT:return GSC_STALE;case GDS_NONFINITE:return GSC_NONFINITE;case GDS_FP_ENV:return GSC_FP_ENV;default:return GSC_INVARIANT;}}
void gsc_destroy(gsc_scheduler *s){if(s){if(s->busy)return;free(s->hs);free(s->changed);free(s->es);free(s->adj);free(s->front);free(s->flags);free(s->active_arc);free(s->rows);free(s->messages);free(s);}}
gsc_rc gsc_create(gds_state *st,const gd_index *idx,const gds_handle *hs,uint32_t n,const uint32_t *arcs,uint32_t m,gsc_limits lim,gsc_scheduler **out){
    if(!st||!idx||!hs||!out||!n||n>GSC_MAX_ENROLLED||m>GSC_MAX_ARCS||(!arcs&&m)||!lim.max_active||lim.max_active>GDS_MAX_BATCH||!lim.max_rounds||lim.max_rounds>GSC_MAX_ROUNDS||!lim.max_visits||lim.max_visits>GSC_MAX_VISITS)return GSC_RANGE;
    if(m>6*n)return GSC_AUTHORITY;
    gds_stats stats;if(gds_inspect(st,&stats)!=GDS_OK)return GSC_INVARIANT;
    if(n>stats.resident)return GSC_AUTHORITY;
    size_t payload=sizeof(gsc_scheduler)+2*(size_t)n*sizeof(gds_handle)+(size_t)m*sizeof(edge)+(size_t)n*sizeof(links)+(size_t)n*sizeof(uint32_t)+n+(m?m:1)+((size_t)n*stats.width+(m?(size_t)m*stats.width:1))*sizeof(double);
    if(!m)payload+=sizeof(edge); /* one sentinel allocation */
    if(payload>GSC_PAYLOAD_LIMIT)return GSC_RANGE;
    gsc_scheduler *s=calloc(1,sizeof(*s));if(!s)return GSC_ALLOC;
    s->state=st;s->epoch=stats.epoch;s->n=n;s->m=m;s->w=stats.width;s->precision=stats.precision;s->lim=lim;s->payload=payload;
    s->hs=malloc(n*sizeof(*s->hs));s->changed=malloc(n*sizeof(*s->changed));s->es=malloc((m?m:1)*sizeof(*s->es));s->adj=calloc(n,sizeof(*s->adj));s->front=malloc(n*sizeof(*s->front));s->flags=calloc(n,1);s->active_arc=calloc(m?m:1,1);s->rows=malloc((size_t)n*s->w*sizeof(double));s->messages=malloc((m?(size_t)m*s->w:1)*sizeof(double));
    if(!s->hs||!s->changed||!s->es||!s->adj||!s->front||!s->flags||!s->active_arc||!s->rows||!s->messages){gsc_destroy(s);return GSC_ALLOC;}
    memcpy(s->hs,hs,n*sizeof(*hs));qsort(s->hs,n,sizeof(*hs),hcmp);
    double tmp[GDS_MAX_WIDTH];
    for(uint32_t i=0;i<n;i++){if(i&&s->hs[i-1].vertex==s->hs[i].vertex){gsc_destroy(s);return GSC_AUTHORITY;}gsc_rc rc=state_rc(gds_read(st,&s->hs[i],tmp,s->w));if(rc){gsc_destroy(s);return rc;}}
    for(uint32_t i=0;i<m;i++){uint32_t u,v;if(gd_arc_endpoints(idx,arcs[i],&u,&v)!=GD_OK){gsc_destroy(s);return GSC_AUTHORITY;}u=find(s,u);v=find(s,v);if(u==GD_NONE||v==GD_NONE){gsc_destroy(s);return GSC_AUTHORITY;}s->es[i]=(edge){arcs[i],u,v};}
    qsort(s->es,m,sizeof(*s->es),ecmp);
    for(uint32_t i=0;i<m;i++){edge e=s->es[i];if((i&&s->es[i-1].id==e.id)||s->adj[e.u].no>=6||s->adj[e.v].ni>=6){gsc_destroy(s);return GSC_AUTHORITY;}s->adj[e.u].out[s->adj[e.u].no++]=i;s->adj[e.v].in[s->adj[e.v].ni++]=i;}
    *out=s;return GSC_OK;
}
static int epoch_ok(const gsc_scheduler *s){gds_stats st;return gds_inspect(s->state,&st)==GDS_OK&&st.epoch==s->epoch;}
gsc_rc gsc_inspect(const gsc_scheduler *s,gsc_stats *out){if(!s||!out)return GSC_RANGE;*out=(gsc_stats){s->status,s->rounds,s->visits,s->nfront,s->n,s->m,s->payload};return GSC_OK;}
gsc_rc gsc_frontier(const gsc_scheduler *s,uint32_t *out,uint32_t cap,uint32_t *count){if(!s||!count||cap<s->nfront||(!out&&s->nfront))return GSC_RANGE;for(uint32_t i=0;i<s->nfront;i++)out[i]=s->hs[s->front[i]].vertex;*count=s->nfront;return GSC_OK;}
gsc_rc gsc_start(gsc_scheduler *s,const uint32_t *vs,uint32_t n){
    if(!s||!vs||!n)return GSC_RANGE;
    if(s->busy||s->status!=GSC_NEW||!epoch_ok(s))return GSC_SESSION;
    if(n>s->lim.max_active||n>s->n)return GSC_RANGE;
    memset(s->flags,0,s->n);double tmp[GDS_MAX_WIDTH];
    for(uint32_t i=0;i<n;i++){uint32_t j=find(s,vs[i]);if(j==GD_NONE||s->flags[j])return GSC_AUTHORITY;gsc_rc rc=state_rc(gds_read(s->state,&s->hs[j],tmp,s->w));if(rc)return rc;s->flags[j]=1;}
    for(uint32_t i=0;i<s->n;i++)if(s->flags[i])s->front[s->nfront++]=i;
    s->status=GSC_RUNNING;return GSC_OK;
}
static gsc_rc quantize(const gsc_scheduler *s,double *row){
    if(s->precision==GDS_F32&&fegetround()!=FE_TONEAREST)return GSC_FP_ENV;
    for(uint32_t j=0;j<s->w;j++){double x=row[j];if(!isfinite(x))return GSC_NONFINITE;if(s->precision==GDS_F32){if(fabs(x)>=0x1.ffffffp127)return GSC_NONFINITE;float f=fabs(x)>FLT_MAX?(signbit(x)?-FLT_MAX:FLT_MAX):(float)x;row[j]=(double)f;}}
    return GSC_OK;
}
static gsc_rc stop(gsc_scheduler *s,gsc_round *out,uint32_t status){s->status=status;*out=(gsc_round){status,s->nfront,0,0,0,0};return GSC_OK;}
gsc_rc gsc_step(gsc_scheduler *s,gsc_transport transport,gsc_update update,void *ctx,gsc_round *out){
    if(!s||!transport||!update||!out)return GSC_RANGE;
    if(s->busy||s->status!=GSC_RUNNING||!epoch_ok(s))return GSC_SESSION;
    uint32_t ns=s->nfront,nd=0,na=0,nt=0,nc=0;
    if(s->rounds>=s->lim.max_rounds)return stop(s,out,GSC_ROUND_BUDGET);
    memset(s->flags,0,s->n);memset(s->active_arc,0,s->m);
    for(uint32_t i=0;i<ns;i++){uint32_t u=s->front[i];s->flags[u]|=1;for(uint32_t j=0;j<s->adj[u].no;j++){uint32_t a=s->adj[u].out[j];s->active_arc[a]=1;s->flags[s->es[a].v]|=2;na++;}}
    for(uint32_t i=0;i<s->n;i++){nt+=(s->flags[i]!=0);nd+=((s->flags[i]&2)!=0);}
    if(nt>s->lim.max_active)return stop(s,out,GSC_ACTIVE_BUDGET);
    if(na>s->lim.max_visits-s->visits)return stop(s,out,GSC_ARC_BUDGET);
    gsc_rc rc=GSC_OK;s->busy=1;
    for(uint32_t i=0;i<s->n;i++)if(s->flags[i]){rc=state_rc(gds_read(s->state,&s->hs[i],s->rows+(size_t)i*s->w,s->w));if(rc)goto done;}
    for(uint32_t i=0;i<ns;i++){uint32_t u=s->front[i];for(uint32_t j=0;j<s->adj[u].no;j++){uint32_t a=s->adj[u].out[j];edge e=s->es[a];double *msg=s->messages+(size_t)a*s->w;for(uint32_t k=0;k<s->w;k++)msg[k]=NAN;if(transport(ctx,e.id,s->hs[u].vertex,s->hs[e.v].vertex,s->rows+(size_t)u*s->w,s->w,msg)){rc=GSC_CALLBACK;goto done;}rc=quantize(s,msg);if(rc)goto done;}}
    for(uint32_t v=0;v<s->n;v++)if(s->flags[v]&2){gsc_message inbox[6];uint32_t nm=0;double tmp[GDS_MAX_WIDTH];for(uint32_t j=0;j<s->adj[v].ni;j++){uint32_t a=s->adj[v].in[j];if(s->active_arc[a])inbox[nm++]=(gsc_message){s->es[a].id,s->messages+(size_t)a*s->w};}double *old=s->rows+(size_t)v*s->w;for(uint32_t j=0;j<s->w;j++)tmp[j]=NAN;if(update(ctx,s->hs[v].vertex,old,inbox,nm,s->w,tmp)){rc=GSC_CALLBACK;goto done;}rc=quantize(s,tmp);if(rc)goto done;int diff=0;for(uint32_t j=0;j<s->w;j++)diff|=tmp[j]!=old[j];if(diff){/* Transport complete. Ascending destinations imply nc<=v: compaction cannot clobber a future old row. */memcpy(s->rows+(size_t)nc*s->w,tmp,s->w*sizeof(double));s->changed[nc++]=s->hs[v];}}
    if(nc){rc=state_rc(gds_commit(s->state,s->changed,s->rows,nc,s->w));if(rc)goto done;}
    for(uint32_t i=0;i<nc;i++)s->front[i]=find(s,s->changed[i].vertex);
    s->nfront=nc;s->rounds++;s->visits+=na;s->status=nc?GSC_RUNNING:GSC_QUIESCENT;*out=(gsc_round){s->status,ns,na,nd,nc,nt};
done:s->busy=0;return rc;
}
