from __future__ import annotations

from dataclasses import replace
from itertools import count
import os
import signal
import sys
import threading
import time

import pytest

from elpis_fractal_spine.contracts import InferenceExecutionRequest, ModelResidencyRequest
from elpis_fractal_spine.isolated_driver import IsolatedProvider, SupervisorPolicy
from elpis_fractal_spine.isolated_driver.errors import (
    InfrastructureError, LifecycleError, ProtocolError, ProviderError, WorkerTimeout,
)
from elpis_fractal_spine.isolated_driver.supervisor import State
from test_isolated_driver_authority import PACKAGE, PROVIDER, make_wheel


_PROVIDER_ARTIFACT_SEQUENCE = count()


def request():
    return InferenceExecutionRequest("request", "test-model", "in", "out", (1,), None, 1)


def provider(tmp_path, source=PROVIDER, context=None, **policy):
    artifact_root = (
        tmp_path
        / (
            "provider-artifact-"
            + str(next(_PROVIDER_ARTIFACT_SEQUENCE))
        )
    )
    artifact_root.mkdir()
    path, authority = make_wheel(artifact_root, source)
    return IsolatedProvider(authority=authority, wheel_path=path, runtime_context=context or {},
                            policy=SupervisorPolicy(scratch_root=tmp_path, **policy))


def assert_clean(p):
    if p._process is not None:
        assert p._process.poll() is not None
        assert all(pipe.closed for pipe in (p._process.stdin, p._process.stdout, p._process.stderr))
        with pytest.raises(ChildProcessError):
            os.waitpid(p._process.pid, os.WNOHANG)
    assert p._stderr_thread is None or not p._stderr_thread.is_alive()
    assert p.snapshot is None or not p.snapshot.work_root.exists()


def test_lifecycle_two_workers_python_state_and_no_host_import(tmp_path, monkeypatch):
    monkeypatch.setenv("ISOLATED_PARENT_MARKER", "parent")
    monkeypatch.setenv("PYTHONPATH", "/must/not/inherit")
    source = PROVIDER + '''
os.environ['ISOLATED_PARENT_MARKER'] = 'child'
assert 'PYTHONPATH' not in os.environ
assert os.environ['PYTHONNOUSERSITE'] == '1'
assert os.environ['PYTHONDONTWRITEBYTECODE'] == '1'
'''
    assert not any(name == PACKAGE or name.startswith(PACKAGE + ".") for name in sys.modules)
    a = provider(tmp_path, source)
    with pytest.raises(LifecycleError):
        a.execute(request())
    before_threads = set(threading.enumerate())
    b = provider(tmp_path, source)
    try:
        a.start()
        b.start()
        assert a.receipt.child_pid != b.receipt.child_pid != os.getpid()
        lease = a.acquire(ModelResidencyRequest("test-model"))
        with pytest.raises(ProviderError, match="already acquired"):
            a.acquire(ModelResidencyRequest("test-model"))
        assert a.state is State.READY
        assert a.execute(request(), residency=lease).output_payload == (1,)
        assert a.execute(request()).output_payload == (2,)
        assert b.execute(request()).output_payload == (1,)
        a.release(lease)
        a.close()
        a.close()
        assert_clean(a)
        assert b.execute(request()).output_payload == (2,)
        with pytest.raises(LifecycleError):
            a.execute(request())
    finally:
        a.close()
        b.close()
    assert os.environ["ISOLATED_PARENT_MARKER"] == "parent"
    assert not any(name == PACKAGE or name.startswith(PACKAGE + ".") for name in sys.modules)
    assert_clean(b)
    assert set(threading.enumerate()) == before_threads


@pytest.mark.parametrize("source", ["raise RuntimeError('import failed')", PROVIDER + "\ndef factory(context): raise ValueError('factory failed')\n",
                                    PROVIDER + "\ndef factory(context): return object()\n"])
def test_import_factory_and_surface_failure_cleanup(tmp_path, source):
    from elpis_fractal_spine.provider_activation import InferenceDriverRegistry
    registry = InferenceDriverRegistry()
    p = provider(tmp_path, source)
    with pytest.raises(InfrastructureError):
        p.start()
    assert p.state is State.FAILED
    assert PACKAGE not in sys.modules
    assert registry.registered_driver_ids() == ()
    assert_clean(p)
    p.close()
    p.close()


def test_factory_timeout(tmp_path):
    p = provider(tmp_path, PROVIDER + "\ndef factory(context):\n import time; time.sleep(30)\n", startup_timeout=1)
    start = time.monotonic()
    with pytest.raises(WorkerTimeout):
        p.start()
    assert time.monotonic() - start < 5
    assert_clean(p)


def test_rpc_timeout_ignoring_sigterm_requires_kill(tmp_path):
    source = PROVIDER + '''
import signal
signal.signal(signal.SIGTERM, signal.SIG_IGN)
def hung(self, request, *, residency=None):
    import time
    time.sleep(30)
Provider.execute = hung
'''
    p = provider(tmp_path, source, rpc_timeout=0.1, terminate_grace=0.1)
    p.start()
    with pytest.raises(WorkerTimeout):
        p.execute(request())
    assert p._process.returncode == -signal.SIGKILL
    assert_clean(p)
    p.close()


