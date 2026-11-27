#include "model_protocol.h"
#include <string.h>
static uint64_t get(const uint8_t *p,unsigned n){uint64_t x=0;for(unsigned i=0;i<n;i++)x|=(uint64_t)p[i]<<(8*i);return x;}
static void put(uint8_t *p,unsigned n,uint64_t x){for(unsigned i=0;i<n;i++)p[i]=(uint8_t)(x>>(8*i));}
static int finite64(const uint8_t *p){return (get(p,8)&UINT64_C(0x7ff0000000000000))!=UINT64_C(0x7ff0000000000000);}
uint32_t emp_abi_version(void){return EMP_VERSION;}
static int validate(unsigned resp,uint16_t op,uint32_t status,uint64_t id,uint32_t len,const uint8_t *p){
    if(resp>1||!id)return EMP_CODEC_INVALID;
    if(op<EMP_INSPECT||op>EMP_PROPOSE_ADAPT)return EMP_CODEC_OPCODE;
    static const uint32_t req[]={0,0,192,100,2276}, ans[]={0,128,140,128,0};
    if(!resp){
        if(status)return EMP_CODEC_INVALID;
        if(len!=req[op])return EMP_CODEC_SIZE;
        if(op==EMP_PROPOSE_ADAPT){
            for(unsigned i=0;i<256;i++)if(!finite64(p+228+8*i))return EMP_CODEC_INVALID;
            for(unsigned i=0;i<32;i++)if(get(p+228+8*(5*i+4),8)!=UINT64_C(0x3ff0000000000000))return EMP_CODEC_INVALID;
        }
    }else{
        if(status>EMP_UNAVAILABLE)return EMP_CODEC_INVALID;
        if(status==EMP_PROPOSED){if(op!=EMP_PROPOSE_ADAPT)return EMP_CODEC_INVALID;}
        else if(status==EMP_OK){if(op==EMP_PROPOSE_ADAPT)return EMP_CODEC_INVALID;}
        if(len!=(status==EMP_OK?ans[op]:0))return EMP_CODEC_SIZE;
        if(status==EMP_OK&&op==EMP_INSPECT&&get(p+120,8))return EMP_CODEC_INVALID;
        if(status==EMP_OK&&op==EMP_READ_ROW)for(unsigned i=0;i<3;i++)if(!finite64(p+96+8*i))return EMP_CODEC_INVALID;
    }
    return EMP_CODEC_OK;
}
int emp_decode(unsigned resp,const uint8_t *wire,size_t size,emp_message *out){
    if(resp>1||!wire||!out)return EMP_CODEC_INVALID;
    if(size<EMP_HEADER||size>EMP_MAX_FRAME)return EMP_CODEC_SIZE;
    if(memcmp(wire,resp?"ELR1":"ELQ1",4)||get(wire+24,8))return EMP_CODEC_INVALID;
    if(get(wire+4,2)!=EMP_VERSION)return EMP_CODEC_VERSION;
    uint16_t op=(uint16_t)get(wire+6,2);uint32_t len=(uint32_t)get(wire+8,4),status=(uint32_t)get(wire+12,4);uint64_t id=get(wire+16,8);
    if(len!=size-EMP_HEADER)return EMP_CODEC_SIZE;
    int rc=validate(resp,op,status,id,len,wire+EMP_HEADER);if(rc)return rc;
    memset(out,0,sizeof *out);out->request_id=id;out->length=len;out->status=status;out->op=op;memcpy(out->payload,wire+EMP_HEADER,len);return 0;
}
int emp_encode(unsigned resp,const emp_message *msg,uint8_t *wire,size_t capacity,size_t *written){
    if(resp>1||!msg||!wire||!written)return EMP_CODEC_INVALID;
    if(msg->length>EMP_MAX_PAYLOAD||capacity<EMP_HEADER+msg->length)return EMP_CODEC_SIZE;
    int rc=validate(resp,msg->op,msg->status,msg->request_id,msg->length,msg->payload);if(rc)return rc;
    memcpy(wire,resp?"ELR1":"ELQ1",4);put(wire+4,2,EMP_VERSION);put(wire+6,2,msg->op);put(wire+8,4,msg->length);put(wire+12,4,msg->status);put(wire+16,8,msg->request_id);put(wire+24,8,0);memcpy(wire+EMP_HEADER,msg->payload,msg->length);*written=EMP_HEADER+msg->length;return 0;
}
