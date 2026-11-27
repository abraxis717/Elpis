#include "model_ipc.h"
#include <errno.h>
#include <poll.h>
#include <string.h>
#include <unistd.h>
_Static_assert(CR6_IPC_PACKET<=4096,"Linux atomic pipe write bound");
static int valid(const cr6_ipc_lane *l){return l&&(l->role==0||l->role==1);}
static int in_fd(const cr6_ipc_lane *l){return 3+2*l->role;}
static int out_fd(const cr6_ipc_lane *l){return in_fd(l)+1;}
static int ready(const cr6_ipc_lane *l){return l->target>4&&l->used==l->target;}
int cr6_ipc_init(cr6_ipc_lane *l,int role){if(!l||(role!=0&&role!=1))return CR6_IPC_INVALID;memset(l,0,sizeof *l);l->role=role;l->target=4;return CR6_IPC_IDLE;}
void cr6_ipc_close(cr6_ipc_lane *l){if(!valid(l)||l->closed)return;int a=in_fd(l),b=out_fd(l),role=l->role;memset(l,0,sizeof *l);l->role=role;l->closed=1;(void)close(a);(void)close(b);}
static int fail(cr6_ipc_lane *l){cr6_ipc_close(l);return CR6_IPC_CLOSED;}
int cr6_ipc_poll(cr6_ipc_lane *m,cr6_ipc_lane *o,int ms){
 if(!valid(m)||!valid(o)||m->role!=0||o->role!=1||ms<0||ms>100)return CR6_IPC_INVALID;
 struct pollfd p[4];cr6_ipc_lane *ls[2]={m,o};
 for(int i=0;i<2;i++){cr6_ipc_lane *l=ls[i];p[2*i]=(struct pollfd){l->closed?-1:in_fd(l),(!l->queued&&!ready(l))?POLLIN:0,0};p[2*i+1]=(struct pollfd){l->closed?-1:out_fd(l),l->queued?POLLOUT:0,0};}
 if(m->closed&&o->closed)return CR6_IPC_CLOSED;
 int rc=poll(p,4,ms);if(rc<0){if(errno==EINTR)return CR6_IPC_IDLE;return CR6_IPC_INVALID;}
 for(int i=0;i<2;i++)if((p[i*2].revents|p[i*2+1].revents)&(POLLERR|POLLHUP|POLLNVAL))cr6_ipc_close(ls[i]);
 return rc?CR6_IPC_PROGRESS:CR6_IPC_IDLE;
}
int cr6_ipc_receive(cr6_ipc_lane *l){
 if(!valid(l))return CR6_IPC_INVALID;
 if(l->closed)return CR6_IPC_CLOSED;
 if(ready(l))return CR6_IPC_READY;
 if(l->queued)return CR6_IPC_BUSY;
 ssize_t n=read(in_fd(l),l->rx+l->used,l->target-l->used);
 if(n<0){if(errno==EAGAIN||errno==EINTR)return CR6_IPC_IDLE;return fail(l);}if(n==0)return fail(l);
 l->used+=(uint32_t)n;
 if(l->used==4&&l->target==4){uint32_t sz=(uint32_t)l->rx[0]|(uint32_t)l->rx[1]<<8|(uint32_t)l->rx[2]<<16|(uint32_t)l->rx[3]<<24;if(!sz||sz>CR6_IPC_MAX)return fail(l);l->target=4+sz;}
 return ready(l)?CR6_IPC_READY:CR6_IPC_PROGRESS;
}
int cr6_ipc_peek(const cr6_ipc_lane *l,const uint8_t **p,size_t *n){if(!valid(l)||!p||!n)return CR6_IPC_INVALID;if(l->closed)return CR6_IPC_CLOSED;if(!ready(l))return CR6_IPC_IDLE;*p=l->rx+4;*n=l->target-4;return CR6_IPC_READY;}
int cr6_ipc_consume(cr6_ipc_lane *l){if(!valid(l))return CR6_IPC_INVALID;if(l->closed)return CR6_IPC_CLOSED;if(!ready(l))return CR6_IPC_INVALID;memset(l->rx,0,l->used);l->used=0;l->target=4;return CR6_IPC_PROGRESS;}
int cr6_ipc_queue(cr6_ipc_lane *l,const uint8_t *p,size_t n){if(!valid(l)||!p||!n||n>CR6_IPC_MAX)return CR6_IPC_INVALID;if(l->closed)return CR6_IPC_CLOSED;if(l->queued)return CR6_IPC_BUSY;memmove(l->tx+4,p,n);for(unsigned i=0;i<4;i++)l->tx[i]=(uint8_t)(n>>(8*i));l->queued=(uint32_t)n+4;return CR6_IPC_PROGRESS;}
int cr6_ipc_flush(cr6_ipc_lane *l){if(!valid(l))return CR6_IPC_INVALID;if(l->closed)return CR6_IPC_CLOSED;if(!l->queued)return CR6_IPC_IDLE;ssize_t n=write(out_fd(l),l->tx,l->queued);if(n<0&&(errno==EAGAIN||errno==EINTR))return CR6_IPC_IDLE;if(n!=(ssize_t)l->queued)return fail(l);memset(l->tx,0,l->queued);l->queued=0;return CR6_IPC_PROGRESS;}