@pytest.mark.parametrize("how", ["os._exit(17)", "os.abort()"])
def test_worker_crash_then_release_is_infrastructure_failure(tmp_path, how):
    source = PROVIDER + f"\ndef broken(self, request, *, residency=None): {how}\nProvider.execute = broken\n"
    p = provider(tmp_path, source).start()
    binding = p.acquire(ModelResidencyRequest("test-model"))
    with pytest.raises(InfrastructureError):
        p.execute(request())
    with pytest.raises(InfrastructureError):
        p.release(binding)
    assert_clean(p)
    p.close()


def test_external_kill(tmp_path):
    p = provider(tmp_path).start()
    os.kill(p._process.pid, signal.SIGKILL)
    p._process.wait(timeout=2)
    with pytest.raises(InfrastructureError):
        p.execute(request())
    assert_clean(p)


def test_idle_worker_death_is_reaped_without_another_rpc(tmp_path):
    p = provider(tmp_path).start()
    os.kill(p._process.pid, signal.SIGKILL)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and p._stderr_thread.is_alive():
        time.sleep(0.01)
    assert p.state is State.FAILED
    assert_clean(p)
    p.close()


def test_rpc_after_idle_crash_joins_observer_before_returning(tmp_path):
    p = provider(tmp_path)
    drain = p._drain_stderr
    observer_finishing = threading.Event()
    def delayed_observer_exit():
        drain()
        observer_finishing.set()
        time.sleep(0.1)
    p._drain_stderr = delayed_observer_exit
    p.start()
    os.kill(p._process.pid, signal.SIGKILL)
    assert observer_finishing.wait(3)
    assert p.state is State.FAILED
    with pytest.raises(InfrastructureError):
        p.execute(request())
    assert_clean(p)
    p.close()


def test_snapshot_disappearance(tmp_path):
    p = provider(tmp_path).start()
    from elpis_fractal_spine.isolated_driver.wheel import remove_snapshot
    remove_snapshot(p.snapshot.package_root)
    with pytest.raises(InfrastructureError, match="snapshot"):
        p.execute(request())
    assert_clean(p)


def test_stderr_flood_is_bounded_and_drained(tmp_path):
    source = PROVIDER + '''
os.write(2, b'x' * 2_000_000)
print('python stdout is diagnostics')
os.write(1, b'native stdout is diagnostics\\n')
'''
    p = provider(tmp_path, source, stderr_bytes=1024).start()
    assert p.execute(request()).status == "OK"
    p.close()
    assert len(p._stderr) <= 1024
    assert "native stdout is diagnostics" in p.stderr_tail
    assert_clean(p)


def test_infinite_stderr_and_factory_hang_cleanup(tmp_path):
    p = provider(tmp_path, "import os\nwhile True: os.write(2, b'x' * 8192)\n", startup_timeout=1)
    with pytest.raises(WorkerTimeout, match="stderr tail") as error:
        p.start()
    assert len(str(error.value)) < 17000
    assert len(p._stderr) <= p.policy.stderr_bytes
    assert_clean(p)


@pytest.mark.parametrize("injection", [
    "os.write(3, b'bad!')",
    "os.write(3, b'\\x00\\x20\\x00\\x00')",
    "os.write(3, b'\\x00\\x00\\x00\\x01{')",
    "from elpis_fractal_spine.isolated_driver.protocol import encode_frame, message; os.write(3, encode_frame(message('execute',999,{'ok':True,'value':None})))",
])
def test_malicious_stdout_frames_cleanup(tmp_path, injection):
    source = PROVIDER + f"\ndef corrupt(self, request, *, residency=None):\n {injection}\n import time; time.sleep(20)\nProvider.execute = corrupt\n"
    p = provider(tmp_path, source, rpc_timeout=1).start()
    with pytest.raises(ProtocolError):
        p.execute(request())
    assert_clean(p)


def test_oversized_provider_result_is_infrastructure_failure(tmp_path):
    source = PROVIDER.replace("(counter,)", "('x' * 2_000_000,)")
    p = provider(tmp_path, source).start()
    with pytest.raises(InfrastructureError):
        p.execute(request())
    assert_clean(p)


def test_invalid_result_type_is_not_ordinary_abstention(tmp_path):
    p = provider(tmp_path, PROVIDER.replace("return InferenceExecutionResult('OK', (counter,), 1, 'synthetic', 'cpu', 'HOT')", "return {'status': 'ABSTAIN'}")).start()
    with pytest.raises(InfrastructureError):
        p.execute(request())
    assert_clean(p)


def test_handshake_mismatch_before_factory_and_cleanup(tmp_path, monkeypatch):
    import elpis_fractal_spine.isolated_driver.supervisor as supervisor
    original = supervisor.read_frame
    def crossed(*args, **kwargs):
        value = original(*args, **kwargs)
        if value["op"] == "start" and value["payload"].get("ok"):
            value["payload"]["value"]["authority_digest"] = "0" * 64
        return value
    monkeypatch.setattr(supervisor, "read_frame", crossed)
    p = provider(tmp_path)
    with pytest.raises(ProtocolError, match="handshake"):
        p.start()
    assert_clean(p)


