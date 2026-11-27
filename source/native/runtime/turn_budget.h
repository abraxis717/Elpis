/* SPDX-License-Identifier: Apache-2.0 */
#ifndef CR5_TURN_BUDGET_H
#define CR5_TURN_BUDGET_H
#include "borrowed.h"
/* Private serialized logical turn, independent of native transaction tokens.
 * Limits are conservative reservations, not elapsed time or measured FLOPs.
 * Zero denies the corresponding operation; a refused/aborted native operation
 * never refunds an accepted reservation. Trusted owner explicitly ends a turn. */
enum { TB_TX,TB_ADMISSIONS,TB_EPISODES,TB_ROWS,TB_STEPS,TB_READS,TB_PANEL,TB_ARCS,TB_SEEDS,TB_ROUNDS,TB_VISITS,TB_ACTIVE_ROUNDS,TB_N };
typedef struct { uint64_t v[TB_N]; } ct_turn_budget;
int ct_budget_start(ct_runtime *,const ct_turn_budget *);
int ct_budget_end(ct_runtime *);
int ct_budget_open(const ct_runtime *);
int ct_budget_usage(const ct_runtime *,ct_turn_budget *);
#endif
