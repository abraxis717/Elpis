"""Audit child-process hermeticity.

Detects fresh Python child processes launched from repository code that depend
on repository-local source but do not declare the minimal source roots they
require -- i.e. they resolve repository packages by inheriting the ambient
``PYTHONPATH`` exported by the test runner instead of declaring their own roots.

The repository deliberately does not export all source roots through ambient
``PYTHONPATH``. Every child execution boundary must declare only the minimal
source roots it actually requires. This audit is the permanent, reusable guard
against that class of regression.

Design notes
------------
* **Evidence-driven.** A finding is reported only when the child *provably*
  imports a repository-local package (the inline ``-c`` code, the ``-m`` module,
  or the launched script file is inspected) AND no explicit source-root
  declaration is found in the launch context.
* **Conservative.** When the audit cannot determine whether a child needs
  repository-local source, or cannot classify the environment it is given, it
  does *not* report a finding. False positives are a defect; a missed finding in
  an ambiguous case is acceptable.
* **Deterministic.** File traversal and findings are sorted; no network access,
  no wall-clock dependence.

Recognised legitimate (non-finding) declarations:

* an ``env`` mapping that sets ``PYTHONPATH`` (literal dict, or a variable built
  from ``os.environ``/``dict(os.environ)`` with ``PYTHONPATH`` assigned);
* an ``env`` produced by a helper call (treated as declaring roots -- the helper
  is the established per-test pattern);
* the child's own code performing ``sys.path.insert`` / ``sys.path.append``;
* the launched script file self-declaring its roots.

Run as a CLI::

    python tools/audit_child_process_hermeticity.py [ROOT] [--json]

or as a module::

    from tools.audit_child_process_hermeticity import audit
    findings = audit(Path("..."))
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import tomllib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Finding:
    """A child-process launch that relies on ambient PYTHONPATH."""

    path: str
    line: int
    reason: str


# ---------------------------------------------------------------------------
# Repository-local package discovery
# ---------------------------------------------------------------------------

def _add_packages(directory: Path, packages: set[str]) -> None:
    """Add immediate sub-packages and top-level modules of *directory*."""
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.is_dir() and (entry / "__init__.py").is_file():
            packages.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py" and entry.name != "__init__.py":
            packages.add(entry.stem)


def repo_local_packages(root: Path) -> set[str]:
    """Derive the set of repository-local top-level package/module names.

    Sources: the declared pytest ``pythonpath`` roots, every ``components/*/src``
    directory, top-level component packages, and the ``tools`` package. This is
    the set of names a child process would need a source root to import.
    """
    packages: set[str] = set()

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            data = {}
        pythonpath = (
            data.get("tool", {})
            .get("pytest", {})
            .get("ini_options", {})
            .get("pythonpath", [])
        )
        for rel in pythonpath:
            directory = root / rel
            if directory.is_dir():
                _add_packages(directory, packages)

    components = root / "components"
    if components.is_dir():
        for src in sorted(components.glob("*/src")):
            if src.is_dir():
                _add_packages(src, packages)
        for entry in sorted(components.iterdir()):
            if entry.is_dir() and (entry / "__init__.py").is_file():
                packages.add(entry.name)

    if (root / "tools" / "__init__.py").is_file():
        packages.add("tools")

    return packages


# ---------------------------------------------------------------------------
# Child-code import analysis
# ---------------------------------------------------------------------------

def _top_level_imports(code: str) -> set[str]:
    """Return top-level imported names from *code*.

    Uses ``ast`` when the code parses; falls back to a conservative regex scan.
    Returns an empty set when nothing can be determined.
    """
    imports: set[str] = set()
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        import re

        for match in re.finditer(
            r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", code, flags=re.MULTILINE
        ):
            imports.add(match.group(1))
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
    return imports


# ---------------------------------------------------------------------------
# Scope analysis: string variables and environment-variable provenance
# ---------------------------------------------------------------------------

def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _dict_has_pythonpath(node: ast.Dict) -> bool:
    for key in node.keys:
        if isinstance(key, ast.Constant) and key.value == "PYTHONPATH":
            return True
    return False


@dataclass
class EnvInfo:
    base_ambient: bool = False      # built from os.environ / dict(os.environ)
    pythonpath_set: bool = False    # PYTHONPATH assigned to this variable
    is_literal_dict: bool = False   # assigned a literal dict
    literal_has_pythonpath: bool = False
    is_call: bool = False           # assigned a (helper) call -- unresolvable


