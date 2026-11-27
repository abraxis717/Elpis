/* SPDX-License-Identifier: Apache-2.0 */
#ifndef CR5_BORROWED_H
#define CR5_BORROWED_H
#include "elpis/cognitive_transaction.h"
/* Private DEV ABI: caller owns a valid C ABI session; must serialize every call,
 * keep session alive until coordinator destroy, and admit at most one coordinator
 * per owner. No cross-DSO Rust object layout contract is implied. */
int ct_create_borrowed(elpis_ecs_c_session *session,uint32_t cells,uint32_t records,uint32_t links,uint32_t width,ct_runtime **out);
#endif
