/* SPDX-License-Identifier: Apache-2.0 */
#ifndef GD_INTERNAL_H
#define GD_INTERNAL_H
#include "elpis/geodome.h"
struct gd_index {
    double *xyz;
    uint32_t *faces, *codes, *inverse, *sorted, *neighbors;
    uint64_t *edges;
    uint8_t *degrees;
};
#define GD_SHIFT 18u
#define GD_MASK ((1u<<GD_SHIFT)-1u)
static inline uint64_t gd_edge(uint32_t a, uint32_t b) {
    if (a>b) { uint32_t t=a; a=b; b=t; }
    return ((uint64_t)a<<GD_SHIFT)|b;
}
gd_status gd_geometry(gd_index *idx);
gd_status gd_build_index(gd_index *idx);
uint32_t gd_pow7(uint32_t d);
uint32_t gd_rank_code(uint32_t rank);
#endif
