/* SPDX-License-Identifier: Apache-2.0
 * Native port of HexaFlake Geodome v1.0.0; see PROVENANCE.md. */
#ifndef ELPIS_GEODOME_H
#define ELPIS_GEODOME_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
#define GD_VERTICES 144002u
#define GD_EDGES 432000u
#define GD_FACES 288000u
#define GD_ARCS 864000u
#define GD_CAPACITY 823543u
#define GD_DEPTH 7u
#define GD_PAGE_MAX 1024u
#define GD_NONE UINT32_MAX
/* Opaque, immutable after create. Caller serializes lifetime. No state or transport authority. */
typedef struct gd_index gd_index;
typedef enum { GD_OK=0, GD_RANGE=1, GD_UNOCCUPIED=2, GD_NONEDGE=3, GD_ALLOC=4, GD_INVARIANT=5 } gd_status;
gd_status gd_create(gd_index **out);
void gd_destroy(gd_index *idx);
size_t gd_payload_bytes(const gd_index *idx);
gd_status gd_vertex_code(const gd_index *idx, uint32_t v, uint32_t *code);
gd_status gd_resolve_code(const gd_index *idx, uint32_t code, uint32_t *v);
gd_status gd_xyz(const gd_index *idx, uint32_t v, double out[3]);
gd_status gd_face(const gd_index *idx, uint32_t f, uint32_t out[3]);
gd_status gd_neighbors(const gd_index *idx, uint32_t v, uint32_t out[6], uint32_t *count);
gd_status gd_arc_id(const gd_index *idx, uint32_t u, uint32_t v, uint32_t *arc);
gd_status gd_arc_endpoints(const gd_index *idx, uint32_t arc, uint32_t *u, uint32_t *v);
/* Prefix represented by (depth, radix-7 code); root is (0,0). */
gd_status gd_prefix_count(const gd_index *idx, uint32_t depth, uint32_t code, uint32_t *count);
gd_status gd_prefix_page(const gd_index *idx, uint32_t depth, uint32_t code, uint32_t offset,
                         uint32_t limit, uint32_t *out, uint32_t *count);
/* Digit pairs in canonical Hexaflag order. Exactly depth rows supplied by caller. */
gd_status gd_address_decode(uint32_t depth, uint32_t code, int32_t out[][2]);
gd_status gd_address_encode(uint32_t depth, const int32_t digits[][2], uint32_t *code);
gd_status gd_coordinate(uint32_t depth, uint32_t code, int32_t *x, int32_t *y);
gd_status gd_coordinate_code(uint32_t depth, int32_t x, int32_t y, uint32_t *code);
#ifdef __cplusplus
}
#endif
#endif
