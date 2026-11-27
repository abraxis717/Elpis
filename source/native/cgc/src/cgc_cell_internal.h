#ifndef ELPIS_CGC_CELL_INTERNAL_H
#define ELPIS_CGC_CELL_INTERNAL_H
#include "elpis/cgc_r97w.h"
struct cgr_cell {
    double initial[CGR_PARAMS], slow[CGR_PARAMS], fast[CGR_PARAMS];
    double ss[CGR_PARAMS], sf[CGR_PARAMS], proposal[CGR_PARAMS];
    double x[CGR_SUPPORT*CGR_INPUTS], y[CGR_SUPPORT*CGR_OUTPUTS];
    uint64_t revision, observation, staged_observation;
    uint32_t active, observed, steps, proposed, consolidated;
};
#endif
