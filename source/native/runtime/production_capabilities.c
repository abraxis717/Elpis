/* SPDX-License-Identifier: Apache-2.0 */
#include "borrowed.h"
/* Private C capability table. Rust owns context and supplies synchronous
 * callbacks. No Rust layout crosses this boundary except this repr(C) table. */
typedef struct {
    const void *session;
    int32_t (*coordinate)(const void *,elpis_ecs_c_session_coordinate *);
    int32_t (*at)(const void *,uint32_t,elpis_ecs_c_entity *);
    int32_t (*find)(const void *,const uint8_t *,elpis_ecs_c_entity *);
    int32_t (*next)(const void *,uint8_t,const uint8_t *,uint8_t *);
    int32_t (*check)(const void *,const uint8_t *,uint64_t,const uint8_t *,uint32_t *);
} cr5_context;
_Static_assert(sizeof(cr5_context)==6*sizeof(void*),"context layout");
_Static_assert(sizeof(eve_key)==96 && sizeof(eve_record)==200 && sizeof(eve_locator)==72,"evidence layout");
_Static_assert(sizeof(eve_coordinate)==96 && sizeof(eve_receipt)==104 && sizeof(eve_answer)==44,"coordinate layout");
_Static_assert(sizeof(ct_stats)==32 && sizeof(gsc_stats)==32 && sizeof(gsc_limits)==12,"stats layout");
#define CTX(s) ((const cr5_context *)(s))
int32_t cr5_session_read_coordinate(const elpis_ecs_c_session*s,elpis_ecs_c_session_coordinate*out){return s&&CTX(s)->session?CTX(s)->coordinate(CTX(s)->session,out):ELPIS_ECS_C_INVALID;}
int32_t cr5_session_entity_at(const elpis_ecs_c_session*s,uint32_t i,elpis_ecs_c_entity*out){return s&&CTX(s)->session?CTX(s)->at(CTX(s)->session,i,out):ELPIS_ECS_C_INVALID;}
int32_t cr5_session_entity_find(const elpis_ecs_c_session*s,const uint8_t id[32],elpis_ecs_c_entity*out){return s&&CTX(s)->session?CTX(s)->find(CTX(s)->session,id,out):ELPIS_ECS_C_INVALID;}
int32_t cr5_session_next_entity_id(const elpis_ecs_c_session*s,uint8_t k,const uint8_t label[32],uint8_t out[32]){return s&&CTX(s)->session?CTX(s)->next(CTX(s)->session,k,label,out):ELPIS_ECS_C_INVALID;}
int32_t cr5_session_check_evidence(const elpis_ecs_c_session*s,const uint8_t id[32],uint64_t v,const uint8_t scope[32],uint32_t*out){return s&&CTX(s)->session?CTX(s)->check(CTX(s)->session,id,v,scope,out):ELPIS_ECS_C_INVALID;}
int32_t cr5_session_create(const elpis_ecs_c_session_config*c,elpis_ecs_c_session**out){(void)c;if(out)*out=NULL;return ELPIS_ECS_C_UNAUTHORIZED;}
void cr5_session_destroy(elpis_ecs_c_session*s){(void)s;}
int32_t cr5_session_transition(elpis_ecs_c_session*s,const elpis_ecs_c_session_coordinate*c,const uint8_t e[512],elpis_ecs_c_session_receipt*out){(void)s;(void)c;(void)e;(void)out;return ELPIS_ECS_C_UNAUTHORIZED;}
