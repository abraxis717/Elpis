"""Fail-closed qualification environment authority (not a dependency resolver)."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import sysconfig


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path) -> tuple[str, dict]:
    raw = path.read_bytes()
    entries = {}
    for line in raw.decode().replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9.+!-]+)((?:\s+--hash=sha256:[a-f0-9]{64})+)", line)
        if not match:
            raise ValueError("QUALIFICATION_LOCK_UNPINNED_OR_UNHASHED:" + line)
        name = normalized(match[1])
        if name in entries:
            raise ValueError("QUALIFICATION_LOCK_DUPLICATE:" + name)
        entries[name] = {"version": match[2], "hashes": re.findall(r"sha256:([a-f0-9]{64})", match[3])}
    if not entries:
        raise ValueError("QUALIFICATION_LOCK_EMPTY")
    return hashlib.sha256(raw).hexdigest(), entries


def supported_python(version=None) -> None:
    version = sys.version_info if version is None else version
    if tuple(version[:2]) not in {(3, 11), (3, 12)}:
        raise ValueError("QUALIFICATION_PYTHON_UNSUPPORTED")



def distribution_content_identity(dist) -> dict:
    name = normalized(dist.metadata["Name"])
    files = dist.files

    if not files:
        raise ValueError(
            "QUALIFICATION_DISTRIBUTION_FILES_MISSING:" + name
        )

    prefix = Path(sys.prefix).resolve()
    rows = []
    seen = set()

    for item in sorted(files, key=lambda value: value.as_posix()):
        rel = item.as_posix()

        # Wheel/RECORD metadata in real distributions can contain the
        # same installed relative path more than once. Content authority
        # is over distinct installed paths, not duplicate metadata rows.
        if rel in seen:
            continue
        seen.add(rel)

        candidate = Path(dist.locate_file(item))

        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(
                "QUALIFICATION_DISTRIBUTION_FILE_MISSING:"
                + name
                + ":"
                + rel
            ) from exc

        if not resolved.is_relative_to(prefix):
            raise ValueError(
                "QUALIFICATION_DISTRIBUTION_FILE_OUTSIDE_ENV:"
                + name
                + ":"
                + rel
            )

        if not resolved.is_file():
            raise ValueError(
                "QUALIFICATION_DISTRIBUTION_FILE_NOT_REGULAR:"
                + name
                + ":"
                + rel
            )

        raw = resolved.read_bytes()
        rows.append(
            {
                "path": rel,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return {
        "file_count": len(rows),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


VENV_BOOTSTRAP_SCRIPT_NAMES = frozenset(
    {
        "activate",
        "activate.csh",
        "activate.fish",
        "Activate.ps1",
    }
)


def _path_identity(paths, prefix: Path) -> dict:
    rows = []

    for path in sorted(
        set(paths),
        key=lambda value: value.relative_to(prefix).as_posix(),
    ):
        raw = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(prefix).as_posix(),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return {
        "file_count": len(rows),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _physical_regular_files(root: Path) -> set[Path]:
    files = set()

    for candidate in root.rglob("*"):
        try:
            if (
                candidate.is_file()
                and not candidate.is_symlink()
            ):
                files.add(candidate.resolve(strict=True))
        except FileNotFoundError:
            # Concurrent disappearance is not acceptable as a stable
            # authority observation; the later set comparison will fail
            # if it represented metadata-owned content.
            continue

    return files


def environment_physical_inventory(distributions) -> dict:
    """Bind complete physical membership of Python execution surfaces.

    Distribution metadata is not accepted as a complete inventory by
    assumption. We independently enumerate the physical site-packages and
    scripts trees and require all physical files to have an expected owner,
    except for the standard venv bootstrap activation scripts. Those bootstrap
    files are still byte-bound into the scripts inventory.
    """

    prefix = Path(sys.prefix).resolve(strict=True)

    roots = {}

    for label in ("purelib", "platlib", "scripts"):
        raw = sysconfig.get_path(label)

        if not raw:
            raise ValueError(
                "QUALIFICATION_ENVIRONMENT_PATH_MISSING:"
                + label
            )

        candidate = Path(raw).resolve(strict=True)

        if (
            not candidate.is_dir()
            or not candidate.is_relative_to(prefix)
        ):
            raise ValueError(
                "QUALIFICATION_ENVIRONMENT_PATH_INVALID:"
                + label
            )

        roots[label] = candidate

    site_roots = []
    for label in ("purelib", "platlib"):
        candidate = roots[label]
        if candidate not in site_roots:
            site_roots.append(candidate)

    scripts_root = roots["scripts"]

    metadata_owned = set()
    metadata_owned_entries = set()

    for dist in distributions:
        files = dist.files

        if not files:
            name = normalized(dist.metadata["Name"])
            raise ValueError(
                "QUALIFICATION_DISTRIBUTION_FILES_MISSING:"
                + name
            )

        for item in files:
            candidate = Path(dist.locate_file(item))

            try:
                resolved = candidate.resolve(strict=True)
            except FileNotFoundError as exc:
                raise ValueError(
                    "QUALIFICATION_METADATA_FILE_MISSING:"
                    + item.as_posix()
                ) from exc

            if not resolved.is_relative_to(prefix):
                raise ValueError(
                    "QUALIFICATION_METADATA_FILE_OUTSIDE_ENV:"
                    + item.as_posix()
                )

            logical = Path(os.path.abspath(candidate))

            if resolved.is_file() or candidate.is_symlink():
                metadata_owned_entries.add(logical)

            if resolved.is_file():
                metadata_owned.add(resolved)

    physical_site = set()
    physical_site_entries = set()
    site_topology = []
    permitted_site_roots = tuple(site_roots)

    for site_root in site_roots:
        physical_site.update(
            _physical_regular_files(site_root)
        )
        physical_site_entries.update(
            _physical_import_entries(
                site_root,
                permitted_roots=permitted_site_roots,
            )
        )
        site_topology.append(
            _tree_import_identity(
                site_root,
                permitted_roots=permitted_site_roots,
            )
        )

    metadata_site = {
        path
        for path in metadata_owned
        if any(
            path.is_relative_to(site_root)
            for site_root in site_roots
        )
    }

    metadata_site_entries = {
        path
        for path in metadata_owned_entries
        if any(
            path == site_root
            or path.is_relative_to(site_root)
            for site_root in site_roots
        )
    }

    unowned_site = physical_site - metadata_site
    missing_site = metadata_site - physical_site
    unowned_site_entries = (
        physical_site_entries - metadata_site_entries
    )
    missing_site_entries = (
        metadata_site_entries - physical_site_entries
    )

    if unowned_site:
        sample = sorted(
            path.relative_to(prefix).as_posix()
            for path in unowned_site
        )[0]
        raise ValueError(
            "QUALIFICATION_SITE_INVENTORY_UNOWNED:"
            + sample
        )

    if missing_site:
        sample = sorted(
            path.relative_to(prefix).as_posix()
            for path in missing_site
        )[0]
        raise ValueError(
            "QUALIFICATION_SITE_INVENTORY_MISSING:"
            + sample
        )

    if unowned_site_entries:
        sample = sorted(
            path.relative_to(prefix).as_posix()
            for path in unowned_site_entries
        )[0]
        raise ValueError(
            "QUALIFICATION_SITE_TOPOLOGY_UNOWNED:"
            + sample
        )

    if missing_site_entries:
        sample = sorted(
            path.relative_to(prefix).as_posix()
            for path in missing_site_entries
        )[0]
        raise ValueError(
            "QUALIFICATION_SITE_TOPOLOGY_MISSING:"
            + sample
        )

    physical_scripts = _physical_regular_files(
        scripts_root
    )

    metadata_scripts = {
        path
        for path in metadata_owned
        if path.is_relative_to(scripts_root)
    }

    unowned_scripts = (
        physical_scripts - metadata_scripts
    )

    bootstrap_scripts = set()

    for path in unowned_scripts:
        if (
            path.parent != scripts_root
            or path.name
            not in VENV_BOOTSTRAP_SCRIPT_NAMES
        ):
            raise ValueError(
                "QUALIFICATION_SCRIPT_INVENTORY_UNOWNED:"
                + path.relative_to(prefix).as_posix()
            )

        bootstrap_scripts.add(path)

    missing_scripts = (
        metadata_scripts - physical_scripts
    )

    if missing_scripts:
        sample = sorted(
            path.relative_to(prefix).as_posix()
            for path in missing_scripts
        )[0]
        raise ValueError(
            "QUALIFICATION_SCRIPT_INVENTORY_MISSING:"
            + sample
        )

    site_topology_canonical = json.dumps(
        site_topology,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return {
        "site_packages": {
            "file_count": sum(
                item["file_count"]
                for item in site_topology
            ),
            "symlink_count": sum(
                item["symlink_count"]
                for item in site_topology
            ),
            "sha256": hashlib.sha256(
                site_topology_canonical
            ).hexdigest(),
            "roots": site_topology,
        },
        "scripts": _path_identity(
            physical_scripts,
            prefix,
        ),
        "metadata_owned_site_files": len(
            metadata_site
        ),
        "metadata_owned_site_entries": len(
            metadata_site_entries
        ),
        "metadata_owned_script_files": len(
            metadata_scripts
        ),
        "venv_bootstrap_scripts": sorted(
            path.relative_to(prefix).as_posix()
            for path in bootstrap_scripts
        ),
    }



def _tree_import_identity(
    root: Path,
    *,
    permitted_roots: tuple[Path, ...],
    excluded_roots: tuple[Path, ...] = (),
) -> dict:
    root = root.resolve(strict=True)
    permitted = tuple(path.resolve(strict=True) for path in permitted_roots)
    excluded = tuple(path.resolve(strict=True) for path in excluded_roots)

    rows = []
    stack = [root]
    seen_dirs = set()

    while stack:
        directory = stack.pop()
        stat_value = directory.stat()
        inode = (stat_value.st_dev, stat_value.st_ino)

        if inode in seen_dirs:
            continue
        seen_dirs.add(inode)

        with os.scandir(directory) as stream:
            entries = sorted(stream, key=lambda entry: entry.name)

        for entry in entries:
            path = Path(entry.path)

            try:
                if any(
                    path == excluded_root
                    or path.is_relative_to(excluded_root)
                    for excluded_root in excluded
                ):
                    continue

                relative = path.relative_to(root).as_posix()

                if entry.is_symlink():
                    target_text = os.readlink(path)
                    target = path.resolve(strict=True)

                    if not any(
                        target == permitted_root
                        or target.is_relative_to(permitted_root)
                        for permitted_root in permitted
                    ):
                        raise ValueError(
                            'QUALIFICATION_IMPORT_SYMLINK_OUTSIDE_SURFACES:'
                            + str(path)
                        )

                    if target.is_file():
                        target_kind = 'file'
                    elif target.is_dir():
                        target_kind = 'directory'
                    else:
                        raise ValueError(
                            'QUALIFICATION_IMPORT_SYMLINK_TARGET_UNSUPPORTED:'
                            + str(path)
                        )

                    rows.append(
                        {
                            'path': relative,
                            'kind': 'symlink',
                            'target': target_text,
                            'target_kind': target_kind,
                        }
                    )
                    continue

                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                    continue

                if entry.is_file(follow_symlinks=False):
                    raw = path.read_bytes()
                    rows.append(
                        {
                            'path': relative,
                            'kind': 'file',
                            'size': len(raw),
                            'sha256': hashlib.sha256(raw).hexdigest(),
                        }
                    )
                    continue

                raise ValueError(
                    'QUALIFICATION_IMPORT_ENTRY_UNSUPPORTED:'
                    + str(path)
                )

            except FileNotFoundError as exc:
                raise ValueError(
                    'QUALIFICATION_IMPORT_ENTRY_UNSTABLE:'
                    + str(path)
                ) from exc

    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')

    return {
        'root': str(root),
        'file_count': sum(row['kind'] == 'file' for row in rows),
        'symlink_count': sum(row['kind'] == 'symlink' for row in rows),
        'sha256': hashlib.sha256(canonical).hexdigest(),
    }



def _physical_import_entries(
    root: Path,
    *,
    permitted_roots: tuple[Path, ...],
) -> set[Path]:
    root = root.resolve(strict=True)
    permitted = tuple(
        path.resolve(strict=True)
        for path in permitted_roots
    )

    entries = set()
    stack = [root]
    seen_dirs = set()

    while stack:
        directory = stack.pop()
        stat_value = directory.stat()
        inode = (stat_value.st_dev, stat_value.st_ino)

        if inode in seen_dirs:
            continue
        seen_dirs.add(inode)

        with os.scandir(directory) as stream:
            children = sorted(
                stream,
                key=lambda entry: entry.name,
            )

        for entry in children:
            path = Path(entry.path)

            try:
                if entry.is_symlink():
                    target = path.resolve(strict=True)

                    if not any(
                        target == permitted_root
                        or target.is_relative_to(
                            permitted_root
                        )
                        for permitted_root in permitted
                    ):
                        raise ValueError(
                            "QUALIFICATION_IMPORT_SYMLINK_OUTSIDE_SURFACES:"
                            + str(path)
                        )

                    if not (
                        target.is_file()
                        or target.is_dir()
                    ):
                        raise ValueError(
                            "QUALIFICATION_IMPORT_SYMLINK_TARGET_UNSUPPORTED:"
                            + str(path)
                        )

                    entries.add(
                        Path(os.path.abspath(path))
                    )
                    continue

                if entry.is_dir(
                    follow_symlinks=False
                ):
                    stack.append(path)
                    continue

                if entry.is_file(
                    follow_symlinks=False
                ):
                    entries.add(
                        Path(os.path.abspath(path))
                    )
                    continue

                raise ValueError(
                    "QUALIFICATION_IMPORT_ENTRY_UNSUPPORTED:"
                    + str(path)
                )

            except FileNotFoundError as exc:
                raise ValueError(
                    "QUALIFICATION_IMPORT_ENTRY_UNSTABLE:"
                    + str(path)
                ) from exc

    return entries

def base_import_inventory(repository_root: Path) -> dict:
    repository_root = repository_root.resolve(strict=True)
    tooling_root = (
        repository_root / "tools"
    ).resolve(strict=True)
    stdlib = Path(sysconfig.get_path('stdlib')).resolve(strict=True)
    purelib = Path(sysconfig.get_path('purelib')).resolve(strict=True)
    platlib = Path(sysconfig.get_path('platlib')).resolve(strict=True)
    dynload = (
        Path(sys.base_exec_prefix)
        / 'lib'
        / f'python{sys.version_info.major}.{sys.version_info.minor}'
        / 'lib-dynload'
    ).resolve(strict=True)

    site_roots = []
    for candidate in (purelib, platlib):
        if candidate not in site_roots:
            site_roots.append(candidate)

    permitted_roots = tuple(
        dict.fromkeys([stdlib, dynload, *site_roots, repository_root])
    )

    observed_dirs = []
    observed_files = []

    for path_index, value in enumerate(sys.path):
        candidate = repository_root if not value else Path(value)
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            continue

        if resolved == tooling_root:
            legitimate_scripts = {
                tooling_root / "qualification_environment.py",
                tooling_root / "full_release.py",
            }
            main_file = getattr(sys.modules.get("__main__"), "__file__", None)
            launch_file = Path(main_file).resolve() if main_file else None
            argv_file = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
            additional_tools_or_root = any(
                (Path(item).resolve() if item else repository_root)
                in {tooling_root, repository_root}
                for item in sys.path[1:]
            )
            if (
                path_index != 0
                or launch_file not in legitimate_scripts
                or argv_file != launch_file
                or additional_tools_or_root
            ):
                raise ValueError(
                    "QUALIFICATION_IMPORT_PATH_UNEXPECTED:" + str(resolved)
                )
            resolved = repository_root

        if resolved.is_dir():
            if resolved not in observed_dirs:
                observed_dirs.append(resolved)
        elif resolved.is_file():
            raw = resolved.read_bytes()
            observed_files.append(
                {
                    'path': str(resolved),
                    'size': len(raw),
                    'sha256': hashlib.sha256(raw).hexdigest(),
                }
            )
        else:
            raise ValueError(
                'QUALIFICATION_IMPORT_PATH_UNSUPPORTED:' + str(resolved)
            )

    unexpected = [
        path
        for path in observed_dirs
        if path not in permitted_roots
    ]
    if unexpected:
        raise ValueError(
            'QUALIFICATION_IMPORT_PATH_UNEXPECTED:'
            + ','.join(str(path) for path in unexpected)
        )

    required = {stdlib, dynload, *site_roots}
    if not required <= set(observed_dirs):
        missing = sorted(str(path) for path in required - set(observed_dirs))
        raise ValueError(
            'QUALIFICATION_IMPORT_PATH_MISSING:' + ','.join(missing)
        )

    stdlib_excludes = [dynload]
    for name in ('site-packages', 'dist-packages'):
        candidate = stdlib / name
        if candidate.exists() and candidate.resolve() not in observed_dirs:
            stdlib_excludes.append(candidate.resolve())

    return {
        'sys_path_directories': [str(path) for path in observed_dirs],
        'sys_path_files': observed_files,
        'repository_tools': _tree_import_identity(
            tooling_root,
            permitted_roots=(tooling_root,),
        ),
        'stdlib': _tree_import_identity(
            stdlib,
            permitted_roots=permitted_roots,
            excluded_roots=tuple(stdlib_excludes),
        ),
        'lib_dynload': _tree_import_identity(
            dynload,
            permitted_roots=permitted_roots,
        ),
    }

def authority(root: Path) -> dict:
    supported_python()
    config = Path(sys.prefix) / "pyvenv.cfg"
    if sys.prefix == sys.base_prefix or not config.is_file() or "include-system-site-packages = false" not in config.read_text().lower():
        raise ValueError("QUALIFICATION_ISOLATED_VENV_REQUIRED")
    key = f"release-{sys.platform}-{platform.machine().lower()}-py{sys.version_info.major}{sys.version_info.minor}"
    lock = root / "qualification/locks" / (key + ".lock")
    if not lock.is_file():
        raise ValueError("QUALIFICATION_PLATFORM_LOCK_MISSING:" + key)
    digest, expected = read_lock(lock)
    required = {"pip", "pytest", "numpy", "scipy", "torch", "setuptools", "wheel", "build", "twine"}
    if not required <= expected.keys():
        raise ValueError("QUALIFICATION_RELEASE_PROFILE_INCOMPLETE")
    distributions = list(metadata.distributions())

    installed = {}
    installed_content = {}

    for dist in distributions:
        name = normalized(dist.metadata["Name"])

        if name in installed:
            raise ValueError(
                "QUALIFICATION_DUPLICATE_DISTRIBUTION:"
                + name
            )

        installed[name] = dist.version
        installed_content[name] = (
            distribution_content_identity(dist)
        )

    physical_inventory = environment_physical_inventory(
        distributions
    )
    base_imports = base_import_inventory(root)

    if installed != {
        name: entry["version"]
        for name, entry in expected.items()
    }:
        raise ValueError("QUALIFICATION_INSTALLED_GRAPH_MISMATCH")

    if set(installed_content) != set(installed):
        raise ValueError("QUALIFICATION_INSTALLED_CONTENT_INCOMPLETE")
    report_path = Path(sys.prefix) / "qualification-install.json"
    report = json.loads(report_path.read_bytes())
    observed = {}
    for item in report["install"]:
        name = normalized(item["metadata"]["name"])
        sha = item["download_info"]["archive_info"]["hashes"]["sha256"]
        if name not in expected or sha not in expected[name]["hashes"] or item["metadata"]["version"] != expected[name]["version"]:
            raise ValueError("QUALIFICATION_INSTALL_HASH_MISMATCH:" + name)
        observed[name] = sha
    if set(observed) != set(expected):
        raise ValueError("QUALIFICATION_INSTALL_REPORT_INCOMPLETE")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True, capture_output=True)
    return {
        "schema": "elpis.qualification-environment.v5",
        "profile": key,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable_sha256":
            hashlib.sha256(
                Path(sys.executable).read_bytes()
            ).hexdigest(),
        "venv_config_sha256":
            hashlib.sha256(
                config.read_bytes()
            ).hexdigest(),
        "lock_sha256": digest,
        "installed": installed,
        "installed_content": installed_content,
        "physical_inventory": physical_inventory,
        "base_imports": base_imports,
        "artifacts": observed,
        "install_report_sha256":
            hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(authority(args.root), sort_keys=True, indent=2))