def _analyze_scope(body: list[ast.stmt]) -> tuple[dict[str, str], dict[str, EnvInfo]]:
    """Collect string variables and environment-variable provenance in a scope."""
    string_vars: dict[str, str] = {}
    env_vars: dict[str, EnvInfo] = {}

    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not (isinstance(target, ast.Name)):
                    continue
                name = target.id
                value = node.value
                # string variable (for -c code resolution)
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    string_vars[name] = value.value
                # environment variable provenance
                info = env_vars.setdefault(name, EnvInfo())
                if isinstance(value, ast.Call):
                    func = value.func
                    if isinstance(func, ast.Name) and func.id == "dict":
                        if value.args and _is_os_environ(value.args[0]):
                            info.base_ambient = True
                            for kw in value.keywords:
                                if kw.arg == "PYTHONPATH":
                                    info.pythonpath_set = True
                        else:
                            info.is_literal_dict = True
                            if value.args and isinstance(value.args[0], ast.Dict):
                                info.literal_has_pythonpath = _dict_has_pythonpath(
                                    value.args[0]
                                )
                    elif (
                        isinstance(func, ast.Attribute)
                        and func.attr == "copy"
                        and _is_os_environ(func.value)
                    ):
                        info.base_ambient = True
                    else:
                        info.is_call = True
                elif isinstance(value, ast.Dict):
                    info.is_literal_dict = True
                    info.literal_has_pythonpath = _dict_has_pythonpath(value)
                elif _is_os_environ(value):
                    info.base_ambient = True

        elif isinstance(node, ast.Subscript):
            # env["PYTHONPATH"] = ...
            if (
                isinstance(node.value, ast.Name)
                and isinstance(node.slice, ast.Constant)
                and node.slice.value == "PYTHONPATH"
            ):
                env_vars.setdefault(node.value.id, EnvInfo()).pythonpath_set = True

        elif isinstance(node, ast.Call):
            # env.update({"PYTHONPATH": ...})
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "update"
                and isinstance(func.value, ast.Name)
                and node.args
                and isinstance(node.args[0], ast.Dict)
                and _dict_has_pythonpath(node.args[0])
            ):
                env_vars.setdefault(func.value.id, EnvInfo()).pythonpath_set = True

    return string_vars, env_vars


# ---------------------------------------------------------------------------
# Command-line child-code extraction
# ---------------------------------------------------------------------------

def _interpreter_index(cmd: list[ast.expr]) -> int:
    """Index of the Python interpreter token, or -1."""
    for i, element in enumerate(cmd):
        if _is_sys_executable(element):
            return i
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            token = element.value
            if token == "python" or token.startswith("python3"):
                return i
    return -1


