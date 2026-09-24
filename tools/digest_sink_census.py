#!/usr/bin/env python3
"""Exhaustive direct SHA-256 production-sink census."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

SCHEMA = "elpis.direct-sha256-sink-census.v1"
BASELINE_COMMIT = "b7606061417db38a1f36a0db5a565cfe3bf2906e"
FORWARD_SCHEMA = "elpis.direct-sha256-sink-forward.v1"
FORWARD_REGISTRY_NAME = "direct_sha256_sink_forward_v1.json"

PRODUCTION_ROOTS = (
    "src",
    "components",
    "runtime",
    "ECS/runtime",
    "native/elpis-header/src",
)
EXCLUDED_PARTS = {"tests", "__pycache__", ".venv", "venv"}

ALLOWED_CATEGORIES = {
    "CANONICAL_IDENTITY_V1_AUTHORITY",
    "R2_ZERO_DEP_CANONICAL_IDENTITY_V1_EQUIVALENT",
    "R2_LEGACY_V1_PROTOCOL_IDENTITY",
    "RAW_BYTES_DIGEST",
    "HISTORICAL_DIRECT_SHA256",
}


class CensusError(RuntimeError):
    pass


AST_FORMAT = json.loads(Path(__file__).with_name("digest_ast_format_v1.json").read_text())["nodes"]


def canonical_ast(node: Any) -> str:
    """Elpis-owned v1 serialization, byte compatible with the historical census.

    Field order and optional-None omission are frozen data, not CPython's
    evolving ast.dump defaults. New syntax fails closed until format review.
    Location attributes never participate in identity.
    """
    if isinstance(node, ast.AST):
        name = type(node).__name__
        if name not in AST_FORMAT:
            raise CensusError("AST_FORMAT_NODE_UNSUPPORTED:" + name)
        spec = AST_FORMAT[name]
        if set(node._fields) - set(spec["fields"]):
            raise CensusError("AST_FORMAT_FIELDS_UNSUPPORTED:" + name)
        fields = []
        for field in spec["fields"]:
            value = getattr(node, field, None)
            if value is None and field in spec["omit_none"]:
                continue
            fields.append(field + "=" + canonical_ast(value))
        return name + "(" + ", ".join(fields) + ")"
    if isinstance(node, list):
        return "[" + ", ".join(canonical_ast(value) for value in node) + "]"
    if node is None or node is Ellipsis or type(node) in {str, bytes, int, float, complex, bool}:
        return repr(node)
    raise CensusError("AST_FORMAT_VALUE_UNSUPPORTED")


def _git(root: Path, *args: str) -> bytes:
    try:
        from tools import release_git as _release_git
    except ModuleNotFoundError:
        import release_git as _release_git

    p = _release_git.run(root, *args)
    if p.returncode:
        raise CensusError(
            f"GIT_FAILED:{' '.join(args)}:"
            f"{p.stderr.decode(errors='replace').strip()}"
        )
    return p.stdout


def _tracked_paths(root: Path, commit: str | None) -> list[str]:
    if commit is None:
        raw = _git(root, "ls-files", "-z")
    else:
        raw = _git(root, "ls-tree", "-r", "--name-only", "-z", commit)
    out: list[str] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        rel = item.decode("utf-8")
        p = PurePosixPath(rel)
        if p.suffix != ".py":
            continue
        if not any(
            rel == base or rel.startswith(base + "/")
            for base in PRODUCTION_ROOTS
        ):
            continue
        if any(part in EXCLUDED_PARTS for part in p.parts):
            continue
        if p.name.startswith("test_"):
            continue
        out.append(rel)
    return sorted(out)


def _source(root: Path, rel: str, commit: str | None) -> str:
    if commit is None:
        return (root / rel).read_text(encoding="utf-8")
    return _git(root, "show", f"{commit}:{rel}").decode("utf-8")


def _imports(tree: ast.AST) -> tuple[set[str], set[str]]:
    hashlib_aliases: set[str] = set()
    sha_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "hashlib":
                    hashlib_aliases.add(alias.asname or "hashlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "hashlib":
            for alias in node.names:
                if alias.name == "sha256":
                    sha_aliases.add(alias.asname or "sha256")
    return hashlib_aliases, sha_aliases


def _is_sha_call(
    node: ast.Call,
    hashlib_aliases: set[str],
    sha_aliases: set[str],
) -> bool:
    f = node.func
    if isinstance(f, ast.Attribute):
        if (
            f.attr == "sha256"
            and isinstance(f.value, ast.Name)
            and f.value.id in hashlib_aliases
        ):
            return True
        if (
            f.attr == "new"
            and isinstance(f.value, ast.Name)
            and f.value.id in hashlib_aliases
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "sha256"
        ):
            return True
    return isinstance(f, ast.Name) and f.id in sha_aliases


def _sha_input(node: ast.Call) -> ast.AST | None:
    f = node.func
    if (
        isinstance(f, ast.Attribute)
        and f.attr == "new"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "sha256"
    ):
        return node.args[1] if len(node.args) > 1 else None
    return node.args[0] if node.args else None


def _obvious_read_bytes(expr: ast.AST | None) -> bool:
    if expr is None:
        return False
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Attribute)
        and expr.func.attr == "read_bytes"
        and not expr.args
    ):
        return True
    return isinstance(expr, ast.Constant) and isinstance(expr.value, bytes)


def _structured_markers(expr: ast.AST | None) -> list[str]:
    if expr is None:
        return []
    markers: set[str] = set()
    for node in ast.walk(expr):
        if isinstance(node, ast.Name):
            low = node.id.lower()
            if any(x in low for x in ("canonical", "payload", "schema", "json")):
                markers.add(node.id)
        elif isinstance(node, ast.Attribute):
            low = node.attr.lower()
            if any(x in low for x in ("canonical", "payload", "schema", "json")):
                markers.add(node.attr)
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                low = fn.id.lower()
            elif isinstance(fn, ast.Attribute):
                low = fn.attr.lower()
            else:
                low = ""
            if any(x in low for x in ("canonical", "json", "asdict", "model_dump")):
                markers.add(low)
    return sorted(markers)


class SinkVisitor(ast.NodeVisitor):
    def __init__(
        self,
        rel: str,
        source: str,
        hashlib_aliases: set[str],
        sha_aliases: set[str],
    ):
        self.rel = rel
        self.source = source
        self.hashlib_aliases = hashlib_aliases
        self.sha_aliases = sha_aliases
        self.scope: list[str] = []
        self.sinks: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        if _is_sha_call(node, self.hashlib_aliases, self.sha_aliases):
            qualname = ".".join(self.scope) if self.scope else "<module>"
            normalized = canonical_ast(node)
            fingerprint = hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest()
            expr = _sha_input(node)
            segment = ast.get_source_segment(self.source, node) or normalized
            self.sinks.append(
                {
                    "path": self.rel,
                    "qualname": qualname,
                    "lineno": node.lineno,
                    "fingerprint": fingerprint,
                    "call": " ".join(segment.split()),
                    "obvious_raw_bytes": _obvious_read_bytes(expr),
                    "structured_markers": _structured_markers(expr),
                }
            )
        self.generic_visit(node)


def scan(root: Path, commit: str | None = None) -> list[dict[str, Any]]:
    all_sinks: list[dict[str, Any]] = []
    for rel in _tracked_paths(root, commit):
        source = _source(root, rel, commit)
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            raise CensusError(f"PARSE_FAILED:{rel}:{exc}") from exc
        hashlib_aliases, sha_aliases = _imports(tree)
        if not hashlib_aliases and not sha_aliases:
            continue
        visitor = SinkVisitor(
            rel,
            source,
            hashlib_aliases,
            sha_aliases,
        )
        visitor.visit(tree)

        # Multiple byte-identical SHA calls can legitimately occur in the same
        # function. Give them a deterministic source-order occurrence index so
        # the census identity remains unique without relying on absolute line
        # numbers (which churn under unrelated edits above the function).
        counts: dict[tuple[str, str], int] = {}
        for sink in sorted(
            visitor.sinks,
            key=lambda s: (s["lineno"], s["fingerprint"], s["call"]),
        ):
            base = (sink["qualname"], sink["fingerprint"])
            occurrence = counts.get(base, 0)
            counts[base] = occurrence + 1
            sink["occurrence"] = occurrence
            all_sinks.append(sink)

    return sorted(
        all_sinks,
        key=lambda x: (
            x["path"],
            x["qualname"],
            x["fingerprint"],
            x["occurrence"],
        ),
    )


def identity(sink: dict[str, Any]) -> tuple[str, str, str, int]:
    return (
        sink["path"],
        sink["qualname"],
        sink["fingerprint"],
        int(sink["occurrence"]),
    )


def _baseline_category(sink: dict[str, Any]) -> tuple[str, str]:
    path = sink["path"]
    qual = sink["qualname"]
    if (
        path == "src/elpis/canonical_identity.py"
        and qual.endswith("content_digest")
    ):
        return (
            "CANONICAL_IDENTITY_V1_AUTHORITY",
            "sole cross-component Canonical Identity v1 SHA-256 authority",
        )
    if (
        path == "runtime/R2/src/elpis_runtime_r2/receipt.py"
        and qual.endswith("_canonical_identity_digest")
    ):
        return (
            "R2_ZERO_DEP_CANONICAL_IDENTITY_V1_EQUIVALENT",
            "R2 zero-dependency wheel; repository contract proves byte-equivalence to elpis.canonical_identity",
        )
    if (
        path == "runtime/R2/src/elpis_runtime_r2/receipt.py"
        and qual.endswith("_legacy_v1_digest")
    ):
        return (
            "R2_LEGACY_V1_PROTOCOL_IDENTITY",
            "historical Elpis2.2.13 receipt-v1 verification compatibility only",
        )
    if sink["obvious_raw_bytes"]:
        return (
            "RAW_BYTES_DIGEST",
            "AST proves SHA-256 input is direct raw bytes or Path.read_bytes()",
        )
    return (
        "HISTORICAL_DIRECT_SHA256",
        "pre-Q0a direct SHA-256 sink frozen into the census; future sinks cannot claim this category unless present at the bound baseline commit",
    )


def build_baseline(root: Path) -> dict[str, Any]:
    records = []
    for sink in scan(root, BASELINE_COMMIT):
        category, justification = _baseline_category(sink)
        record = dict(sink)
        record["category"] = category
        record["justification"] = justification
        records.append(record)
    return {
        "schema": SCHEMA,
        "baseline_commit": BASELINE_COMMIT,
        "production_roots": list(PRODUCTION_ROOTS),
        "excluded_path_parts": sorted(EXCLUDED_PARTS),
        "policy": {
            "new_structured_identity": "MUST_USE_ELPIS_CANONICAL_IDENTITY",
            "new_direct_sha256_default": "FORBIDDEN_UNTIL_EXPLICITLY_CLASSIFIED",
            "historical_direct_sha256": "MUST_BE_PROVABLY_PRESENT_AT_BASELINE_COMMIT",
            "raw_bytes_digest": "ALLOWED_ONLY_WITH_EXPLICIT_CENSUS_ENTRY_AND_NO_STRUCTURED_MARKERS",
        },
        "sinks": records,
    }


def load_baseline(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise CensusError("CENSUS_SCHEMA_INVALID")
    if data.get("baseline_commit") != BASELINE_COMMIT:
        raise CensusError("CENSUS_BASELINE_COMMIT_INVALID")
    if tuple(data.get("production_roots", ())) != PRODUCTION_ROOTS:
        raise CensusError("CENSUS_ROOTS_INVALID")
    sinks = data.get("sinks")
    if not isinstance(sinks, list):
        raise CensusError("CENSUS_SINKS_INVALID")
    seen: set[tuple[str, str, str, int]] = set()
    for entry in sinks:
        key = identity(entry)
        if key in seen:
            raise CensusError(f"CENSUS_DUPLICATE:{key}")
        seen.add(key)
        category = entry.get("category")
        if category not in ALLOWED_CATEGORIES:
            raise CensusError(f"CENSUS_CATEGORY_INVALID:{key}:{category}")
        justification = entry.get("justification")
        if not isinstance(justification, str) or not justification.strip():
            raise CensusError(f"CENSUS_JUSTIFICATION_MISSING:{key}")
    return data


def load_forward(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema": FORWARD_SCHEMA,
            "baseline_commit": BASELINE_COMMIT,
            "sinks": [],
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != FORWARD_SCHEMA:
        raise CensusError("FORWARD_CENSUS_SCHEMA_INVALID")
    if data.get("baseline_commit") != BASELINE_COMMIT:
        raise CensusError("FORWARD_CENSUS_BASELINE_INVALID")
    sinks = data.get("sinks")
    if not isinstance(sinks, list):
        raise CensusError("FORWARD_CENSUS_SINKS_INVALID")
    seen = set()
    for entry in sinks:
        key = identity(entry)
        if key in seen:
            raise CensusError(f"FORWARD_CENSUS_DUPLICATE:{key}")
        seen.add(key)
        if entry.get("category") != "RAW_BYTES_DIGEST":
            raise CensusError(f"FORWARD_CENSUS_CATEGORY_INVALID:{key}")
        justification = entry.get("justification")
        if not isinstance(justification, str) or not justification.strip():
            raise CensusError(
                f"FORWARD_CENSUS_JUSTIFICATION_MISSING:{key}"
            )
    return data


def verify(root: Path, baseline_path: Path) -> dict[str, Any]:
    baseline = load_baseline(baseline_path)
    forward = load_forward(root / "tools" / FORWARD_REGISTRY_NAME)
    baseline_actual = {
        identity(s): s
        for s in scan(root, BASELINE_COMMIT)
    }
    current_actual = {
        identity(s): s
        for s in scan(root, None)
    }
    baseline_registered = {
        identity(s): s
        for s in baseline["sinks"]
    }
    forward_registered = {
        identity(s): s
        for s in forward["sinks"]
    }
    overlap = set(baseline_registered).intersection(forward_registered)
    if overlap:
        raise CensusError(
            "FORWARD_CENSUS_OVERLAPS_BASELINE:" + repr(sorted(overlap))
        )
    registered = dict(baseline_registered)
    registered.update(forward_registered)

    errors: list[str] = []

    for key, entry in baseline_registered.items():
        category = entry["category"]
        if category in {
            "HISTORICAL_DIRECT_SHA256",
            "R2_LEGACY_V1_PROTOCOL_IDENTITY",
        } and key not in baseline_actual:
            errors.append(f"HISTORICAL_ENTRY_NOT_IN_BASELINE:{key}")

    for key, sink in current_actual.items():
        entry = registered.get(key)
        if entry is None:
            errors.append(
                "UNREGISTERED_DIRECT_SHA256:"
                f"{sink['path']}:{sink['lineno']}:{sink['qualname']}:"
                f"{sink['call']}"
            )
            continue
        category = entry["category"]
        if category == "RAW_BYTES_DIGEST":
            markers = sink.get("structured_markers") or []
            if markers:
                errors.append(
                    f"RAW_CATEGORY_HAS_STRUCTURED_MARKERS:{key}:{markers}"
                )
        elif category == "CANONICAL_IDENTITY_V1_AUTHORITY":
            if not (
                sink["path"] == "src/elpis/canonical_identity.py"
                and sink["qualname"].endswith("content_digest")
            ):
                errors.append(f"CANONICAL_AUTHORITY_MISBOUND:{key}")
        elif category == "R2_ZERO_DEP_CANONICAL_IDENTITY_V1_EQUIVALENT":
            if not (
                sink["path"] == "runtime/R2/src/elpis_runtime_r2/receipt.py"
                and sink["qualname"].endswith("_canonical_identity_digest")
            ):
                errors.append(f"R2_EQUIVALENT_MISBOUND:{key}")

    for key, entry in baseline_registered.items():
        if key in current_actual:
            continue
        if entry["category"] in {
            "CANONICAL_IDENTITY_V1_AUTHORITY",
            "R2_ZERO_DEP_CANONICAL_IDENTITY_V1_EQUIVALENT",
        }:
            errors.append(f"REQUIRED_AUTHORITY_SINK_MISSING:{key}")

    for key in forward_registered:
        if key not in current_actual:
            errors.append(f"FORWARD_CENSUS_SINK_MISSING:{key}")

    categories: dict[str, int] = {}
    for key in current_actual:
        entry = registered.get(key)
        category = entry["category"] if entry else "UNREGISTERED"
        categories[category] = categories.get(category, 0) + 1

    report = {
        "schema": SCHEMA,
        "baseline_commit": BASELINE_COMMIT,
        "registered_sink_count": len(registered),
        "baseline_registered_sink_count": len(baseline_registered),
        "forward_registered_sink_count": len(forward_registered),
        "baseline_actual_sink_count": len(baseline_actual),
        "current_sink_count": len(current_actual),
        "categories": dict(sorted(categories.items())),
        "errors": errors,
        "status": "PASS" if not errors else "NONPASS",
    }
    if errors:
        raise CensusError(
            "DIRECT_SHA256_CENSUS_NONPASS:\n" + "\n".join(errors)
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--emit-baseline", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    baseline = (
        args.baseline.resolve()
        if args.baseline is not None
        else root / "tools" / "direct_sha256_sink_census_v1.json"
    )

    if args.emit_baseline:
        data = build_baseline(root)
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(
            json.dumps(
                data,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": "EMITTED",
            "path": str(baseline),
            "sink_count": len(data["sinks"]),
            "baseline_commit": BASELINE_COMMIT,
        }, sort_keys=True))
        return 0

    report = verify(root, baseline)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
