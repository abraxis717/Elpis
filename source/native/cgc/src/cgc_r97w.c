#include "elpis/cgc_r97w.h"
#include "elpis/ecsg_math.h"
#include <float.h>
#include <fenv.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
_Static_assert(DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 && sizeof(double)==8,"binary64 required");
#include "cgc_cell_internal.h"
static int finite_vec(const double *p,size_t n){
    if(!p) return 0;
    for(size_t i=0;i<n;i++) if(!isfinite(p[i])) return 0;
    return 1;
}
static int fp_ok(void){return fegetround()==FE_TONEAREST;}
cgr_status cgr_predict(const double *w,const double *x,size_t rows,double *y){
    if(!w||!x||!y||!rows||rows>CGR_MAX_ROWS||!fp_ok())return CGR_INVALID;
    if(!finite_vec(w,CGR_PARAMS)||!finite_vec(x,rows*CGR_INPUTS))return CGR_NONFINITE;
    double out[CGR_MAX_ROWS*CGR_OUTPUTS], col[CGR_MAX_ROWS];
    for(size_t o=0;o<CGR_OUTPUTS;o++){
        if(elpis_ecsg_forward_f64(w+o*CGR_INPUTS*CGR_MICRO,CGR_INPUTS,CGR_MICRO,x,rows,col)!=ELPIS_ECSG_MATH_OK)return CGR_NONFINITE;
        for(size_t r=0;r<rows;r++)out[r*CGR_OUTPUTS+o]=col[r];
    }
    if(!finite_vec(out,rows*CGR_OUTPUTS))return CGR_NONFINITE;
    memcpy(y,out,rows*CGR_OUTPUTS*sizeof(double));return CGR_OK;
}
cgr_status cgr_step(const double *w,const double *x,const double *y,size_t rows,double *next){
    if(!w||!x||!y||!next||!rows||rows>CGR_MAX_ROWS||!fp_ok())return CGR_INVALID;
    if(!finite_vec(y,rows*CGR_OUTPUTS))return CGR_NONFINITE;
    double pred[CGR_MAX_ROWS*CGR_OUTPUTS],g[CGR_PARAMS]={0},tmp[CGR_PARAMS];
    cgr_status status=cgr_predict(w,x,rows,pred);if(status!=CGR_OK)return status;
    const double factor=2.0/(double)(rows*CGR_OUTPUTS);
    double loss=0.0;
    for(size_t r=0;r<rows;r++)for(size_t o=0;o<CGR_OUTPUTS;o++){
        double e=pred[r*CGR_OUTPUTS+o]-y[r*CGR_OUTPUTS+o];
        loss+=e*e;if(!isfinite(loss))return CGR_NONFINITE;
        for(size_t i=0;i<CGR_MICRO;i++){
            double z=0.0;
            for(size_t a=0;a<CGR_INPUTS;a++)z+=x[r*CGR_INPUTS+a]*w[(o*CGR_INPUTS+a)*CGR_MICRO+i];
            double d=(factor*e)*(0.5+z+1.5*z*z);
            if(!isfinite(d))return CGR_NONFINITE;
            for(size_t a=0;a<CGR_INPUTS;a++)g[(o*CGR_INPUTS+a)*CGR_MICRO+i]+=x[r*CGR_INPUTS+a]*d;
        }
    }
    double ss=0.0;
    for(size_t j=0;j<CGR_PARAMS;j++)ss+=g[j]*g[j];
    if(!isfinite(ss))return CGR_NONFINITE;
    double scale=fmin(1.0,2.0/(sqrt(ss)+1e-12));
    for(size_t j=0;j<CGR_PARAMS;j++)tmp[j]=w[j]-0.08*scale*g[j];
    if(!finite_vec(tmp,CGR_PARAMS))return CGR_NONFINITE;
    memcpy(next,tmp,sizeof tmp);return CGR_OK;
}
cgr_status cgr_interpolate(const double *slow,const double *fast,double *next){
    if(!slow||!fast||!next||!fp_ok())return CGR_INVALID;
    if(!finite_vec(slow,CGR_PARAMS)||!finite_vec(fast,CGR_PARAMS))return CGR_NONFINITE;
    double tmp[CGR_PARAMS];
    for(size_t j=0;j<CGR_PARAMS;j++)tmp[j]=slow[j]+0.28*(fast[j]-slow[j]);
    if(!finite_vec(tmp,CGR_PARAMS))return CGR_NONFINITE;
    memcpy(next,tmp,sizeof tmp);return CGR_OK;
}
cgr_status cgr_create(const double *initial,cgr_cell **out){
    if(!initial||!out||!fp_ok())return CGR_INVALID;
    if(!finite_vec(initial,CGR_PARAMS))return CGR_NONFINITE;
    cgr_cell *c=calloc(1,sizeof *c);if(!c)return CGR_NOMEM;
    memcpy(c->initial,initial,sizeof c->initial);memcpy(c->slow,initial,sizeof c->slow);memcpy(c->fast,initial,sizeof c->fast);
    *out=c;return CGR_OK;
}
void cgr_destroy(cgr_cell *c){if(c){memset(c,0,sizeof *c);free(c);}}
size_t cgr_payload_bytes(void){return sizeof(cgr_cell);}
static void clear(cgr_cell *c){
    memset(c->ss,0,sizeof c->ss);memset(c->sf,0,sizeof c->sf);memset(c->proposal,0,sizeof c->proposal);
    memset(c->x,0,sizeof c->x);memset(c->y,0,sizeof c->y);
    c->active=c->observed=c->steps=c->proposed=c->consolidated=0;c->staged_observation=0;
}
cgr_status cgr_begin(cgr_cell *c){
    if(!c)return CGR_INVALID;
    if(c->active)return CGR_STATE;
    if(c->revision==UINT64_MAX)return CGR_LIMIT;
    clear(c);memcpy(c->ss,c->slow,sizeof c->ss);memcpy(c->sf,c->fast,sizeof c->sf);c->active=1;return CGR_OK;
}
cgr_status cgr_observe(cgr_cell *c,uint64_t observation,const double *x,const double *y){
    if(!c||!observation||!x||!y)return CGR_INVALID;
    if(!c->active||c->observed)return CGR_STATE;
    if(!finite_vec(x,CGR_SUPPORT*CGR_INPUTS)||!finite_vec(y,CGR_SUPPORT*CGR_OUTPUTS))return CGR_NONFINITE;
    memcpy(c->x,x,sizeof c->x);memcpy(c->y,y,sizeof c->y);c->observed=1;c->staged_observation=observation;return CGR_OK;
}
cgr_status cgr_propose_update(cgr_cell *c){
    if(!c)return CGR_INVALID;
    if(!c->active||!c->observed||c->proposed||c->consolidated)return CGR_STATE;
    if(c->steps>=CGR_STEPS)return CGR_LIMIT;
    cgr_status status=cgr_step(c->sf,c->x,c->y,CGR_SUPPORT,c->proposal);
    if(status==CGR_OK)c->proposed=1;
    return status;
}
cgr_status cgr_learn(cgr_cell *c){
    if(!c)return CGR_INVALID;
    if(!c->active||!c->proposed)return CGR_STATE;
    memcpy(c->sf,c->proposal,sizeof c->sf);memset(c->proposal,0,sizeof c->proposal);c->proposed=0;c->steps++;return CGR_OK;
}
cgr_status cgr_consolidate(cgr_cell *c){
    if(!c)return CGR_INVALID;
    if(!c->active||c->proposed||c->consolidated||c->steps!=CGR_STEPS)return CGR_STATE;
    cgr_status status=cgr_interpolate(c->ss,c->sf,c->ss);
    if(status==CGR_OK)c->consolidated=1;
    return status;
}
cgr_status cgr_reset_fast(cgr_cell *c){
    if(!c)return CGR_INVALID;
    if(!c->active||c->proposed||(c->steps && !c->consolidated))return CGR_STATE;
    memcpy(c->sf,c->ss,sizeof c->sf);return CGR_OK;
}
cgr_status cgr_commit(cgr_cell *c){
    if(!c)return CGR_INVALID;
    if(!c->active||c->proposed)return CGR_STATE;
    if(c->revision==UINT64_MAX)return CGR_LIMIT;
    memcpy(c->slow,c->ss,sizeof c->slow);memcpy(c->fast,c->sf,sizeof c->fast);
    if(c->steps)c->observation=c->staged_observation;
    c->revision++;clear(c);return CGR_OK;
}
cgr_status cgr_abort(cgr_cell *c){if(!c)return CGR_INVALID;if(!c->active)return CGR_STATE;clear(c);return CGR_OK;}
static const double *bank_ptr(const cgr_cell *c,cgr_bank bank){
    if(!c)return NULL;
    switch(bank){case CGR_INITIAL:return c->initial;case CGR_SLOW:return c->slow;case CGR_FAST:return c->fast;
    case CGR_STAGED_SLOW:return c->active?c->ss:NULL;case CGR_STAGED_FAST:return c->active?c->sf:NULL;
    case CGR_PROPOSAL:return c->active&&c->proposed?c->proposal:NULL;default:return NULL;}
}
cgr_status cgr_query(const cgr_cell *c,cgr_bank bank,const double *x,size_t rows,double *y){
    if(bank!=CGR_INITIAL&&bank!=CGR_SLOW&&bank!=CGR_FAST)return CGR_INVALID;
    return cgr_predict(bank_ptr(c,bank),x,rows,y);
}
cgr_status cgr_inspect(const cgr_cell *c,cgr_info *info){
    if(!c||!info)return CGR_INVALID;
    cgr_info tmp={c->revision,c->observation,c->active,c->observed,c->steps,c->proposed,c->consolidated};*info=tmp;return CGR_OK;
}
cgr_status cgr_copy_bank(const cgr_cell *c,cgr_bank bank,double *out){
    const double *p=bank_ptr(c,bank);if(!p||!out)return CGR_INVALID;
    memcpy(out,p,CGR_PARAMS*sizeof(double));return CGR_OK;
}
