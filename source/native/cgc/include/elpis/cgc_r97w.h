#ifndef ELPIS_CGC_R97W_H
#define ELPIS_CGC_R97W_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Trusted serialized caller. No evidence admission or scheduler authority.
 * W[o][a][i], X[row][a], Y[row][o]; binary64, contiguous.
 * Caller buffers must have the documented length and not alias the opaque cell.
 */
enum { CGR_INPUTS=5, CGR_OUTPUTS=3, CGR_MICRO=8, CGR_PARAMS=120,
       CGR_MAX_ROWS=64, CGR_SUPPORT=32, CGR_STEPS=8 };
typedef enum { CGR_OK=0, CGR_INVALID=-1, CGR_NONFINITE=-2,
               CGR_STATE=-3, CGR_LIMIT=-4, CGR_NOMEM=-5 } cgr_status;
typedef enum { CGR_INITIAL=0, CGR_SLOW=1, CGR_FAST=2,
               CGR_STAGED_SLOW=3, CGR_STAGED_FAST=4, CGR_PROPOSAL=5 } cgr_bank;
typedef struct cgr_cell cgr_cell;
typedef struct { uint64_t revision, observation; uint32_t active, observed,
    steps, proposed, consolidated; } cgr_info;
/* Atomic output: query writes rows*3; step writes 120; init requires 120. */
cgr_status cgr_predict(const double *w,const double *x,size_t rows,double *y);
cgr_status cgr_step(const double *w,const double *x,const double *y,size_t rows,double *next);
cgr_status cgr_interpolate(const double *slow,const double *fast,double *next);
cgr_status cgr_create(const double *initial,cgr_cell **out);
void cgr_destroy(cgr_cell *c);
size_t cgr_payload_bytes(void);
cgr_status cgr_begin(cgr_cell *c);
/* Observe exactly 32 support pairs, caller-supplied nonzero diagnostic ID. */
cgr_status cgr_observe(cgr_cell *c,uint64_t observation,const double *x,const double *y);
cgr_status cgr_propose_update(cgr_cell *c);
cgr_status cgr_learn(cgr_cell *c);
cgr_status cgr_consolidate(cgr_cell *c);
cgr_status cgr_reset_fast(cgr_cell *c);
cgr_status cgr_commit(cgr_cell *c);
cgr_status cgr_abort(cgr_cell *c);
cgr_status cgr_query(const cgr_cell *c,cgr_bank bank,const double *x,size_t rows,double *y);
cgr_status cgr_inspect(const cgr_cell *c,cgr_info *info);
cgr_status cgr_copy_bank(const cgr_cell *c,cgr_bank bank,double *out);
#ifdef __cplusplus
}
#endif
#endif
