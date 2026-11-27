#ifndef ELPIS_MODEL_PROTOCOL_H
#define ELPIS_MODEL_PROTOCOL_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* DEV C ABI 1, independent of RuntimeCore ABI v8. All wire scalars LE.
 * No struct is serialized by memcpy. No pointer, path, text or native handle
 * crosses the wire. The codec is not authorization or execution authority. */
enum { EMP_VERSION=1, EMP_HEADER=32, EMP_MAX_PAYLOAD=2276, EMP_MAX_FRAME=2308 };
enum { EMP_INSPECT=1, EMP_LOOKUP=2, EMP_READ_ROW=3, EMP_PROPOSE_ADAPT=4 };
enum { EMP_OK=0, EMP_PROPOSED=1, EMP_INVALID=2, EMP_STALE=3, EMP_REFUSED=4, EMP_BUSY=5, EMP_LIMIT=6, EMP_UNAVAILABLE=7 };
enum { EMP_CODEC_OK=0, EMP_CODEC_INVALID=-1, EMP_CODEC_SIZE=-2, EMP_CODEC_VERSION=-3, EMP_CODEC_OPCODE=-4 };
/* Header offsets: magic[4] ELQ1/ELR1, version:u16, op:u16,
 * payload_bytes:u32, status:u32 (request zero), request_id:u64 (nonzero), reserved:u64 (zero).
 * Coordinate: session[32], instance:u64, generation:u64, root[32], store_instance:u64, revision:u64.
 * Key: source[32], relation[32], scope[32].
 * Requests: INSPECT empty; LOOKUP coord+key; READ_ROW coord+vertex:u32;
 * PROPOSE_ADAPT coord+vertex+key+record_id[32]+X[32][5]+Y[32][3] binary64 LE.
 * X bias column exactly +1; all numbers finite. Proposal is INERT, not a learn or commit.
 * Responses: OK INSPECT coord+physical/adaptive/records/links:u32 each+payload_bytes:u64+reserved:u64 zero;
 * OK LOOKUP coord+records/locators/conflict:u32 each+target[32]; OK READ_ROW coord+row[3]+revision:u64.
 * PROPOSED only for PROPOSE_ADAPT, no payload. Errors have no payload. No successful commit opcode.
 * Request IDs only correlate frames; replay/session authorization belongs to the owner, not codec. */
typedef struct { uint64_t request_id; uint32_t length,status; uint16_t op; uint8_t payload[EMP_MAX_PAYLOAD]; } emp_message;
uint32_t emp_abi_version(void);
/* response is exactly 0 (request) or 1 (response). Inputs/outputs must be valid
 * nonoverlapping caller buffers. No output bytes or size modified on refusal. */
int emp_decode(unsigned response,const uint8_t *wire,size_t size,emp_message *out);
int emp_encode(unsigned response,const emp_message *msg,uint8_t *wire,size_t capacity,size_t *written);
#ifdef __cplusplus
}
#endif
#endif
