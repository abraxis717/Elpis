/* SPDX-License-Identifier: Apache-2.0 */
/* Single owning translation unit. Never link the sealed scheduler separately. */
#include "geodome_scheduler.c"
#include "reusable_scheduler.h"
struct gsc_workspace {gsc_scheduler s;uint32_t capacity,width,bound;};
/* In-place heapsort: canonical ordering, O(n log n), no libc allocation. */
#define SORT_IMPL(NAME,T,KEY) \
static void NAME##_sift(T *a,uint32_t n,uint32_t root){ \
    while(root<n/2){uint32_t child=2*root+1; \
        if(child+1<n&&a[child].KEY<a[child+1].KEY)child++; \
        if(a[root].KEY>=a[child].KEY)return; \
        T tmp=a[root];a[root]=a[child];a[child]=tmp;root=child;} \
} \
static void NAME(T *a,uint32_t n){ \
    for(uint32_t i=n/2;i>0;i--)NAME##_sift(a,n,i-1); \
    for(uint32_t i=n;i>1;i--){T tmp=a[0];a[0]=a[i-1];a[i-1]=tmp;NAME##_sift(a,i-1,0);} \
}
SORT_IMPL(sort_handles,gds_handle,vertex)
SORT_IMPL(sort_edges,edge,id)
#undef SORT_IMPL
void gsc_workspace_destroy(gsc_workspace *w){
    if(!w||w->s.busy)return;
    gsc_scheduler *s=&w->s;
    free(s->hs);free(s->changed);free(s->es);free(s->adj);free(s->front);
    free(s->flags);free(s->active_arc);free(s->rows);free(s->messages);free(w);
}
size_t gsc_workspace_bytes(const gsc_workspace *w){return w?w->s.payload:0;}
gsc_rc gsc_workspace_reserve(uint32_t capacity,uint32_t width,gsc_workspace **out){
    if(!out||!capacity||capacity>GSC_MAX_ENROLLED||!width||width>GDS_MAX_WIDTH)return GSC_RANGE;
    size_t n=capacity,m=6*n;
    size_t payload=sizeof(gsc_workspace)+2*n*sizeof(gds_handle)+m*sizeof(edge)+n*sizeof(links)+n*sizeof(uint32_t)+n+m+(n+m)*width*sizeof(double);
    if(payload>GSC_PAYLOAD_LIMIT)return GSC_RANGE;
    gsc_workspace *w=calloc(1,sizeof *w);if(!w)return GSC_ALLOC;
    gsc_scheduler *s=&w->s;w->capacity=capacity;w->width=width;s->payload=payload;
    s->hs=malloc(n*sizeof(*s->hs));s->changed=malloc(n*sizeof(*s->changed));s->es=malloc(m*sizeof(*s->es));
    s->adj=malloc(n*sizeof(*s->adj));s->front=malloc(n*sizeof(*s->front));s->flags=malloc(n);s->active_arc=malloc(m);
    s->rows=malloc(n*width*sizeof(double));s->messages=malloc(m*width*sizeof(double));
    if(!s->hs||!s->changed||!s->es||!s->adj||!s->front||!s->flags||!s->active_arc||!s->rows||!s->messages){gsc_workspace_destroy(w);return GSC_ALLOC;}
    *out=w;return GSC_OK;
}
gsc_rc gsc_workspace_clear(gsc_workspace *w){
    if(!w)return GSC_RANGE;
    if(w->s.busy)return GSC_SESSION;
    gsc_scheduler *s=&w->s;w->bound=0;s->state=NULL;s->epoch=0;s->n=s->m=s->w=s->precision=0;
    s->lim=(gsc_limits){0};s->status=GSC_NEW;s->rounds=s->visits=s->nfront=0;
    return GSC_OK;
}
gsc_rc gsc_workspace_bind(gsc_workspace *w,gds_state *st,const gd_index *idx,const gds_handle *hs,uint32_t n,const uint32_t *arcs,uint32_t m,gsc_limits lim,gsc_scheduler **out){
    if(!w||!st||!idx||!hs||!out||!n||n>w->capacity||m>GSC_MAX_ARCS||(!arcs&&m)||!lim.max_active||lim.max_active>GDS_MAX_BATCH||!lim.max_rounds||lim.max_rounds>GSC_MAX_ROUNDS||!lim.max_visits||lim.max_visits>GSC_MAX_VISITS)return GSC_RANGE;
    if(w->bound||w->s.busy)return GSC_SESSION;
    if(m>6*n)return GSC_AUTHORITY;
    gds_stats stats;if(gds_inspect(st,&stats)!=GDS_OK)return GSC_INVARIANT;
    if(n>stats.resident)return GSC_AUTHORITY;
    if(stats.width!=w->width)return GSC_RANGE;
    gsc_scheduler *s=&w->s;s->state=st;s->epoch=stats.epoch;s->n=n;s->m=m;s->w=stats.width;s->precision=stats.precision;s->lim=lim;
    memset(s->adj,0,n*sizeof(*s->adj));memcpy(s->hs,hs,n*sizeof(*hs));sort_handles(s->hs,n);
    gsc_rc rc=GSC_OK;double tmp[GDS_MAX_WIDTH];
    for(uint32_t i=0;i<n;i++){
        if(i&&s->hs[i-1].vertex==s->hs[i].vertex){rc=GSC_AUTHORITY;goto fail;}
        rc=state_rc(gds_read(st,&s->hs[i],tmp,s->w));if(rc)goto fail;
    }
    for(uint32_t i=0;i<m;i++){
        uint32_t u,v;if(gd_arc_endpoints(idx,arcs[i],&u,&v)!=GD_OK){rc=GSC_AUTHORITY;goto fail;}
        u=find(s,u);v=find(s,v);if(u==GD_NONE||v==GD_NONE){rc=GSC_AUTHORITY;goto fail;}
        s->es[i]=(edge){arcs[i],u,v};
    }
    sort_edges(s->es,m);
    for(uint32_t i=0;i<m;i++){
        edge e=s->es[i];if((i&&s->es[i-1].id==e.id)||s->adj[e.u].no>=6||s->adj[e.v].ni>=6){rc=GSC_AUTHORITY;goto fail;}
        s->adj[e.u].out[s->adj[e.u].no++]=i;s->adj[e.v].in[s->adj[e.v].ni++]=i;
    }
    w->bound=1;*out=s;return GSC_OK;
fail:(void)gsc_workspace_clear(w);return rc;
}
