#include "fms_inference_bridge.h"
#include "elpis/fms.h"
#include "elpis/fms_pal_posix.h"
#include <stdlib.h>
#include <string.h>

#define ELPIS_FMS_KIND_MODEL_CHECKPOINT 0x4650524du

_Static_assert(FMS_NTIERS == 3,
    "elpis_fms_inference_stats Python ctypes ABI requires exactly 3 FMS tiers");
_Static_assert(FMS_NDOMAINS == 3,
    "elpis_fms_inference_stats Python ctypes ABI requires exactly 3 FMS domains");

struct elpis_fms_inference_ctx {
    fms_ctx *fms;
    fms_id checkpoint_id;
    uint64_t checkpoint_bytes;
    fms_lease *lease;
    int registered;
};

int elpis_fms_inference_create(
    const char *cold_root, uint64_t warm_budget_bytes,
    uint64_t cold_budget_bytes, int hot_absent_policy,
    elpis_fms_inference_ctx **out) {
    if (!cold_root || !*cold_root || !out) return FMS_E_INVAL;
    if (hot_absent_policy != FMS_FOLD_DOWN &&
        hot_absent_policy != FMS_REJECT) return FMS_E_INVAL;
    *out = NULL;
    fms_pal *pal = fms_pal_posix_create(cold_root);
    if (!pal) return FMS_E_IO;

    fms_config cfg;
    memset(&cfg, 0, sizeof cfg);
    cfg.tier_budget[FMS_WARM] = warm_budget_bytes;
    cfg.tier_budget[FMS_COLD] = cold_budget_bytes;
    cfg.domain_ceiling[FMS_DOM_RAM] = warm_budget_bytes;
    cfg.domain_ceiling[FMS_DOM_STORAGE] = cold_budget_bytes;
    cfg.high_wm = 0.90f;
    cfg.low_wm = 0.70f;
    cfg.max_objects = 8;
    cfg.hot_absent_policy = (uint8_t)hot_absent_policy;
    cfg.cold_absent_policy = FMS_FOLD_DOWN;

    fms_ctx *fms = fms_create(&cfg, pal);
    if (!fms) {
        pal->destroy(pal->self);
        return FMS_E_NOMEM;
    }

    elpis_fms_inference_ctx *ctx =
        (elpis_fms_inference_ctx *)calloc(1, sizeof *ctx);
    if (!ctx) {
        fms_destroy(fms);
        return FMS_E_NOMEM;
    }
    ctx->fms = fms;
    *out = ctx;
    return FMS_OK;
}

void elpis_fms_inference_destroy(elpis_fms_inference_ctx *ctx) {
    if (!ctx) return;
    if (ctx->lease) {
        (void)fms_lease_release(ctx->fms, ctx->lease);
        ctx->lease = NULL;
    }
    if (ctx->registered) {
        (void)fms_unregister(ctx->fms, ctx->checkpoint_id);
        ctx->registered = 0;
    }
    if (ctx->fms) fms_destroy(ctx->fms);
    free(ctx);
}

int elpis_fms_inference_register_checkpoint(
    elpis_fms_inference_ctx *ctx, const void *bytes, uint64_t size_bytes,
    int want_tier, int *actual_tier) {
    if (!ctx || !ctx->fms || !bytes || !size_bytes || !actual_tier)
        return FMS_E_INVAL;
    if (ctx->registered) return FMS_E_STATE;
    fms_id id = 0;
    fms_status rc = fms_register(
        ctx->fms, ELPIS_FMS_KIND_MODEL_CHECKPOINT, size_bytes,
        want_tier, 0.0f, bytes, &id);
    if (rc < 0) return rc;
    ctx->checkpoint_id = id;
    ctx->checkpoint_bytes = size_bytes;
    ctx->registered = 1;
    *actual_tier = (int)rc;
    return FMS_OK;
}

int elpis_fms_inference_acquire_checkpoint(
    elpis_fms_inference_ctx *ctx, int want_tier, const void **ptr_out,
    uint64_t *size_out, int *actual_tier) {
    if (!ctx || !ctx->fms || !ptr_out || !size_out || !actual_tier)
        return FMS_E_INVAL;
    if (!ctx->registered) return FMS_E_NOTFOUND;
    if (ctx->lease) return FMS_E_BUSY;

    fms_lease *lease = NULL;
    fms_status rc = fms_lease_acquire(
        ctx->fms, ctx->checkpoint_id, want_tier, FMS_READ, &lease);
    if (rc < 0) return rc;

    const void *ptr = fms_lease_ptr(lease);
    int tier = fms_lease_tier(lease);
    if (!ptr || tier < FMS_HOT || tier > FMS_COLD) {
        (void)fms_lease_release(ctx->fms, lease);
        return FMS_E_STATE;
    }
    ctx->lease = lease;
    *ptr_out = ptr;
    *size_out = ctx->checkpoint_bytes;
    *actual_tier = tier;
    return FMS_OK;
}

int elpis_fms_inference_release_checkpoint(elpis_fms_inference_ctx *ctx) {
    if (!ctx || !ctx->fms) return FMS_E_INVAL;
    if (!ctx->lease) return FMS_E_STATE;
    fms_status rc = fms_lease_release(ctx->fms, ctx->lease);
    if (rc == FMS_OK) ctx->lease = NULL;
    return rc;
}

int elpis_fms_inference_unregister_checkpoint(elpis_fms_inference_ctx *ctx) {
    if (!ctx || !ctx->fms) return FMS_E_INVAL;
    if (!ctx->registered) return FMS_E_NOTFOUND;
    if (ctx->lease) return FMS_E_BUSY;
    fms_status rc = fms_unregister(ctx->fms, ctx->checkpoint_id);
    if (rc == FMS_OK) {
        ctx->registered = 0;
        ctx->checkpoint_id = 0;
        ctx->checkpoint_bytes = 0;
    }
    return rc;
}

int elpis_fms_inference_hot_available(elpis_fms_inference_ctx *ctx) {
    return (ctx && ctx->fms) ? fms_hot_available(ctx->fms) : 0;
}

const char *elpis_fms_inference_backend_name(elpis_fms_inference_ctx *ctx) {
    if (!ctx || !ctx->fms) return "invalid";
    const char *name = fms_backend_name(ctx->fms);
    return name ? name : "unknown";
}

int elpis_fms_inference_get_stats(
    elpis_fms_inference_ctx *ctx, elpis_fms_inference_stats *out) {
    if (!ctx || !ctx->fms || !out) return FMS_E_INVAL;
    fms_stats stats;
    memset(&stats, 0, sizeof stats);
    fms_get_stats(ctx->fms, &stats);
    memset(out, 0, sizeof *out);
    for (int i = 0; i < FMS_NTIERS; ++i)
        out->tier_bytes[i] = stats.tier_bytes[i];
    for (int i = 0; i < FMS_NDOMAINS; ++i)
        out->domain_bytes[i] = stats.domain_bytes[i];
    out->objects = stats.objects;
    out->pinned_bytes = stats.pinned_bytes;
    out->forced_cpu_fallbacks = stats.forced_cpu_fallbacks;
    out->forced_placements = stats.forced_placements;
    return FMS_OK;
}

const char *elpis_fms_inference_strerror(int status) {
    return fms_strerror(status);
}
