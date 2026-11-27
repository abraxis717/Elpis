/* SPDX-License-Identifier: Apache-2.0
 * CR3 functional evidence obligations, serialized volatile session extension. */
#ifndef ELPIS_ECS_C_ENROLLMENT_H
#define ELPIS_ECS_C_ENROLLMENT_H
#include "elpis/ecs_c_session.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EVE_MAX_RECORDS 1024u
#define EVE_MAX_LINKS 4096u
#define EVE_MAX_ADMISSIONS 1024u
#define EVE_MAX_PAGE 1024u
#define EVE_IDENTITY_CONFLICT 100
#define EVE_LAST_LOCATOR 101
#define EVE_NOT_FOUND 102
#define EVE_TX_STATE 103
#define EVE_TURN_LIMIT 104
/* Session status codes are returned unchanged; custom codes above are local.
 * Serialized trusted caller, no overlapping calls or external session transitions
 * during a call. Session must outlive this object. All buffers valid/disjoint.
 * The store does not own or authenticate physical/adaptive handles; CR4 does.
 * All record identities are exact canonical digests, not approximate matches. */
typedef struct eve_store eve_store;
typedef struct { uint8_t source[32], relation[32], scope[32]; } eve_key;
typedef struct {
    eve_key key;
    uint64_t source_version;
    uint8_t target[32], provenance[32], id[32];
} eve_record;
typedef struct {
    uint64_t state_owner, state_epoch, state_generation;
    uint64_t cell_owner, cell_epoch, cell_generation, cell_revision;
    uint32_t vertex, state_slot, cell_slot, cell_key;
} eve_locator;
typedef struct { eve_record record; eve_locator locator; } eve_member;
typedef struct { elpis_ecs_c_session_coordinate session; uint64_t store_instance, revision; } eve_coordinate;
typedef struct { eve_coordinate coordinate; uint64_t transaction; } eve_receipt;
typedef struct {
    uint32_t records, locators, distinct_conflict; /* 1 iff >=2 distinct live targets */
    uint8_t target[32]; /* zero for empty or conflict */
} eve_answer;
typedef struct { uint32_t record_capacity, link_capacity, records, locators, transaction_open; uint64_t revision; size_t payload_bytes; } eve_stats;
/* Canonical SHA-256 over domain, source/relation/scope, LE source_version,
 * target and provenance. No physical coordinates in this digest. */
int eve_record_id(const eve_record *r, uint8_t out[32]);
int eve_create(elpis_ecs_c_session *session, uint32_t records, uint32_t links, eve_store **out);
void eve_destroy(eve_store *s);
int eve_coordinate_read(const eve_store *s, eve_coordinate *out);
int eve_inspect(const eve_store *s, eve_stats *out);
int eve_begin(eve_store *s, const eve_coordinate *expected, uint64_t *transaction);
/* Atomically stage evidence and locator. Repeated identical association refuses;
 * same evidence ID with another locator is permitted. Source's per-turn limit
 * enforced across successful admissions in this transaction, not global turns. */
int eve_admit(eve_store *s, uint64_t transaction, const eve_record *r, const eve_locator *l);
/* Detach only if another locator remains; do not silently discard evidence. */
int eve_detach(eve_store *s, uint64_t transaction, const uint8_t id[32], const eve_locator *l);
/* Reclaim only absent/terminated/older-version sources. Dormant stays retained. */
int eve_prune(eve_store *s, uint64_t transaction, uint32_t *retired);
int eve_reset(eve_store *s, uint64_t transaction);
int eve_commit(eve_store *s, uint64_t transaction, eve_receipt *out);
int eve_abort(eve_store *s, uint64_t transaction);
/* Read committed bank only, pinned to current session coordinate and revision.
 * Lookup/page report only source-live records; locators are declared, not verified
 * live in external components. Page order is bank slot order; pin across pages. */
int eve_lookup(const eve_store *s, const eve_coordinate *expected, const eve_key *key, eve_answer *out);
int eve_page(const eve_store *s, const eve_coordinate *expected, const eve_key *key,
             uint32_t offset, uint32_t limit, eve_member *out, uint32_t *written);
#ifdef __cplusplus
}
#endif
#endif
