"""Linux R0 syscall restrictions, not a filesystem/read or hostile-code jail."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import errno
import os
import resource
import sys

from .errors import SandboxError

KILL_NETWORK_SYSCALLS = (
    "socket", "socketcall", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "sendto", "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg",
)
# Network attempts kill the process. Other denials return EPERM, except clone3
# -> ENOSYS so libc can fall back to filtered clone. KILL also gives behavioral
# attribution when an outer sandbox already returns EPERM for networking.
DENIED_SYSCALLS = KILL_NETWORK_SYSCALLS + (
    "execve", "execveat", "fork", "vfork", "setsid", "setpgid",
    "ptrace", "process_vm_readv", "process_vm_writev", "pidfd_open", "pidfd_getfd",
    "pidfd_send_signal", "kill", "tkill", "rt_sigqueueinfo", "rt_tgsigqueueinfo",
    "mount", "umount", "umount2", "ioctl", "setrlimit",
    "setns", "unshare", "bpf", "perf_event_open", "keyctl", "add_key",
    "request_key", "reboot", "kexec_load", "kexec_file_load", "init_module",
    "finit_module", "delete_module", "swapon", "swapoff", "userfaultfd",
    "openat2", "creat", "truncate", "truncate64", "ftruncate", "ftruncate64",
    "unlink", "unlinkat", "rename", "renameat", "renameat2", "mkdir", "mkdirat",
    "rmdir", "link", "linkat", "symlink", "symlinkat", "chmod", "fchmod",
    "fchmodat", "fchmodat2", "chown", "fchown", "lchown", "fchownat",
    "chown32", "fchown32", "lchown32", "mknod", "mknodat", "utime", "utimes",
    "futimesat", "utimensat", "setxattr", "lsetxattr", "fsetxattr",
    "removexattr", "lremovexattr", "fremovexattr", "fallocate",
    "io_uring_setup", "io_uring_enter", "io_uring_register", "open_by_handle_at",
    "name_to_handle_at", "fsopen", "fsconfig", "fsmount", "move_mount",
    "open_tree", "mount_setattr", "quotactl", "chroot", "acct",
)


@dataclass(frozen=True)
class SandboxPolicy:
    require_seccomp: bool = True
    address_space_bytes: int = 2 * 1024**3
    file_descriptors: int = 64
    cpu_seconds: int = 300

    def __post_init__(self) -> None:
        if type(self.require_seccomp) is not bool:
            raise SandboxError("require_seccomp must be boolean")
        for value, low, high in ((self.address_space_bytes, 64 * 1024**2, 64 * 1024**3),
                                 (self.file_descriptors, 16, 256), (self.cpu_seconds, 1, 3600)):
            if type(value) is not int or not low <= value <= high:
                raise SandboxError("resource limit outside hard bounds")


@dataclass(frozen=True)
class SandboxReceipt:
    no_new_privs: bool
    seccomp: bool
    core_bytes: int
    address_space_bytes: int
    file_descriptors: int
    cpu_seconds: int


def _load_seccomp() -> ctypes.CDLL:
    # No ctypes.util.find_library subprocess or external ldconfig invocation.
    try:
        return ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise SandboxError("libseccomp.so.2 is unavailable") from exc


def seccomp_available() -> bool:
    if sys.platform != "linux":
        return False
    try:
        _load_seccomp()
        return True
    except SandboxError:
        return False


class _Comparison(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def _filter() -> None:
    if os.uname().machine not in ("x86_64", "aarch64"):
        raise SandboxError("R0 syscall argument policy supports x86_64/aarch64 only")
    lib = _load_seccomp()
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                         ctypes.c_uint, ctypes.POINTER(_Comparison)]
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    lib.seccomp_attr_set.restype = ctypes.c_int
    ctx = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW; bad architectures default KILL.
    if not ctx:
        raise SandboxError("seccomp_init failed")

    def deny(name: str, comparison: _Comparison | None = None, error: int = errno.EPERM) -> None:
        number = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
        if number == -1:  # Not present on this architecture/libseccomp database.
            return
        args = ctypes.pointer(comparison) if comparison is not None else None
        action = 0x80000000 if name in KILL_NETWORK_SYSCALLS else 0x00050000 | error
        if lib.seccomp_rule_add_array(ctx, action, number, int(comparison is not None), args) < 0:
            raise SandboxError(f"seccomp rule failed: {name}")

    try:
        # TSYNC includes trusted bootstrap threads (e.g. already-loaded BLAS).
        if lib.seccomp_attr_set(ctx, 4, 1) != 0:
            raise SandboxError("seccomp TSYNC unavailable")
        for name in DENIED_SYSCALLS:
            deny(name)
        deny("clone3", error=errno.ENOSYS)
        # CLONE_THREAD must be set: compute threads allowed, new processes denied.
        deny("clone", _Comparison(0, 7, 0x00010000, 0))  # MASKED_EQ
        deny("tgkill", _Comparison(0, 1, os.getpid(), 0))  # NE: only own thread group
        deny("prlimit64", _Comparison(2, 1, 0, 0))  # NE: no resource setters
        for syscall, argument in (("open", 1), ("openat", 2)):
            for flag in (os.O_WRONLY, os.O_RDWR, os.O_CREAT, os.O_TRUNC, os.O_APPEND, 0x400000):
                deny(syscall, _Comparison(argument, 7, flag, flag))
        if lib.seccomp_load(ctx) != 0:
            raise SandboxError("seccomp_load failed")
    finally:
        lib.seccomp_release(ctx)


def apply_sandbox(policy: SandboxPolicy) -> SandboxReceipt:
    """Worker-only, irreversible. Must precede snapshot import."""
    if sys.platform != "linux" and policy.require_seccomp:
        raise SandboxError("required Linux seccomp sandbox unavailable")
    try:
        def limit(kind: int, target: int) -> int:
            _, hard = resource.getrlimit(kind)
            actual = target if hard == resource.RLIM_INFINITY else min(target, hard)
            resource.setrlimit(kind, (actual, actual))
            return actual

        core = limit(resource.RLIMIT_CORE, 0)
        address = limit(resource.RLIMIT_AS, policy.address_space_bytes)
        descriptors = limit(resource.RLIMIT_NOFILE, policy.file_descriptors)
        cpu = limit(resource.RLIMIT_CPU, policy.cpu_seconds)
        nnp = False
        active = False
        if sys.platform == "linux":
            libc = ctypes.CDLL(None, use_errno=True)
            libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
            libc.prctl.restype = ctypes.c_int
            if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
                raise SandboxError("PR_SET_NO_NEW_PRIVS failed")
            nnp = libc.prctl(39, 0, 0, 0, 0) == 1
            if not nnp:
                raise SandboxError("no_new_privs verification failed")
            if policy.require_seccomp or seccomp_available():
                _filter()
                active = True
        return SandboxReceipt(nnp, active, core, address, descriptors, cpu)
    except (OSError, ValueError) as exc:
        raise SandboxError("resource/confinement setup failed") from exc
