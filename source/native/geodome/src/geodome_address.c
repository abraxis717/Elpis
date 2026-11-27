/* SPDX-License-Identifier: Apache-2.0
 * Algorithm port: Hexaflag.py and GEO144K/g2b_bridge.py. */
#include "internal.h"
static const int32_t digits[7][2]={{0,0},{1,0},{0,1},{-1,1},{-1,0},{0,-1},{1,-1}};
uint32_t gd_pow7(uint32_t d){uint32_t p=1;while(d--)p*=7;return p;}
uint32_t gd_rank_code(uint32_t rank){
    uint32_t lo=0,hi=GD_VERTICES,code=0;
    for(unsigned i=0;i<GD_DEPTH;i++){
        uint32_t span=hi-lo,q=span/7,r=span%7,rel=rank-lo,large=(q+1)*r;
        uint32_t d=rel<large?rel/(q+1):r+(rel-large)/q;
        lo+=d*q+(d<r?d:r);hi=lo+q+(d<r);code=7*code+d;
    }
    return hi-lo==1&&lo==rank?code:GD_NONE;
}
gd_status gd_address_decode(uint32_t depth,uint32_t code,int32_t out[][2]){
    if(depth>GD_DEPTH||code>=gd_pow7(depth)||(depth&&!out))return GD_RANGE;
    for(uint32_t i=depth;i>0;i--){out[i-1][0]=digits[code%7][0];out[i-1][1]=digits[code%7][1];code/=7;}
    return GD_OK;
}
gd_status gd_address_encode(uint32_t depth,const int32_t d[][2],uint32_t *code){
    if(!code||depth>GD_DEPTH||(depth&&!d))return GD_RANGE;
    uint32_t c=0;
    for(uint32_t i=0;i<depth;i++){
        unsigned j=0;while(j<7&&(d[i][0]!=digits[j][0]||d[i][1]!=digits[j][1]))j++;
        if(j==7)return GD_RANGE;
        c=7*c+j;
    }
    *code=c;return GD_OK;
}
gd_status gd_coordinate(uint32_t depth,uint32_t code,int32_t *x,int32_t *y){
    int32_t d[GD_DEPTH][2];
    if(!x||!y||x==y||gd_address_decode(depth,code,d)!=GD_OK)return GD_RANGE;
    int32_t a=0,b=0;
    for(uint32_t i=0;i<depth;i++){
        int32_t u=(i%2?3*a+b:2*a-b)+d[i][0];
        int32_t v=(i%2?-a+2*b:a+3*b)+d[i][1];a=u;b=v;
    }
    *x=a;*y=b;return GD_OK;
}
gd_status gd_coordinate_code(uint32_t depth,int32_t x,int32_t y,uint32_t *code){
    if(!code||depth>GD_DEPTH)return GD_RANGE;
    int64_t a=x,b=y;uint32_t c=0,p=1;
    for(uint32_t i=depth;i>0;i--){
        unsigned matches=0;int64_t u=0,v=0;uint32_t found=0;
        for(uint32_t d=0;d<7;d++){
            int64_t s=a-digits[d][0],t=b-digits[d][1];
            int64_t q=(i-1)%2?2*s-t:3*s+t;
            int64_t r=(i-1)%2?s+3*t:-s+2*t;
            if(q%7==0&&r%7==0){matches++;u=q/7;v=r/7;found=d;}
        }
        if(matches!=1)return GD_INVARIANT;
        c+=p*found;p*=7;a=u;b=v;
    }
    if(a||b)return GD_RANGE;
    *code=c;return GD_OK;
}
