"""Fail closed on new raw Git/process wrappers across tests and tooling.

The exceptions are reviewed source identities, not blanket filename exemptions.
They distinguish isolated fixture Git, historical non-mandatory scripts, and the
already qualified boundary implementations. Changing any exception's executable
AST requires reviewing its targets/callers again. No command is exempt merely
because its destination variable is named ``repo`` or ``tmp_path``.
"""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = Path(__file__).with_name("release_git_authority_exceptions.json")
PROCESS = {"run", "check_output", "check_call", "call", "Popen"}
OS_PROCESS = {"system", "popen", "execv", "execve", "execvp", "execvpe",
              "spawnv", "spawnve", "spawnvp", "spawnvpe"}


def source_identity(source):
    return hashlib.sha256(ast.dump(ast.parse(source), include_attributes=False).encode()).hexdigest()


def execution_sites(source):
    """Inventory literal, aliased, shell and unresolved/dynamic process vectors.

    Dynamic arguments fail closed; reviewed Python-only launch wrappers need a
    source-bound exception too. This avoids relying on a literal-[git] census.
    """
    tree = ast.parse(source)
    imports = {}
    values = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                imports[item.asname or item.name] = item.name
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                imports[item.asname or item.name] = (node.module or "") + "." + item.name
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and node.value is not None:
                    values.setdefault(target.id, []).append(node.value)

    def names(node, seen=frozenset()):
        if isinstance(node, ast.Name):
            if node.id in seen:
                return {"?"}
            if node.id in imports:
                return {imports[node.id]}
            return set().union(*(names(v, seen | {node.id}) for v in values.get(node.id, []))) or {"?"}
        if isinstance(node, ast.Attribute):
            return {v + "." + node.attr for v in names(node.value, seen)}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
            if len(node.args) > 1:
                attr = node.args[1].value if isinstance(node.args[1], ast.Constant) else "?"
                return {v + "." + str(attr) for v in names(node.args[0], seen)}
        return {"?"}

    def commands(node, seen=frozenset()):
        if isinstance(node, (ast.List, ast.Tuple)):
            return commands(node.elts[0], seen) if node.elts else set()
        if isinstance(node, ast.Name):
            # A variable can be reassigned or supplied by a caller. Treat it as
            # dynamic instead of borrowing an assignment from another scope.
            return {"?"}
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant) and isinstance(node.left.value, str) and isinstance(node.right.value, str):
                return {node.left.value + node.right.value}
            return commands(node.left, seen)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value.strip().split()[0]} if node.value.strip() else set()
        if isinstance(node, ast.Attribute) and "sys.executable" in names(node):
            return {"python"}
        return {"?"}

    def canonical_target(node, seen=frozenset()):
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if child.id in {"ROOT", "REPO", "REPOSITORY_ROOT"}:
                    return True
                if child.id not in seen and any(canonical_target(v, seen | {child.id}) for v in values.get(child.id, [])):
                    return True
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and str(ROOT) in child.value:
                return True
        return False

    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = names(node.func)
        sink = any(v.startswith("subprocess.") and v.rsplit(".", 1)[-1] in PROCESS | {"?"}
                   or v.startswith("os.") and v.rsplit(".", 1)[-1] in OS_PROCESS for v in fn)
        arg = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg in {"args", "command"}), None)
        executable = commands(arg) if arg is not None else {"?"}
        literal_vector = isinstance(arg, (ast.List, ast.Tuple)) or (
            isinstance(arg, ast.BinOp)
            and any(isinstance(child, (ast.List, ast.Tuple)) for child in ast.walk(arg))
        )
        git = any(Path(v).name == "git" for v in executable)
        embedded_git = arg is not None and any(
            isinstance(child, ast.Constant) and isinstance(child.value, str)
            and re.search(r"\bgit\b", child.value)
            for child in ast.walk(arg)
        )
        shell_executable = any(Path(v).name in {"sh", "bash", "zsh", "dash", "cmd", "powershell"} for v in executable)
        shell = any(k.arg == "shell" and not (isinstance(k.value, ast.Constant) and k.value.value is False) for k in node.keywords)
        helper = (isinstance(node.func, ast.Name) and node.func.id in {"git", "_git"}) or any(v.rsplit(".", 1)[-1] in {"git", "_git"} for v in fn)
        canonical_helper = helper and any(canonical_target(a) for a in node.args)
        if (sink and (git or embedded_git or "?" in executable or shell or shell_executable or any(v.startswith("os.") for v in fn))) or (literal_vector and git) or canonical_helper:
            sites.append({"line": node.lineno, "call": ast.unparse(node.func), "executables": sorted(executable)})
    return sorted(sites, key=lambda row: row["line"])


