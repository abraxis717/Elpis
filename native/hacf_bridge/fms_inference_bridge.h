#ifndef ELPIS_FMS_INFERENCE_BRIDGE_H
#define ELPIS_FMS_INFERENCE_BRIDGE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct elpis_fms_inference_ctx elpis_fms_inference_ctx;
typedef struct elpis_fms_inference_stats {
    uint64_t tier_bytes[3];
    uint64_t domain_bytes[3];
    uint64_t objects;
    uint64_t pinned_bytes;
    uint64_t forced_cpu_fallbacks;
    uint64_t forced_placements;
} elpis_fms_inference_stats;

int elpis_fms_inference_create(
    const char *cold_root, uint64_t warm_budget_bytes,
    uint64_t cold_budget_bytes, int hot_absent_policy,
    elpis_fms_inference_ctx **out);
void elpis_fms_inference_destroy(elpis_fms_inference_ctx *ctx);
int elpis_fms_inference_register_checkpoint(
    elpis_fms_inference_ctx *ctx, const void *bytes, uint64_t size_bytes,
    int want_tier, int *actual_tier);
int elpis_fms_inference_acquire_checkpoint(
    elpis_fms_inference_ctx *ctx, int want_tier, const void **ptr_out,
    uint64_t *size_out, int *actual_tier);
int elpis_fms_inference_release_checkpoint(elpis_fms_inference_ctx *ctx);
int elpis_fms_inference_unregister_checkpoint(elpis_fms_inference_ctx *ctx);
int elpis_fms_inference_hot_available(elpis_fms_inference_ctx *ctx);
const char *elpis_fms_inference_backend_name(elpis_fms_inference_ctx *ctx);
int elpis_fms_inference_get_stats(
    elpis_fms_inference_ctx *ctx, elpis_fms_inference_stats *out);
const char *elpis_fms_inference_strerror(int status);

#ifdef __cplusplus
}
#endif
#endif
