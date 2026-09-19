from __future__ import annotations

import errno
import os
import signal
import sys

import pytest

from elpis_fractal_spine.isolated_driver import SupervisorPolicy, SandboxPolicy
from elpis_fractal_spine.isolated_driver.errors import InfrastructureError, SandboxError
from elpis_fractal_spine.isolated_driver.sandbox import seccomp_available
from test_isolated_driver_authority import PROVIDER
from test_isolated_driver_supervisor import provider, request, assert_clean

pytestmark = pytest.mark.skipif(sys.platform != "linux" or not seccomp_available(),
                                reason="Linux libseccomp unavailable: confinement not qualified here")


def attempt_source(body):
    return PROVIDER + '''
import errno
def attempt():
''' + "".join("    " + line + "\n" for line in body.splitlines()) + '''
def run(self, request, *, residency=None):
    try:
        attempt()
    except OSError as exc:
        result = exc.errno
    else:
        result = 0
    return InferenceExecutionResult('OK', (result,), 1, 'sandbox', 'cpu', 'HOT')
Provider.execute = run
'''


@pytest.mark.parametrize("body", [
    "import socket\nsocket.socket(socket.AF_INET, socket.SOCK_STREAM)",
    "import socket\nsocket.socket(socket.AF_INET6, socket.SOCK_STREAM)",
    "import socket\nsocket.socketpair()",
])
def test_network_filter_kills_worker_independently_of_outer_eperm(tmp_path, body):
    p = provider(tmp_path, attempt_source(body)).start()
    assert p.receipt.sandbox.seccomp is True
    with pytest.raises(InfrastructureError):
        p.execute(request())
    # An inherited EPERM-only filter cannot make this test pass. Removing this
    # subsystem's socket rule lets the plugin return normally, failing the test.
    assert p._process.returncode == -signal.SIGSYS
    assert_clean(p)
    p.close()


@pytest.mark.parametrize("body", [
    "import subprocess\nsubprocess.run(['/usr/bin/true'], check=True)",
    "os.execve('/usr/bin/true', ['/usr/bin/true'], {})",
    "os.fork()",
    "os.mkdir('denied-directory')",
    "os.open('denied-file', os.O_WRONLY | os.O_CREAT, 0o600)",
    "os.open('denied-file', os.O_RDWR | os.O_CREAT, 0o600)",
    "os.symlink('/tmp', 'denied-symlink')",
])
def test_kernel_exec_process_and_file_denials(tmp_path, body):
    p = provider(tmp_path, attempt_source(body)).start()
    try:
        assert p.receipt.sandbox.seccomp is True
        assert p.receipt.sandbox.no_new_privs is True
        assert p.execute(request()).output_payload == (errno.EPERM,)
    finally:
        p.close()
    assert_clean(p)


@pytest.mark.parametrize("operation", ["open", "truncate", "unlink", "rename", "chmod", "utime"])
def test_existing_file_mutation_denied(tmp_path, operation):
    target = tmp_path / "host-owned.txt"
    target.write_text("original")
    body = {
        "open": f"open({str(target)!r}, 'w').write('altered')",
        "truncate": f"os.truncate({str(target)!r}, 0)",
        "unlink": f"os.unlink({str(target)!r})",
        "rename": f"os.rename({str(target)!r}, {str(target) + '.renamed'!r})",
        "chmod": f"os.chmod({str(target)!r}, 0o777)",
        "utime": f"os.utime({str(target)!r}, (0, 0))",
    }[operation]
    with provider(tmp_path, attempt_source(body)) as p:
        assert p.execute(request()).output_payload == (errno.EPERM,)
    assert target.read_text() == "original"


def test_file_write_denied_already_during_import(tmp_path):
    target = tmp_path / "import-side-effect"
    p = provider(tmp_path, f"open({str(target)!r}, 'w').write('bad')\n" + PROVIDER)
    with pytest.raises(InfrastructureError, match="PermissionError"):
        p.start()
    assert not target.exists()
    assert_clean(p)


def test_readonly_mmap_threads_and_effective_resource_limits(tmp_path):
    target = tmp_path / "model.bin"
    target.write_bytes(b"read-only-model-bytes")
    source = PROVIDER + f'''
import mmap, threading, resource, ctypes
with open({str(target)!r}, 'rb') as handle:
    with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        assert mapped[:] == b'read-only-model-bytes'
values = []
threads = [threading.Thread(target=lambda: values.append(sum(range(10000)))) for _ in range(4)]
for thread in threads: thread.start()
for thread in threads: thread.join()
assert values == [49995000] * 4
assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
assert resource.getrlimit(resource.RLIMIT_NOFILE) == (64, 64)
assert resource.getrlimit(resource.RLIMIT_AS) == (2147483648, 2147483648)
assert resource.getrlimit(resource.RLIMIT_CPU) == (300, 300)
assert ctypes.CDLL(None).prctl(39, 0, 0, 0, 0) == 1
'''
    with provider(tmp_path, source) as p:
        assert p.execute(request()).output_payload == (1,)
        assert p.receipt.sandbox.core_bytes == 0


def test_missing_required_libseccomp_fails_before_import(tmp_path, monkeypatch):
    import elpis_fractal_spine.isolated_driver.supervisor as supervisor
    real_popen = supervisor.subprocess.Popen
    def without_library(args, **kwargs):
        args = list(args)
        injection = ("import elpis_fractal_spine.isolated_driver.sandbox as sb;"
                     "sb._load_seccomp=lambda:(_ for _ in ()).throw(sb.SandboxError('libseccomp unavailable in test'));"
                     "runpy.run_module")
        args[-1] = args[-1].replace("runpy.run_module", injection)
        return real_popen(args, **kwargs)
    monkeypatch.setattr(supervisor.subprocess, "Popen", without_library)
    p = provider(tmp_path, "print('PLUGIN_IMPORTED')\n" + PROVIDER)
    with pytest.raises(SandboxError, match="unavailable"):
        p.start()
    assert "PLUGIN_IMPORTED" not in p.stderr_tail
    assert_clean(p)


def test_resource_policy_hard_ceilings():
    for kwargs in ({"address_space_bytes": 65 * 1024**3}, {"file_descriptors": 257},
                   {"cpu_seconds": 3601}, {"require_seccomp": "yes"}):
        with pytest.raises(SandboxError):
            SandboxPolicy(**kwargs)