def census(root=ROOT, exceptions=None):
    if exceptions is None:
        exceptions = json.loads(EXCEPTIONS.read_text())
    findings = []
    inventory = {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if ".git" in rel.parts or not ("tests" in rel.parts or rel.parts[0] == "tools"):
            continue
        source = path.read_text()
        sites = execution_sites(source)
        if not sites:
            continue
        name = rel.as_posix()
        inventory[name] = sites
        entry = exceptions.get(name)
        if not entry or source_identity(source) != entry["ast_sha256"] or not entry["reason"]:
            findings.append({"path": name, "sites": sites})
    # Stale exceptions cannot silently broaden a later census.
    findings.extend({"stale_exception": name} for name in exceptions if name not in inventory)
    return findings, inventory


def test_complete_test_and_tool_git_authority_census():
    findings, _ = census()
    assert findings == [], json.dumps(findings, indent=2)


def test_census_detects_aliases_dynamic_vectors_and_shell():
    samples = [
        "import subprocess as s\ns.run(['git', 'archive', 'HEAD'], cwd=ROOT)",
        "from subprocess import check_output as read\ncmd=['git', 'show', 'HEAD:x']\nread(cmd)",
        "import subprocess\ncommand=['git']+args\nsubprocess.Popen(command)",
        "import subprocess\ninvoke=subprocess.call\ninvoke(argv)",
        "import os\nos.system('git archive HEAD')",
        "import subprocess\nsubprocess.run(args=command, shell=True)",
        "runner.command(['git', *args], cwd=ROOT)",
        "import subprocess\ngetattr(subprocess, operation)(argv)",
        "from fixture import git as command\nrepo = ROOT\ncommand(repo, 'show', 'HEAD:x')",
        "import subprocess\nsubprocess.run(['bash', '-c', 'git archive HEAD'])",
        "import subprocess\nsubprocess.run(['g' + 'it', 'show', 'HEAD:x'])",
        "import subprocess\nsubprocess.run(['env', 'GIT_DIR=selected', 'git', 'show', 'HEAD:x'])",
    ]
    assert all(execution_sites(source) for source in samples)
    assert not execution_sites("from tools import release_git\nrelease_git.run(ROOT, 'archive', 'HEAD')")
    assert source_identity("repo = tmp_path\n") != source_identity("repo = ROOT\n")


def test_fixture_exception_cannot_be_retargeted_to_canonical_authority(tmp_path):
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    path = test_dir / "test_fixture.py"
    source = "import subprocess\ndef fixture(tmp_path):\n    repo = tmp_path\n    subprocess.run(['git', 'init'], cwd=repo)\n"
    path.write_text(source)
    reviewed = {"tests/test_fixture.py": {"ast_sha256": source_identity(source), "reason": "isolated fixture"}}
    assert census(tmp_path, reviewed)[0] == []
    path.write_text(source.replace("repo = tmp_path", "repo = ROOT"))
    assert census(tmp_path, reviewed)[0][0]["path"] == "tests/test_fixture.py"
    path.write_text(source)
    (test_dir / "test_new.py").write_text("from subprocess import check_output as read\nread(command)\n")
    assert census(tmp_path, reviewed)[0][0]["path"] == "tests/test_new.py"


def test_all_hosted_git_commands_use_streaming_boundary():
    for name in ("ci.yml", "pypi-publish.yaml", "reference-runtime.yml"):
        source = (ROOT / ".github/workflows" / name).read_text()
        # Any direct executable Git spelling, including commands beyond the R4 list.
        assert not re.search(r"(?:^|[\s$(;|&])(?:/[^\s]+/)?git\s+[A-Za-z-]", source), name
        assert "python tools/release_git_cli.py" in source
