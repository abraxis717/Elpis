#ifndef ELPIS_MODEL_IPC_H
#define ELPIS_MODEL_IPC_H
#include <stddef.h>
#include <stdint.h>
/* Local transport only: one LE32 length (1..2308), followed by exact payload.
 * Model and operator lanes have independent preallocated RX/TX slots.
 * Trusted host exclusively owns the lane structs; no pointers cross the wire.
 * A tick performs at most one read and one write; no allocation or wait.
 * One packet is sent via one <= PIPE_BUF write. Caller never retries a
 * partial write: it closes the affected lane. No resynchronization.
 * A detected EOF/HUP discards all partial/queued packets on that lane.
 * Peer death is observed at poll/read/write, not atomically with a decision. */
enum { CR6_IPC_MODEL=0, CR6_IPC_OPERATOR=1, CR6_IPC_MAX=2308, CR6_IPC_PACKET=2312 };
enum { CR6_IPC_IDLE=0, CR6_IPC_PROGRESS=1, CR6_IPC_READY=2, CR6_IPC_CLOSED=-1, CR6_IPC_INVALID=-2, CR6_IPC_BUSY=-3 };
typedef struct { uint8_t rx[CR6_IPC_PACKET],tx[CR6_IPC_PACKET]; uint32_t used,target,queued; int32_t role,closed; } cr6_ipc_lane;
void cr6_ipc_guard(void);
int cr6_ipc_init(cr6_ipc_lane *,int role);
/* Explicit teardown closes the lane's own fixed descriptors, idempotent. */
void cr6_ipc_close(cr6_ipc_lane *);
/* At most one poll call, 0..100ms; closed lanes ignored. HUP/ERR closes lane
 * even when a pending reply or unread bytes exist. It never dispatches. */
int cr6_ipc_poll(cr6_ipc_lane *model,cr6_ipc_lane *operator_lane,int ms);
/* RX pauses while a response is queued or a frame awaits consumption. */
int cr6_ipc_receive(cr6_ipc_lane *);
int cr6_ipc_peek(const cr6_ipc_lane *,const uint8_t **,size_t *);
int cr6_ipc_consume(cr6_ipc_lane *);
int cr6_ipc_queue(cr6_ipc_lane *,const uint8_t *,size_t);
int cr6_ipc_flush(cr6_ipc_lane *);
#endif
