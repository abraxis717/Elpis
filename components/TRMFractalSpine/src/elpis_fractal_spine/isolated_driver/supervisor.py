"""One fresh process per provider, bounded pipes, explicit lifecycle ownership."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import threading
import time

from ..contracts import (InferenceExecutionRequest, InferenceExecutionResult,
                         ModelResidencyBinding, ModelResidencyRequest)
from ._contracts import from_wire, to_wire
from .authority import WheelAuthority
from .context import CanonicalContext, canonicalize_context
from .errors import (AuthorityError, InfrastructureError, LifecycleError, ProtocolError,
                     ProviderError, SandboxError, WorkerTimeout)
from .protocol import check_response, fields, frame_limit, message, read_frame, write_frame
from .sandbox import SandboxPolicy, SandboxReceipt
from .wheel import Snapshot, materialize_wheel, remove_snapshot


class State(str, Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    READY = "READY"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SupervisorPolicy:
    scratch_root: Path
    sandbox: SandboxPolicy = field(default_factory=SandboxPolicy)
    startup_timeout: float = 20.0
    rpc_timeout: float = 30.0
    shutdown_timeout: float = 3.0
    terminate_grace: float = 1.0
    kill_grace: float = 2.0
    frame_bytes: int = 1024 * 1024
    stderr_bytes: int = 16 * 1024
    retain_snapshot_for_debug: bool = False

    def __post_init__(self) -> None:
        for value, maximum in ((self.startup_timeout, 120), (self.rpc_timeout, 300),
                               (self.shutdown_timeout, 30), (self.terminate_grace, 10),
                               (self.kill_grace, 10)):
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value <= maximum:
                raise LifecycleError("timeout outside finite hard bounds")
        frame_limit(self.frame_bytes)
        if type(self.stderr_bytes) is not int or not 256 <= self.stderr_bytes <= 64 * 1024:
            raise LifecycleError("stderr limit outside hard bounds")
        if type(self.retain_snapshot_for_debug) is not bool or type(self.sandbox) is not SandboxPolicy:
            raise LifecycleError("invalid supervisor policy")
        object.__setattr__(self, "scratch_root", Path(self.scratch_root).resolve())


@dataclass(frozen=True)
class StartupReceipt:
    authority_digest: str
    snapshot_digest: str
    child_pid: int
    context_digest: str
    sandbox: SandboxReceipt


class IsolatedProvider:
    """Acquire/release/execute proxy. Explicit start/close; no finalizer authority.

    Calls are serialized under a lock. Provider errors preserve READY, whereas
    transport, timeout, schema, import and factory failures destroy the worker.
    """

    def __init__(self, *, authority: WheelAuthority, wheel_path: Path,
                 runtime_context: CanonicalContext | object, policy: SupervisorPolicy,
                 model_id: str | None = None) -> None:
        if type(authority) is not WheelAuthority or type(policy) is not SupervisorPolicy:
            raise LifecycleError("typed authority and supervisor policy required")
        self.authority = authority
        self.wheel_path = Path(wheel_path)
        self.context = runtime_context if type(runtime_context) is CanonicalContext else canonicalize_context(runtime_context)
        self.policy = policy
        self.model_id = model_id
        self.state = State.NEW
        self.receipt: StartupReceipt | None = None
        self.snapshot: Snapshot | None = None
        self._process: subprocess.Popen | None = None
        self._sequence = 0
        self._lock = threading.RLock()
        self._stderr_lock = threading.Lock()
        self._stderr = bytearray()
        self._stop = threading.Event()
        self._stderr_thread: threading.Thread | None = None

    @property
    def stderr_tail(self) -> str:
        with self._stderr_lock:
            return bytes(self._stderr).decode("utf-8", errors="replace")

    def _drain_stderr(self) -> None:
        fd = self._process.stderr.fileno()
        with selectors.DefaultSelector() as selector:
            selector.register(fd, selectors.EVENT_READ)
            eof = False
            final_drain = 0
            while True:
                # Reap/clean an idle crash too, without requiring another RPC.
                # Never wait on the RPC lock: its owner may be joining us.
                if eof and self._lock.acquire(blocking=False):
                    try:
                        # Serialize reaping with signaling: the cleanup owner
                        # must not have its live child reaped by this observer
                        # between poll() and process-group signaling.
                        if self.state is State.READY and self._process.poll() is not None:
                            self.state = State.FAILED
                            self._cleanup()
                            return
                    finally:
                        self._lock.release()
                if eof:
                    if self._stop.wait(0.05):
                        return
                    continue
                events = selector.select(0.05)
                if not events:
                    if self._stop.is_set():
                        return
                    continue
                try:
                    chunk = os.read(fd, 8192)
                except BlockingIOError:
                    continue
                except OSError:
                    return
                if not chunk:
                    selector.unregister(fd)
                    eof = True
                    continue
                with self._stderr_lock:
                    self._stderr.extend(chunk)
                    del self._stderr[:-self.policy.stderr_bytes]
                if self._stop.is_set():
                    final_drain += len(chunk)
                    if final_drain >= 64 * 1024:
                        return

    def _cleanup(self) -> None:
        process = self._process
        if process is not None:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=self.policy.terminate_grace)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=self.policy.kill_grace)
                    except subprocess.TimeoutExpired as exc:
                        raise InfrastructureError("worker did not reap after SIGKILL") from exc
            self._stop.set()
            if self._stderr_thread is not None and self._stderr_thread is not threading.current_thread():
                self._stderr_thread.join(timeout=1)
                if self._stderr_thread.is_alive():
                    raise InfrastructureError("stderr drain did not stop")
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        if self.snapshot is not None and not self.policy.retain_snapshot_for_debug:
            try:
                remove_snapshot(self.snapshot.work_root)
            except OSError as exc:
                raise InfrastructureError("private snapshot cleanup failed") from exc

    def _fail(self, error: BaseException) -> None:
        self.state = State.FAILED
        self._cleanup()
        kind = type(error) if isinstance(error, (AuthorityError, InfrastructureError)) else InfrastructureError
        raise kind(f"{error}; child stderr tail: {self.stderr_tail}") from error

    def _exchange(self, operation: str, payload: dict, deadline: float) -> object:
        if self._process.poll() is not None:
            raise InfrastructureError("worker exited unexpectedly")
        if not self.snapshot.package_root.is_dir():
            raise InfrastructureError("worker snapshot disappeared")
        # No unsolicited bytes can precede a new request. Duplicate responses
        # also fail here or by the next sequence/operation check.
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            if selector.select(0):
                raise ProtocolError("unsolicited worker output/EOF")
        self._sequence += 1
        write_frame(self._process.stdin.fileno(), message(operation, self._sequence, payload),
                    deadline=deadline, max_bytes=self.policy.frame_bytes)
        response = read_frame(self._process.stdout.fileno(), deadline=deadline,
                              max_bytes=self.policy.frame_bytes)
        envelope = check_response(response, operation, self._sequence)
        if not envelope["ok"]:
            error = envelope["error"]
            if error["category"] == "provider" and operation in ("acquire", "execute", "release"):
                raise ProviderError(error["message"])
            kind = SandboxError if error["category"] == "sandbox" else InfrastructureError
            raise kind(error["message"])
        return envelope["value"]

    def start(self) -> IsolatedProvider:
        with self._lock:
            if self.state is not State.NEW:
                raise LifecycleError("start requires NEW state")
            if os.name != "posix":
                raise SandboxError("R0 pipe supervisor requires POSIX")
            self.state = State.STARTING
            try:
                self.snapshot = materialize_wheel(self.wheel_path, self.authority,
                                                   scratch_root=self.policy.scratch_root)
                deadline = time.monotonic() + self.policy.startup_timeout
                # -I ignores PYTHON* variables and cwd. Only the trusted core
                # source root is deliberately added; plugin path is NOT here.
                core_root = str(Path(__file__).resolve().parents[2])
                import elpis.canonical_identity as canonical_identity
                canonical_identity_file = str(
                    Path(canonical_identity.__file__).resolve()
                )
                bootstrap = (
                    "import sys,runpy,types,importlib.util;"
                    "sys.dont_write_bytecode=True;"
                    "pkg=types.ModuleType('elpis');"
                    "pkg.__path__=[];"
                    "sys.modules['elpis']=pkg;"
                    f"spec=importlib.util.spec_from_file_location('elpis.canonical_identity',{canonical_identity_file!r});"
                    "mod=importlib.util.module_from_spec(spec);"
                    "sys.modules['elpis.canonical_identity']=mod;"
                    "spec.loader.exec_module(mod);"
                    f"sys.path.insert(0,{core_root!r});"
                    "runpy.run_module('elpis_fractal_spine.isolated_driver._worker',run_name='__main__')"
                )
                env = {"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                       "PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                       "HOME": str(self.snapshot.work_root / "cwd"),
                       "TMPDIR": str(self.snapshot.work_root / "cwd"),
                       "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
                self._process = subprocess.Popen(
                    [sys.executable, "-I", "-B", "-c", bootstrap], shell=False,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    close_fds=True, cwd=self.snapshot.work_root / "cwd", env=env,
                    start_new_session=True, bufsize=0,
                )
                for pipe in (self._process.stdin, self._process.stdout, self._process.stderr):
                    os.set_blocking(pipe.fileno(), False)
                self._stderr_thread = threading.Thread(target=self._drain_stderr,
                                                       name=f"elpis-stderr-{self._process.pid}")
                self._stderr_thread.start()
                handshake = self._exchange("start", {
                    "authority": asdict(self.authority), "snapshot_root": str(self.snapshot.package_root),
                    "snapshot_digest": self.snapshot.digest, "members": self.snapshot.members,
                    "sandbox": asdict(self.policy.sandbox), "frame_bytes": self.policy.frame_bytes,
                }, deadline)
                fields(handshake, {"authority", "authority_digest", "snapshot_digest", "snapshot_root", "pid", "sandbox"})
                expected = {"authority": asdict(self.authority), "authority_digest": self.authority.digest,
                            "snapshot_digest": self.snapshot.digest, "snapshot_root": str(self.snapshot.package_root),
                            "pid": self._process.pid}
                if any(handshake[key] != value for key, value in expected.items()):
                    raise ProtocolError("startup handshake identity mismatch")
                sandbox = fields(handshake["sandbox"], {"no_new_privs", "seccomp", "core_bytes", "address_space_bytes", "file_descriptors", "cpu_seconds"})
                if any(type(sandbox[key]) is not bool for key in ("no_new_privs", "seccomp")) or any(type(sandbox[key]) is not int for key in ("core_bytes", "address_space_bytes", "file_descriptors", "cpu_seconds")):
                    raise ProtocolError("invalid sandbox receipt types")
                if sys.platform == "linux" and sandbox["no_new_privs"] is not True or self.policy.sandbox.require_seccomp and sandbox["seccomp"] is not True:
                    raise SandboxError("worker did not establish required confinement")
                if sandbox["core_bytes"] != 0 or any(not 0 < sandbox[key] <= getattr(self.policy.sandbox, key) for key in ("address_space_bytes", "file_descriptors", "cpu_seconds")):
                    raise SandboxError("worker resource receipt mismatch")
                value = self._exchange("factory", {"context": self.context.decode(), "context_digest": self.context.digest}, deadline)
                if value is not None:
                    raise ProtocolError("factory response must be null")
                self.receipt = StartupReceipt(self.authority.digest, self.snapshot.digest, self._process.pid,
                                              self.context.digest, SandboxReceipt(**sandbox))
                self.state = State.READY
                return self
            except BaseException as exc:  # Own/clean process even on caller interruption.
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    self.state = State.FAILED
                    self._cleanup()
                    raise
                self._fail(exc)

    def _ready(self) -> None:
        if self.state is State.FAILED:
            # An idle-crash observer may have just released the lock after
            # cleaning its own process. Join it before returning failure to a
            # caller; FAILED alone does not prove the helper thread has exited.
            self._cleanup()
            raise InfrastructureError(f"worker is FAILED; child stderr tail: {self.stderr_tail}")
        if self.state is not State.READY:
            raise LifecycleError(f"provider operation requires READY, got {self.state.value}")

    def _model(self, model_id: str) -> None:
        if self.model_id is not None and model_id != self.model_id:
            raise LifecycleError("request model differs from bound model port")

    def _rpc(self, operation: str, payload: dict, result_type: type | None) -> object:
        try:
            value = self._exchange(operation, payload, time.monotonic() + self.policy.rpc_timeout)
            if result_type is None:
                if value is not None:
                    raise ProtocolError("release response must be null")
                return None
            return from_wire(result_type, value)
        except ProviderError:
            raise
        except (InfrastructureError, OSError) as exc:
            self._fail(exc)

    def acquire(self, request: ModelResidencyRequest) -> ModelResidencyBinding:
        with self._lock:
            self._ready()
            wire = to_wire(request, ModelResidencyRequest)
            self._model(request.model_id)
            result = self._rpc("acquire", {"request": wire}, ModelResidencyBinding)
            if result.model_id != request.model_id:
                self._fail(ProtocolError("binding model identity mismatch"))
            return result

    def execute(self, request: InferenceExecutionRequest, *, residency: ModelResidencyBinding | None = None) -> InferenceExecutionResult:
        with self._lock:
            self._ready()
            wire = to_wire(request, InferenceExecutionRequest)
            binding = None if residency is None else to_wire(residency, ModelResidencyBinding)
            self._model(request.model_id)
            if residency is not None and residency.model_id != request.model_id:
                raise LifecycleError("residency model differs from execution model")
            return self._rpc("execute", {"request": wire, "residency": binding}, InferenceExecutionResult)

    def release(self, binding: ModelResidencyBinding) -> None:
        with self._lock:
            self._ready()
            wire = to_wire(binding, ModelResidencyBinding)
            self._model(binding.model_id)
            self._rpc("release", {"binding": wire}, None)

    def close(self) -> None:
        with self._lock:
            if self.state is State.CLOSED:
                return
            if self.state in (State.NEW, State.FAILED):
                self._cleanup()
                self.state = State.CLOSED
                return
            if self.state is not State.READY:
                raise LifecycleError("close requires READY, NEW or FAILED state")
            self.state = State.CLOSING
            try:
                deadline = time.monotonic() + self.policy.shutdown_timeout
                if self._exchange("close", {}, deadline) is not None:
                    raise ProtocolError("close response must be null")
                try:
                    self._process.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired as exc:
                    raise WorkerTimeout("worker shutdown timed out") from exc
                if self._process.returncode != 0:
                    raise InfrastructureError("worker failed during shutdown")
                # Reject trailing/duplicate frames even on the final operation.
                if os.read(self._process.stdout.fileno(), 1):
                    raise ProtocolError("trailing output after shutdown")
                self._cleanup()
                self.state = State.CLOSED
            except (InfrastructureError, OSError) as exc:
                self._fail(exc)

    def __enter__(self) -> IsolatedProvider:
        return self.start() if self.state is State.NEW else self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