def _is_sys_executable(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "executable"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _element_str(element: ast.expr, string_vars: dict[str, str]) -> Optional[str]:
    if isinstance(element, ast.Constant) and isinstance(element.value, str):
        return element.value
    if isinstance(element, ast.Name):
        return string_vars.get(element.id)
    return None


def _extract_child(
    cmd: list[ast.expr],
    string_vars: dict[str, str],
    source_dir: Path,
) -> tuple[Optional[str], Optional[str]]:
    """Return (child_code, module_name) for a Python child command.

    ``child_code`` is the inline ``-c`` source or the launched script's source;
    ``module_name`` is set for ``-m`` invocations. Both may be ``None``.
    """
    for i, element in enumerate(cmd):
        value = _element_str(element, string_vars)
        if value == "-c" and i + 1 < len(cmd):
            code = _element_str(cmd[i + 1], string_vars)
            return code, None
        if value == "-m" and i + 1 < len(cmd):
            module = _element_str(cmd[i + 1], string_vars)
            return None, module
    # A script path: a string literal (or resolved variable) ending in .py.
    for element in cmd:
        value = _element_str(element, string_vars)
        if value and value.endswith(".py"):
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = source_dir / candidate
            if candidate.is_file():
                try:
                    return candidate.read_text(encoding="utf-8"), None
                except OSError:
                    return None, None
    return None, None


# ---------------------------------------------------------------------------
# Environment declaration analysis
# ---------------------------------------------------------------------------

def _env_declares_pythonpath(
    env_node: Optional[ast.expr], env_vars: dict[str, EnvInfo]
) -> bool:
    """True when the launch environment provably sets PYTHONPATH.

    Conservative: unresolvable environments (helper calls, unknown variables)
    are treated as declaring roots so they are not flagged.
    """
    if env_node is None:
        return False  # inherits the parent environment (ambient)
    if isinstance(env_node, ast.Dict):
        return _dict_has_pythonpath(env_node)
    if isinstance(env_node, ast.Name):
        info = env_vars.get(env_node.id)
        if info is None:
            return True  # unknown provenance -- do not flag
        if info.pythonpath_set:
            return True
        if info.is_literal_dict:
            return info.literal_has_pythonpath
        if info.base_ambient:
            return False  # ambient copy without PYTHONPATH
        return True  # helper call / unknown -- do not flag
    if isinstance(env_node, ast.Call):
        # os.environ.copy() is an ambient copy with no roots declared.
        if (
            isinstance(env_node.func, ast.Attribute)
            and env_node.func.attr == "copy"
            and _is_os_environ(env_node.func.value)
        ):
            return False
        return True  # helper call -- do not flag
    return True  # conservative default


# ---------------------------------------------------------------------------
# The audit
# ---------------------------------------------------------------------------

_SUBPROCESS_FUNCS = {"run", "Popen", "check_call", "check_output", "call"}

_SKIP_DIRS = {
    ".git", "venv", ".venv", "build", "dist", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


def _iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        parts = set(path.relative_to(root).parts)
        if parts & _SKIP_DIRS:
            continue
        yield path


def _function_bodies(tree: ast.Module):
    """Yield (scope_node, body) for the module and every nested function.

    ``scope_node`` is the node whose ``body`` defines the scope (the module for
    the top level, or the function def for a function scope).
    """
    yield tree, tree.body
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, node.body


def _innermost_scope(
    call: ast.Call, scopes: list[tuple[ast.AST, list[ast.stmt]]]
) -> list[ast.stmt]:
    """Return the body of the innermost scope containing *call*."""
    # ``scopes`` is ordered module-first, functions after; the innermost
    # containing scope is the last one whose node is an ancestor of the call.
    chosen = scopes[0][1]
    for scope_node, body in scopes:
        if scope_node is call:
            continue
        for descendant in ast.walk(scope_node):
            if descendant is call:
                chosen = body
                break
        # keep scanning so a deeper (later) scope wins
    return chosen


def audit(root: Path) -> list[Finding]:
    """Audit *root* for child processes that rely on ambient PYTHONPATH."""
    root = root.resolve()
    packages = repo_local_packages(root)
    findings: list[Finding] = []

    for path in _iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            continue

        source_dir = path.parent
        scopes = list(_function_bodies(tree))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr in _SUBPROCESS_FUNCS
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            ):
                continue
            if not node.args or not isinstance(node.args[0], ast.List):
                continue
            cmd = node.args[0].elts
            if _interpreter_index(cmd) < 0:
                continue  # not a Python child (e.g. git)

            body = _innermost_scope(node, scopes)
            string_vars, env_vars = _analyze_scope(body)

            child_code, module_name = _extract_child(cmd, string_vars, source_dir)

            # Does the child need repository-local source?
            if module_name is not None:
                needs = module_name.split(".")[0] in packages
            elif child_code is not None:
                needs = bool(_top_level_imports(child_code) & packages)
            else:
                needs = False  # undetermined -- do not flag
            if not needs:
                continue

            # Does the launch declare the source roots?
            env_node = next(
                (kw.value for kw in node.keywords if kw.arg == "env"), None
            )
            env_declares = _env_declares_pythonpath(env_node, env_vars)
            child_self = (
                child_code is not None
                and ("sys.path.insert" in child_code
                     or "sys.path.append" in child_code)
            )
            if env_declares or child_self:
                continue

            findings.append(
                Finding(
                    path=path.relative_to(root).as_posix(),
                    line=node.lineno,
                    reason=(
                        "child Python process imports repository-local "
                        "source but declares no source roots; it relies "
                        "on ambient PYTHONPATH"
                    ),
                )
            )

    findings.sort(key=lambda f: (f.path, f.line, f.reason))
    return findings


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="repository root to audit (default: current directory)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit findings as JSON"
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    findings = audit(root)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, sort_keys=True))
    else:
        if not findings:
            print("child-process hermeticity: OK (no ambient-PYTHONPATH reliance)")
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.reason}")
        if findings:
            print(f"child-process hermeticity: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
