/* SPDX-License-Identifier: Apache-2.0
 * Algorithm port: Geodome/geodome_index.py and GEO144K/g2b_bridge.py. */
#include "internal.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
static uint32_t lower32(const uint32_t *a,uint32_t n,uint32_t x){
    uint32_t l=0,r=n;while(l<r){uint32_t m=l+(r-l)/2;if(a[m]<x)l=m+1;else r=m;}return l;
}
static uint32_t lower64(const uint64_t *a,uint32_t n,uint64_t x){
    uint32_t l=0,r=n;while(l<r){uint32_t m=l+(r-l)/2;if(a[m]<x)l=m+1;else r=m;}return l;
}
gd_status gd_build_index(gd_index *g){
    uint32_t *queue=malloc(GD_VERTICES*sizeof(*queue));
    if(!queue)return GD_ALLOC;
    gd_status rc=GD_INVARIANT;
    for(uint32_t i=0;i<GD_VERTICES;i++)g->codes[i]=GD_NONE;
    for(uint32_t i=0;i<GD_CAPACITY;i++)g->inverse[i]=GD_NONE;
    for(uint32_t i=0;i<GD_EDGES;i++){
        uint32_t u=(uint32_t)(g->edges[i]>>GD_SHIFT),v=(uint32_t)(g->edges[i]&GD_MASK);
        if(u>=v||v>=GD_VERTICES||g->degrees[u]>=6||g->degrees[v]>=6)goto done;
        g->neighbors[6u*u+g->degrees[u]++]=v;
        g->neighbors[6u*v+g->degrees[v]++]=u;
    }
    for(uint32_t v=0;v<GD_VERTICES;v++){
        if(g->degrees[v]!=(v<12?5:6))goto done;
        /* Sorted canonical edges give each vertex ascending neighbors. */
        for(uint32_t j=1;j<g->degrees[v];j++)if(g->neighbors[6u*v+j-1]>=g->neighbors[6u*v+j])goto done;
    }
    queue[0]=0;g->codes[0]=0;uint32_t tail=1;
    for(uint32_t head=0;head<tail;head++){
        uint32_t v=queue[head];
        for(uint32_t j=0;j<g->degrees[v];j++){
            uint32_t u=g->neighbors[6u*v+j];
            if(g->codes[u]==GD_NONE){if(tail>=GD_VERTICES)goto done;g->codes[u]=0;queue[tail++]=u;}
        }
    }
    if(tail!=GD_VERTICES)goto done;
    for(uint32_t rank=0;rank<GD_VERTICES;rank++){
        uint32_t c=gd_rank_code(rank),v=queue[rank];
        if(c>=GD_CAPACITY||g->inverse[c]!=GD_NONE||(rank&&g->sorted[rank-1]>=c))goto done;
        g->codes[v]=c;g->inverse[c]=v;g->sorted[rank]=c;
    }
    rc=GD_OK;
done:free(queue);return rc;
}
/* Canonical little-endian pair encoding, independent of host endianness. */
static void hash_pair(elpis_sha256_ctx *ctx,uint32_t a,uint32_t b){
    uint8_t bytes[8];
    for(unsigned i=0;i<4;i++){bytes[i]=(uint8_t)(a>>(8u*i));bytes[4u+i]=(uint8_t)(b>>(8u*i));}
    elpis_sha256_update(ctx,bytes,sizeof bytes);
}
static int gd_identity(const gd_index *g){
    elpis_sha256_ctx ctx; uint8_t digest[32]; char hex[65];
    elpis_sha256_init(&ctx);
    for(uint32_t v=0;v<GD_VERTICES;v++)hash_pair(&ctx,v,g->codes[v]);
    elpis_sha256_final(&ctx,digest);elpis_hex32(digest,hex);
    if(strcmp(hex,"abe96202b554608bd8f5e702b70459daaaf4ab33eb7dfd058723fd4d1724f51b"))return 0;
    elpis_sha256_init(&ctx);
    for(uint32_t i=0;i<GD_EDGES;i++)hash_pair(&ctx,(uint32_t)(g->edges[i]>>GD_SHIFT),(uint32_t)(g->edges[i]&GD_MASK));
    elpis_sha256_final(&ctx,digest);elpis_hex32(digest,hex);
    return strcmp(hex,"712a8fc3d94685aeb614456ba8c88f6df7e6c6ea8a4c19e86d4d3865ad014231")==0;
}
gd_status gd_create(gd_index **out){
    if(!out)return GD_RANGE;
    gd_index *g=calloc(1,sizeof(*g));if(!g)return GD_ALLOC;
    gd_status rc=GD_ALLOC;
    g->xyz=malloc(3u*GD_VERTICES*sizeof(*g->xyz));
    g->faces=malloc(3u*GD_FACES*sizeof(*g->faces));
    g->codes=malloc(GD_VERTICES*sizeof(*g->codes));g->inverse=malloc(GD_CAPACITY*sizeof(*g->inverse));
    g->sorted=malloc(GD_VERTICES*sizeof(*g->sorted));g->edges=malloc(GD_EDGES*sizeof(*g->edges));
    g->neighbors=malloc(6u*GD_VERTICES*sizeof(*g->neighbors));g->degrees=calloc(GD_VERTICES,1);
    if(!g->xyz||!g->faces||!g->codes||!g->inverse||!g->sorted||!g->edges||!g->neighbors||!g->degrees)goto fail;
    rc=gd_geometry(g);if(rc!=GD_OK)goto fail;
    rc=gd_build_index(g);if(rc!=GD_OK)goto fail;
    if(!gd_identity(g)){rc=GD_INVARIANT;goto fail;}
    *out=g;return GD_OK;
fail:gd_destroy(g);return rc;
}
void gd_destroy(gd_index *g){if(g){free(g->xyz);free(g->faces);free(g->codes);free(g->inverse);free(g->sorted);free(g->edges);free(g->neighbors);free(g->degrees);free(g);}}
size_t gd_payload_bytes(const gd_index *g){return g?sizeof(*g)+3u*GD_VERTICES*sizeof(double)+(3u*GD_FACES+8u*GD_VERTICES+GD_CAPACITY)*sizeof(uint32_t)+GD_EDGES*sizeof(uint64_t)+GD_VERTICES:0;}
gd_status gd_vertex_code(const gd_index *g,uint32_t v,uint32_t *c){if(!g||!c||v>=GD_VERTICES)return GD_RANGE;*c=g->codes[v];return GD_OK;}
gd_status gd_resolve_code(const gd_index *g,uint32_t c,uint32_t *v){if(!g||!v||c>=GD_CAPACITY)return GD_RANGE;if(g->inverse[c]==GD_NONE)return GD_UNOCCUPIED;*v=g->inverse[c];return GD_OK;}
gd_status gd_xyz(const gd_index *g,uint32_t v,double out[3]){if(!g||!out||v>=GD_VERTICES)return GD_RANGE;memcpy(out,g->xyz+3u*v,3*sizeof(double));return GD_OK;}
gd_status gd_face(const gd_index *g,uint32_t f,uint32_t out[3]){if(!g||!out||f>=GD_FACES)return GD_RANGE;memcpy(out,g->faces+3u*f,3*sizeof(uint32_t));return GD_OK;}
gd_status gd_neighbors(const gd_index *g,uint32_t v,uint32_t out[6],uint32_t *n){if(!g||!out||!n||v>=GD_VERTICES)return GD_RANGE;memcpy(out,g->neighbors+6u*v,g->degrees[v]*sizeof(uint32_t));*n=g->degrees[v];return GD_OK;}
gd_status gd_arc_id(const gd_index *g,uint32_t u,uint32_t v,uint32_t *arc){if(!g||!arc||u>=GD_VERTICES||v>=GD_VERTICES)return GD_RANGE;if(u==v)return GD_NONEDGE;uint64_t e=gd_edge(u,v);uint32_t i=lower64(g->edges,GD_EDGES,e);if(i==GD_EDGES||g->edges[i]!=e)return GD_NONEDGE;*arc=2u*i+(u>v);return GD_OK;}
gd_status gd_arc_endpoints(const gd_index *g,uint32_t arc,uint32_t *u,uint32_t *v){if(!g||!u||!v||u==v||arc>=GD_ARCS)return GD_RANGE;uint64_t e=g->edges[arc/2];uint32_t a=(uint32_t)(e>>GD_SHIFT),b=(uint32_t)(e&GD_MASK);*u=arc%2?b:a;*v=arc%2?a:b;return GD_OK;}
static gd_status span(const gd_index *g,uint32_t d,uint32_t c,uint32_t *lo,uint32_t *hi){if(!g||d>GD_DEPTH||c>=gd_pow7(d))return GD_RANGE;uint32_t p=gd_pow7(GD_DEPTH-d);*lo=lower32(g->sorted,GD_VERTICES,c*p);*hi=lower32(g->sorted,GD_VERTICES,(c+1)*p);return GD_OK;}
gd_status gd_prefix_count(const gd_index *g,uint32_t d,uint32_t c,uint32_t *n){uint32_t l,h;if(!n||span(g,d,c,&l,&h)!=GD_OK)return GD_RANGE;*n=h-l;return GD_OK;}
gd_status gd_prefix_page(const gd_index *g,uint32_t d,uint32_t c,uint32_t off,uint32_t limit,uint32_t *out,uint32_t *n){uint32_t l,h;if(!out||!n||!limit||limit>GD_PAGE_MAX||span(g,d,c,&l,&h)!=GD_OK||off>h-l)return GD_RANGE;uint32_t k=h-l-off;if(k>limit)k=limit;for(uint32_t i=0;i<k;i++)out[i]=g->inverse[g->sorted[l+off+i]];*n=k;return GD_OK;}