def test_ambient_target_collision_fails_before_import(tmp_path):
    path, authority = make_wheel(tmp_path)
    from test_isolated_driver_authority import wheel_files, INFO
    files = wheel_files()
    files[INFO + "/entry_points.txt"] = b"[elpis.inference_drivers.v1]\nsynthetic.inference.v1 = json:loads\n"
    path, authority = make_wheel(tmp_path, files=files)
    authority = replace(authority, entry_point_value="json:loads")
    p = IsolatedProvider(authority=authority, wheel_path=path, runtime_context={}, policy=SupervisorPolicy(tmp_path))
    with pytest.raises(InfrastructureError, match="ambient"):
        p.start()
    assert_clean(p)


def test_close_hang_and_close_exception_cleanup(tmp_path):
    for body in ("import time; time.sleep(20)", "raise RuntimeError('close failed')"):
        p = provider(tmp_path, PROVIDER + f"\ndef bad_close(self): {body}\nProvider.close = bad_close\n", shutdown_timeout=0.1).start()
        with pytest.raises(InfrastructureError):
            p.close()
        assert_clean(p)
        p.close()


def test_policy_hard_limits_and_new_close(tmp_path):
    for kwargs in ({"rpc_timeout": float("inf")}, {"startup_timeout": 121}, {"rpc_timeout": 0},
                   {"kill_grace": 11}, {"stderr_bytes": 100000}, {"frame_bytes": 5000000}):
        with pytest.raises((LifecycleError, ProtocolError)):
            SupervisorPolicy(tmp_path, **kwargs)
    p = provider(tmp_path)
    p.close()
    p.close()
    with pytest.raises(LifecycleError):
        p.start()


def test_context_rejected_before_spawn(tmp_path, monkeypatch):
    from elpis_fractal_spine.isolated_driver.errors import ContextError
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("spawned with invalid context"))
    with pytest.raises(ContextError):
        provider(tmp_path, context={"object": object()})


def test_large_bounded_result(tmp_path):
    with provider(tmp_path, PROVIDER.replace("(counter,)", "('x' * 400_000,)")) as p:
        assert p.execute(request()).output_payload == ("x" * 400_000,)


def test_duplicate_and_unsolicited_response_fail_closed(tmp_path):
    source = PROVIDER + '''
from elpis_fractal_spine.isolated_driver.protocol import encode_frame, message
def inject(self, request, *, residency=None):
    # A syntactically valid response to execute request 3, emitted twice.
    value = {'status': 'OK', 'output_payload': [1], 'iteration_count': 1,
             'backend_id': 'synthetic', 'device_id': 'cpu', 'residency_tier': 'HOT'}
    frame = encode_frame(message('execute', 3, {'ok': True, 'value': value}))
    os.write(3, frame + frame)
    import time
    time.sleep(20)
Provider.execute = inject
'''
    p = provider(tmp_path, source).start()
    assert p.execute(request()).output_payload == (1,)
    with pytest.raises(ProtocolError, match="unsolicited|mismatch"):
        p.execute(request())
    assert_clean(p)


def test_snapshot_rechecked_in_worker_before_import(tmp_path, monkeypatch):
    import elpis_fractal_spine.isolated_driver.supervisor as supervisor
    original = supervisor.materialize_wheel
    def tampered(*args, **kwargs):
        snapshot = original(*args, **kwargs)
        code = snapshot.package_root / PACKAGE / '__init__.py'
        code.chmod(0o600)
        code.write_text("print('TAMPERED_CODE_RAN')")
        code.chmod(0o400)
        return snapshot
    monkeypatch.setattr(supervisor, "materialize_wheel", tampered)
    p = provider(tmp_path)
    with pytest.raises(InfrastructureError, match="snapshot"):
        p.start()
    assert 'TAMPERED_CODE_RAN' not in p.stderr_tail
    assert_clean(p)


def test_unrelated_entrypoint_is_not_loaded(tmp_path):
    from test_isolated_driver_authority import wheel_files, INFO
    files = wheel_files(extras={'unrelated_fixture.py': b"raise AssertionError('unrelated import')"})
    files[INFO + '/entry_points.txt'] += b'unrelated.driver = unrelated_fixture:factory\n'
    path, authority = make_wheel(tmp_path, files=files)
    with IsolatedProvider(authority=authority, wheel_path=path, runtime_context={}, policy=SupervisorPolicy(tmp_path)) as p:
        assert p.execute(request()).status == 'OK'
    assert 'unrelated_fixture' not in sys.modules


def test_wheel_hash_failure_creates_no_worker(tmp_path, monkeypatch):
    from elpis_fractal_spine.isolated_driver.errors import WheelError
    import subprocess
    p = provider(tmp_path)
    p.wheel_path.write_bytes(b'changed')
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('spawn before verification'))
    with pytest.raises(WheelError, match='outer wheel'):
        p.start()
    assert_clean(p)
