/* SPDX-License-Identifier: Apache-2.0
 * Algorithm port: GEO144K/g1c_compact.py and g2b_bridge.py at pinned HexaFlake. */
#include "internal.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define FREQ 120u
#define LOCAL ((FREQ+1u)*(FREQ+2u)/2u)
static const uint32_t base_faces[20][3] = {
    {0,11,5},{0,5,1},{0,1,7},{0,7,10},{0,10,11},
    {1,5,9},{5,11,4},{11,10,2},{10,7,6},{7,1,8},
    {3,9,4},{3,4,2},{3,2,6},{3,6,8},{3,8,9},
    {4,9,5},{2,4,11},{6,2,10},{8,6,7},{9,8,1}
};
static int cmp64(const void *a, const void *b) {
    uint64_t x=*(const uint64_t *)a,y=*(const uint64_t *)b;
    return (x>y)-(x<y);
}
static uint32_t row(uint32_t i) { return i*(2u*FREQ+3u-i)/2u; }
static uint32_t vertex_id(uint32_t fid, uint32_t i, uint32_t j, uint32_t k,
                          uint32_t ids[12][12]) {
    uint32_t w[3]={i,j,k}, v[3], weights[3], n=0;
    for (uint32_t t=0;t<3;t++) if (w[t]) {v[n]=base_faces[fid][t];weights[n++]=w[t];}
    if(n==1) return v[0];
    if(n==2) {
        uint32_t lo=v[0],hi=v[1],wh=weights[1];
        if(lo>hi){lo=v[1];hi=v[0];wh=weights[0];}
        return 12u+ids[lo][hi]*(FREQ-1u)+wh-1u;
    }
    return 12u+30u*(FREQ-1u)+fid*((FREQ-1u)*(FREQ-2u)/2u)
        +(i-1u)*(FREQ-1u)-(i-1u)*i/2u+j-1u;
}
static int emit(gd_index *idx, uint32_t *n, uint32_t a,uint32_t b,uint32_t c) {
    if(*n>=GD_FACES||a==b||b==c||a==c||a>=GD_VERTICES||b>=GD_VERTICES||c>=GD_VERTICES) return 0;
    const double *x=idx->xyz+3u*a,*y=idx->xyz+3u*b,*z=idx->xyz+3u*c;
    double ab[3],ac[3];
    for(unsigned t=0;t<3;t++){ab[t]=y[t]-x[t];ac[t]=z[t]-x[t];}
    double orientation=(ab[1]*ac[2]-ab[2]*ac[1])*(x[0]+y[0]+z[0])
                      +(ab[2]*ac[0]-ab[0]*ac[2])*(x[1]+y[1]+z[1])
                      +(ab[0]*ac[1]-ab[1]*ac[0])*(x[2]+y[2]+z[2]);
    if(!(orientation>1e-12))return 0;
    uint32_t *p=idx->faces+3u*(*n); p[0]=a;p[1]=b;p[2]=c; ++*n;return 1;
}
gd_status gd_geometry(gd_index *idx) {
    uint8_t *seen=calloc(GD_VERTICES,1);
    uint32_t *local=malloc(LOCAL*sizeof(*local));
    uint64_t *raw=malloc(3u*GD_FACES*sizeof(*raw));
    gd_status rc=GD_ALLOC;
    if(!seen||!local||!raw)goto done;
    rc=GD_INVARIANT;
    uint32_t ids[12][12];
    for(unsigned a=0;a<12;a++)for(unsigned b=0;b<12;b++)ids[a][b]=GD_NONE;
    for(unsigned f=0;f<20;f++)for(unsigned t=0;t<3;t++) {
        uint32_t a=base_faces[f][t],b=base_faces[f][(t+1)%3];
        if(a>b){uint32_t q=a;a=b;b=q;}ids[a][b]=0;
    }
    uint32_t ne=0;
    for(unsigned a=0;a<12;a++)for(unsigned b=a+1;b<12;b++)if(ids[a][b]!=GD_NONE)ids[a][b]=ne++;
    if(ne!=30)goto done;
    double p=(1+sqrt(5.0))/2;
    double base[12][3]={{-1,p,0},{1,p,0},{-1,-p,0},{1,-p,0},{0,-1,p},{0,1,p},
        {0,-1,-p},{0,1,-p},{p,0,-1},{p,0,1},{-p,0,-1},{-p,0,1}};
    for(unsigned a=0;a<12;a++){
        double *v=base[a];double norm=sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
        for(unsigned t=0;t<3;t++)v[t]/=norm;
    }
    uint32_t nv=0,nf=0;
    for(uint32_t fid=0;fid<20;fid++) {
        const uint32_t *f=base_faces[fid];
        for(uint32_t i=0;i<=FREQ;i++)for(uint32_t j=0;j<=FREQ-i;j++){
            uint32_t k=FREQ-i-j,v=vertex_id(fid,i,j,k,ids);
            if(v>=GD_VERTICES)goto done;
            double xyz[3];
            for(unsigned t=0;t<3;t++)xyz[t]=(i*base[f[0]][t]+j*base[f[1]][t]+k*base[f[2]][t])/FREQ;
            double norm=sqrt(xyz[0]*xyz[0]+xyz[1]*xyz[1]+xyz[2]*xyz[2]);
            if(!(norm>0)||!isfinite(norm))goto done;
            for(unsigned t=0;t<3;t++)xyz[t]/=norm;
            if(seen[v]) {
                for(unsigned t=0;t<3;t++)if(fabs(idx->xyz[3u*v+t]-xyz[t])>1e-12)goto done;
            }else{seen[v]=1;nv++;memcpy(idx->xyz+3u*v,xyz,sizeof xyz);}
            local[row(i)+j]=v;
        }
        for(uint32_t i=0;i<FREQ;i++)for(uint32_t j=0;j<FREQ-i;j++){
            uint32_t a=local[row(i)+j],b=local[row(i+1)+j],c=local[row(i)+j+1];
            if(!emit(idx,&nf,a,b,c))goto done;
            if(i+j<FREQ-1&&!emit(idx,&nf,b,local[row(i+1)+j+1],c))goto done;
        }
    }
    if(nv!=GD_VERTICES||nf!=GD_FACES)goto done;
    for(uint32_t f=0;f<GD_FACES;f++)for(unsigned t=0;t<3;t++){
        uint32_t a=idx->faces[3u*f+t],b=idx->faces[3u*f+(t+1)%3];
        /* Keep orientation bit so every edge has opposing incidence. */
        raw[3u*f+t]=(gd_edge(a,b)<<1)|(a>b);
    }
    qsort(raw,3u*GD_FACES,sizeof(*raw),cmp64);
    for(uint32_t e=0;e<GD_EDGES;e++){
        uint64_t a=raw[2u*e],b=raw[2u*e+1u];
        if((a&1u)||b!=a+1u||(e&&idx->edges[e-1]>=a/2u))goto done;
        idx->edges[e]=a/2u;
    }
    rc=GD_OK;
done:
    free(raw);free(local);free(seen);return rc;
}
