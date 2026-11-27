/* DEV CR6 pipe-capability guard. Derived from sealed CR5 host_guard.c; no probe or bypass. */
#define _GNU_SOURCE
#include <errno.h>
#include <dirent.h>
#include <stdint.h>
#include <inttypes.h>
#include <fcntl.h>
#include <limits.h>
#include <math.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdio.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"CHECK_FAIL:%s:%d:%s\n",__func__,__LINE__,#x); _exit(125); } } while(0)
#define ALLOW(n) BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_##n,0,1), BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW)
#define DENY BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|(EPERM&SECCOMP_RET_DATA))

/* All failure messages before arming require both anonymous diagnostic pipes. */
static int pipe_fd_mode(int fd,int mode,int protocol) {
    char path[32],link[64]; struct stat st;
    int n=snprintf(path,sizeof path,"/proc/self/fd/%d",fd);
    if(n<=0 || (size_t)n>=sizeof path || fstat(fd,&st) || !S_ISFIFO(st.st_mode)) return 0;
    int flags=fcntl(fd,F_GETFL); if(flags<0 || (flags&O_ACCMODE)!=mode) return 0;
    if(protocol && (!(flags&O_NONBLOCK) || (flags&(O_DIRECT|O_ASYNC)) || fpathconf(fd,_PC_PIPE_BUF)<2312))return 0;
    ssize_t m=readlink(path,link,sizeof link-1);
    if(m<8 || (size_t)m>=sizeof link-1) return 0;
    link[m]=0; if(strncmp(link,"pipe:[",6) || link[m-1]!=']') return 0;
    for(ssize_t i=6;i<m-1;i++) if(link[i]<'0'||link[i]>'9') return 0;
    return 1;
}
static int uint_line(const char *s,uint64_t *out) {
    uint64_t n=0; if(*s<'0'||*s>'9') return 0;
    do { unsigned d=(unsigned)(*s++-'0'); if(n>(UINT64_MAX-d)/10)return 0; n=n*10+d; } while(*s>='0'&&*s<='9');
    if(strcmp(s,"\n")!=0) return 0;
    *out=n;return 1;
}
static int read_number(const char *path,uint64_t *out){
    FILE *f=fopen(path,"r");if(!f)return 0;char b[64];
    int ok=fgets(b,sizeof b,f)!=NULL && uint_line(b,out) && fgetc(f)==EOF && !ferror(f);
    if(fclose(f)!=0)return 0;
    return ok;
}
static int cgroup_path(char *out,size_t cap){
    FILE *f=fopen("/proc/self/cgroup","r");if(!f)return 0;
    char b[4096];int ok=fgets(b,sizeof b,f)!=NULL && fgetc(f)==EOF && !ferror(f);
    if(fclose(f)!=0||!ok||strncmp(b,"0::/",4))return 0;
    char *nl=strchr(b,'\n');if(!nl || nl[1])return 0;*nl=0;
    /* Kernel-derived v2 path; refuse ambiguous/escaped and parent components. */
    const char *s=b+3;for(const char *q=s;*q;q++)if((unsigned char)*q<32||*q=='\\')return 0;
    if(strstr(s,"/../")||strstr(s,"/./")||!strcmp(s,"/..")||!strcmp(s,"/.")||strstr(s,"//"))return 0;
    size_t len=strlen(s);if(len>=3&&!strcmp(s+len-3,"/.."))return 0;if(len>=2&&!strcmp(s+len-2,"/."))return 0;
    int n=snprintf(out,cap,"/sys/fs/cgroup%s",s);return n>0&&(size_t)n<cap;
}
static int resource_bounds(void){
    char base[4096],p[4160];uint64_t mem,swap,used;
    if(!cgroup_path(base,sizeof base))return 0;
    int n=snprintf(p,sizeof p,"%s/memory.max",base);if(n<=0||(size_t)n>=sizeof p||!read_number(p,&mem))return 0;
    n=snprintf(p,sizeof p,"%s/memory.swap.max",base);if(n<=0||(size_t)n>=sizeof p||!read_number(p,&swap))return 0;
    n=snprintf(p,sizeof p,"%s/memory.swap.current",base);if(n<=0||(size_t)n>=sizeof p||!read_number(p,&used))return 0;
    if(mem<128ULL*1024*1024 || mem>4294967296ULL || swap || used)return 0;
    FILE *f=fopen("/proc/swaps","r");if(!f)return 0;char b[4096];
    int ok=fgets(b,sizeof b,f)!=NULL&&strchr(b,'\n')&&fgetc(f)==EOF&&!ferror(f);
    if(fclose(f)!=0)return 0;
    return ok;
}
static int one_task(void){
    DIR *d=opendir("/proc/self/task");if(!d)return 0;unsigned n=0;struct dirent *e;errno=0;
    while((e=readdir(d))!=NULL)if(strcmp(e->d_name,".")&&strcmp(e->d_name,".."))n++;
    int ok=errno==0&&n==1;if(closedir(d)!=0)return 0;return ok;
}
static int no_caps(void){
    FILE *f=fopen("/proc/self/status","r");if(!f)return 0;char b[4096];unsigned seen=0;int ok=1;
    while(fgets(b,sizeof b,f)){
        if(!strncmp(b,"CapEff:\t",8)||!strncmp(b,"CapPrm:\t",8)){
            seen++;const char *v=b+8;if(strcmp(v,"0000000000000000\n"))ok=0;
        }
    }
    if(ferror(f))ok=0;
    if(fclose(f)!=0)return 0;
    return ok&&seen==2;
}

