"""Trusted fresh-interpreter bootstrap. Never run in the Elpis parent."""
from __future__ import annotations

from dataclasses import asdict
import importlib
import importlib.machinery
import os
from pathlib import Path
import sys
import time

from ..contracts import (InferenceExecutionRequest, InferenceExecutionResult,
                         ModelResidencyBinding, ModelResidencyRequest)
from ._contracts import from_wire, to_wire
from .authority import WheelAuthority
from .context import CanonicalContext, canonical_bytes
from .errors import ProtocolError, SandboxError
from .protocol import fields, message, read_frame, write_frame
from .sandbox import SandboxPolicy, apply_sandbox
from .wheel import recheck_snapshot


def _inside(spec: object, root: Path) -> bool:
    origin = getattr(spec, "origin", None)
    locations = getattr(spec, "submodule_search_locations", None)
    return (type(origin) is str and Path(origin).resolve().is_relative_to(root)
            and (locations is None or all(Path(p).resolve().is_relative_to(root) for p in locations)))


def _load_factory(authority: WheelAuthority, root: Path) -> object:
    module_name, attribute = authority.entry_point_value.split(":")
    top = module_name.split(".")[0]
    # Refuse an ambient/cache collision BEFORE executing any target code.
    if top in sys.modules:
        raise ProtocolError("entry-point top-level module is already ambient")
    spec = importlib.machinery.PathFinder.find_spec(top, [str(root)])
    if not _inside(spec, root):
        raise ProtocolError("entry-point package is not in verified snapshot")
    sys.path.insert(0, str(root))
    module = importlib.import_module(module_name)
    for name in (top, module_name):
        if not _inside(getattr(sys.modules.get(name), "__spec__", None), root):
            raise ProtocolError("loaded entry-point module escaped snapshot")
    factory = module
    for part in attribute.split("."):
        factory = getattr(factory, part)
    if not callable(factory):
        raise ProtocolError("entry point is not callable")
    return factory


def main() -> None:
    # Preserve the actual protocol pipe; Python prints and native stdout go to
    # bounded stderr. A malicious native plugin can still corrupt fd 3: fatal.
    output = os.dup(1)
    os.dup2(2, 1)
    os.set_blocking(0, False)
    os.set_blocking(output, False)
    sequence = 0
    operation = "start"
    frame_bytes = 1024 * 1024
    provider = None
    stage = "start"
    try:
        # Trusted startup config is itself framed/bounded. Parent owns deadlines.
        boot = read_frame(0, deadline=time.monotonic() + 300, max_bytes=4 * 1024 * 1024)
        sequence = boot["id"]
        if boot["op"] != "start" or sequence != 1:
            raise ProtocolError("expected start request 1")
        config = fields(boot["payload"], {"authority", "snapshot_root", "snapshot_digest",
                                         "members", "sandbox", "frame_bytes"})
        authority = WheelAuthority(**config["authority"])
        root = Path(config["snapshot_root"]).resolve(strict=True)
        frame_bytes = config["frame_bytes"]
        receipt = apply_sandbox(SandboxPolicy(**config["sandbox"]))
        recheck_snapshot(root, config["members"], config["snapshot_digest"])
        identity = {"authority": asdict(authority), "authority_digest": authority.digest,
                    "snapshot_digest": config["snapshot_digest"], "snapshot_root": str(root),
                    "pid": os.getpid(), "sandbox": asdict(receipt)}
        write_frame(output, message("start", sequence, {"ok": True, "value": identity}),
                    deadline=time.monotonic() + 300, max_bytes=frame_bytes)
        stage = "factory"
        while True:
            # Long idle lifetime allowed; each I/O remains bounded. Parent owns
            # per-operation deadlines and terminates a blocked provider call.
            request = read_frame(0, deadline=time.monotonic() + 3600, max_bytes=frame_bytes)
            if request["id"] != sequence + 1:
                raise ProtocolError("request sequence mismatch")
            sequence = request["id"]
            operation = request["op"]
            payload = request["payload"]
            if stage == "factory":
                if operation != "factory":
                    raise ProtocolError("expected factory request")
                fields(payload, {"context", "context_digest"})
                context = CanonicalContext(canonical_bytes(payload["context"]))
                if context.digest != payload["context_digest"]:
                    raise ProtocolError("context digest mismatch")
                recheck_snapshot(root, config["members"], config["snapshot_digest"])
                factory = _load_factory(authority, root)
                provider = factory(context.decode())
                if any(not callable(getattr(provider, name, None)) for name in ("acquire", "release", "execute")):
                    raise ProtocolError("factory returned invalid provider surface")
                result = None
                stage = "ready"
            elif stage == "ready":
                # Validate wire contracts outside the provider-exception boundary.
                if operation == "acquire":
                    fields(payload, {"request"})
                    args = (from_wire(ModelResidencyRequest, payload["request"]),)
                elif operation == "execute":
                    fields(payload, {"request", "residency"})
                    args = (from_wire(InferenceExecutionRequest, payload["request"]),)
                    residency = None if payload["residency"] is None else from_wire(ModelResidencyBinding, payload["residency"])
                elif operation == "release":
                    fields(payload, {"binding"})
                    args = (from_wire(ModelResidencyBinding, payload["binding"]),)
                elif operation == "close":
                    fields(payload, set())
                    args = ()
                else:
                    raise ProtocolError("operation invalid in ready state")
                try:
                    if operation == "acquire":
                        value = provider.acquire(*args)
                    elif operation == "execute":
                        value = provider.execute(*args, residency=residency)
                    elif operation == "release":
                        value = provider.release(*args)
                    else:
                        closer = getattr(provider, "close", None)
                        value = closer() if callable(closer) else None
                except Exception as exc:  # Deliberate plugin-call containment boundary.
                    if operation == "close":
                        raise
                    write_frame(output, message(operation, sequence, {"ok": False, "error": {
                        "category": "provider", "message": str(exc)[:2048]}}),
                        deadline=time.monotonic() + 300, max_bytes=frame_bytes)
                    continue
                if operation == "acquire":
                    result = to_wire(value, ModelResidencyBinding)
                elif operation == "execute":
                    result = to_wire(value, InferenceExecutionResult)
                else:
                    if value is not None:
                        raise ProtocolError("release/close must return None")
                    result = None
            write_frame(output, message(operation, sequence, {"ok": True, "value": result}),
                        deadline=time.monotonic() + 300, max_bytes=frame_bytes)
            if operation == "close":
                return
    except BaseException as exc:  # Final process boundary, no traceback objects on wire.
        try:
            write_frame(output, message(operation, max(sequence, 1), {"ok": False, "error": {
                "category": "sandbox" if isinstance(exc, SandboxError) else "infrastructure",
                "message": (type(exc).__name__ + ": " + str(exc))[:2048]}}),
                deadline=time.monotonic() + 1, max_bytes=frame_bytes)
        except BaseException:
            pass
        raise SystemExit(70) from None
    finally:
        os.close(output)


if __name__ == "__main__":
    main()