static int pipes_distinct(void){
    struct stat s[6];
    for(int fd=1;fd<=6;fd++){
        int mode=(fd==3||fd==5)?O_RDONLY:O_WRONLY;
        if(!pipe_fd_mode(fd,mode,fd>=3)||fstat(fd,&s[fd-1]))return 0;
        for(int j=1;j<fd;j++)if(s[j-1].st_dev==s[fd-1].st_dev&&s[j-1].st_ino==s[fd-1].st_ino)return 0;
    }
    return 1;
}
void cr6_ipc_guard(void){
    if(!pipe_fd_mode(1,O_WRONLY,0)||!pipe_fd_mode(2,O_WRONLY,0)) _exit(125);
    setvbuf(stdout,NULL,_IONBF,0);setvbuf(stderr,NULL,_IONBF,0);
    CHECK(getuid()!=0 && geteuid()==getuid() && getegid()==getgid() && no_caps());
    CHECK(one_task());CHECK(resource_bounds());CHECK(pipes_distinct());
    struct sigaction sa={0};sa.sa_handler=SIG_IGN;CHECK(sigemptyset(&sa.sa_mask)==0);CHECK(sigaction(SIGPIPE,&sa,NULL)==0);
    /* The only pre-existing mappings admitted are private; otherwise a later
     * mprotect could turn a shared file mapping into a write path. */
    FILE *maps=fopen("/proc/self/maps","r");CHECK(maps!=NULL);
    char line[4096],perms[5];while(fgets(line,sizeof line,maps)){
        CHECK(sscanf(line,"%*s %4s",perms)==1 && perms[3]=='p');
    }CHECK(!ferror(maps));CHECK(fclose(maps)==0);
    struct stat a,b; CHECK(fstat(1,&a)==0 && fstat(2,&b)==0 && S_ISFIFO(a.st_mode) && S_ISFIFO(b.st_mode));
    struct rlimit lim={0,0},got; CHECK(setrlimit(RLIMIT_CORE,&lim)==0);
    CHECK(getrlimit(RLIMIT_CORE,&got)==0 && !got.rlim_cur && !got.rlim_max);
    CHECK(setrlimit(RLIMIT_FSIZE,&lim)==0);
    CHECK(getrlimit(RLIMIT_FSIZE,&got)==0 && !got.rlim_cur && !got.rlim_max);
    CHECK(prctl(PR_SET_DUMPABLE,0,0,0,0)==0 && prctl(PR_GET_DUMPABLE,0,0,0,0)==0);
    CHECK(syscall(SYS_close_range,7u,UINT_MAX,0u)==0);
    CHECK(close(0)==0 || errno==EBADF);
    int abi=(int)syscall(SYS_landlock_create_ruleset,NULL,0,LANDLOCK_CREATE_RULESET_VERSION);
    CHECK(abi>=5);
    /* Deny all handled filesystem mutations; reads are not a Landlock authority. */
    struct landlock_ruleset_attr attr={.handled_access_fs=0xfff2ULL & ~(1ULL<<2) & ~(1ULL<<3)};
    /* 0xfff2: WRITE_FILE and bits 4..15 (remove/make/refer/truncate/ioctl). */
    int fd=(int)syscall(SYS_landlock_create_ruleset,&attr,sizeof(attr),0); CHECK(fd>=0);
    CHECK(prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)==0);
    CHECK(syscall(SYS_landlock_restrict_self,fd,0)==0); CHECK(close(fd)==0);
    struct sock_filter ins[]={
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,arch)),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,AUDIT_ARCH_X86_64,1,0),
        BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr)),
        /* Exact descriptor capabilities: no open/dup/pipe/socket after arming. */
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_read,0,5),
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0])),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,3,2,0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,5,1,0),
        DENY,BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_write,0,7),
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0])),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,1,4,0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,2,3,0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,4,2,0),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,6,1,0),
        DENY,BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),
        /* poll with at most four descriptors and a bounded nonnegative wait. */
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_poll,0,6),
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[1])),
        BPF_JUMP(BPF_JMP|BPF_JGT|BPF_K,4,3,0),
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[2])),
        BPF_JUMP(BPF_JMP|BPF_JGT|BPF_K,100,1,0),
        BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),DENY,
        /* mmap only anonymous/private: no writable backing or shared mapping. */
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_mmap,0,5),
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[3])),
        BPF_STMT(BPF_ALU|BPF_AND|BPF_K,MAP_SHARED|MAP_PRIVATE|MAP_ANONYMOUS),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,MAP_PRIVATE|MAP_ANONYMOUS,1,0),
        DENY,BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),
        ALLOW(brk),ALLOW(munmap),ALLOW(mprotect),ALLOW(mremap),ALLOW(madvise),
        ALLOW(futex),ALLOW(clock_gettime),ALLOW(gettimeofday),ALLOW(getrandom),
        ALLOW(fstat),ALLOW(newfstatat),ALLOW(close),ALLOW(rt_sigreturn),
        ALLOW(getpid),ALLOW(gettid),ALLOW(sigaltstack),ALLOW(sched_getaffinity),
        ALLOW(rt_sigaction),ALLOW(rt_sigprocmask),ALLOW(sched_yield),
        /* Resume kernel-maintained restart blocks (e.g. bounded poll after SIGSTOP/SIGCONT). */
        ALLOW(restart_syscall),
        ALLOW(exit),ALLOW(exit_group),DENY
    };
    struct sock_fprog prog={(unsigned short)(sizeof ins/sizeof ins[0]),ins};
    CHECK(prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&prog)==0);
    printf("GUARD_ARMED=PASS ABI=%d\n",abi); fflush(stdout);
}
