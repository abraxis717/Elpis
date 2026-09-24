from pathlib import Path, PurePosixPath

from tools import qualification_environment as environment
import pytest


class FakeDistribution:
    def __init__(self, root):
        self.root = Path(root)
        self.metadata = {"Name": "pytest"}
        self.version = "9.0.3"
        self.files = [
            PurePosixPath("pytest/__init__.py"),
            PurePosixPath("pytest/core.py"),
            PurePosixPath("pytest-9.0.3.dist-info/METADATA"),
        ]

    def locate_file(self, item):
        return self.root / item


def make_distribution(root):
    (root / "pytest").mkdir(parents=True)
    (root / "pytest-9.0.3.dist-info").mkdir(parents=True)

    (root / "pytest/__init__.py").write_text(
        "from .core import value\n"
    )
    (root / "pytest/core.py").write_text(
        "value = 1\n"
    )
    (root / "pytest-9.0.3.dist-info/METADATA").write_text(
        "Name: pytest\nVersion: 9.0.3\n"
    )

    return FakeDistribution(root)


def test_installed_source_mutation_changes_content_identity(
    tmp_path, monkeypatch
):
    # distribution_content_identity requires the files to belong to the
    # active environment prefix. Bind the helper's sys.prefix to this
    # synthetic environment only for this focused unit test.
    monkeypatch.setattr(environment.sys, "prefix", str(tmp_path))

    dist = make_distribution(tmp_path)

    before = environment.distribution_content_identity(dist)

    (tmp_path / "pytest/core.py").write_text(
        "value = 999\n"
    )

    after = environment.distribution_content_identity(dist)

    assert before["file_count"] == after["file_count"]
    assert before["sha256"] != after["sha256"]


def test_metadata_mutation_changes_content_identity(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(environment.sys, "prefix", str(tmp_path))

    dist = make_distribution(tmp_path)

    before = environment.distribution_content_identity(dist)

    (tmp_path / "pytest-9.0.3.dist-info/METADATA").write_text(
        "Name: pytest\nVersion: FORGED\n"
    )

    after = environment.distribution_content_identity(dist)

    assert before["sha256"] != after["sha256"]



class PhysicalInventoryDistribution:
    def __init__(self, prefix, files):
        self.prefix = prefix
        self.files = tuple(Path(item) for item in files)
        self.metadata = {"Name": "fixture"}
        self.version = "1.0"

    def locate_file(self, item):
        return self.prefix / item


def bind_physical_layout(tmp_path, monkeypatch):
    site = tmp_path / "site-packages"
    scripts = tmp_path / "bin"

    site.mkdir()
    scripts.mkdir()

    monkeypatch.setattr(
        environment.sys,
        "prefix",
        str(tmp_path),
    )

    def get_path(name):
        if name in {"purelib", "platlib"}:
            return str(site)
        if name == "scripts":
            return str(scripts)
        raise AssertionError(name)

    monkeypatch.setattr(
        environment.sysconfig,
        "get_path",
        get_path,
    )

    return site, scripts


def test_unowned_site_file_is_rejected(
    tmp_path,
    monkeypatch,
):
    site, scripts = bind_physical_layout(
        tmp_path,
        monkeypatch,
    )

    owned = site / "owned.py"
    owned.write_text("value = 1\n")

    rogue = site / "rogue.py"
    rogue.write_text("value = 999\n")

    dist = PhysicalInventoryDistribution(
        tmp_path,
        ["site-packages/owned.py"],
    )

    with pytest.raises(
        ValueError,
        match="QUALIFICATION_SITE_INVENTORY_UNOWNED",
    ):
        environment.environment_physical_inventory(
            [dist]
        )


def test_unowned_console_script_is_rejected(
    tmp_path,
    monkeypatch,
):
    site, scripts = bind_physical_layout(
        tmp_path,
        monkeypatch,
    )

    owned = site / "owned.py"
    owned.write_text("value = 1\n")

    rogue = scripts / "rogue-command"
    rogue.write_text("#!/bin/sh\nexit 0\n")

    dist = PhysicalInventoryDistribution(
        tmp_path,
        ["site-packages/owned.py"],
    )

    with pytest.raises(
        ValueError,
        match="QUALIFICATION_SCRIPT_INVENTORY_UNOWNED",
    ):
        environment.environment_physical_inventory(
            [dist]
        )


def test_standard_venv_activation_scripts_are_bound(
    tmp_path,
    monkeypatch,
):
    site, scripts = bind_physical_layout(
        tmp_path,
        monkeypatch,
    )

    owned = site / "owned.py"
    owned.write_text("value = 1\n")

    activate = scripts / "activate"
    activate.write_text("ORIGINAL\n")

    dist = PhysicalInventoryDistribution(
        tmp_path,
        ["site-packages/owned.py"],
    )

    before = environment.environment_physical_inventory(
        [dist]
    )

    activate.write_text("MUTATED\n")

    after = environment.environment_physical_inventory(
        [dist]
    )

    assert before["scripts"]["file_count"] == 1
    assert after["scripts"]["file_count"] == 1
    assert (
        before["scripts"]["sha256"]
        != after["scripts"]["sha256"]
    )
    assert before["venv_bootstrap_scripts"] == [
        "bin/activate"
    ]


def test_metadata_owned_physical_inventory_is_exact(
    tmp_path,
    monkeypatch,
):
    site, scripts = bind_physical_layout(
        tmp_path,
        monkeypatch,
    )

    module = site / "owned.py"
    module.write_text("value = 1\n")

    command = scripts / "owned-command"
    command.write_text("#!/bin/sh\nexit 0\n")

    dist = PhysicalInventoryDistribution(
        tmp_path,
        [
            "site-packages/owned.py",
            "bin/owned-command",
        ],
    )

    result = (
        environment.environment_physical_inventory(
            [dist]
        )
    )

    assert result["site_packages"]["file_count"] == 1
    assert result["scripts"]["file_count"] == 1
    assert result["metadata_owned_site_files"] == 1
    assert result["metadata_owned_script_files"] == 1
    assert result["venv_bootstrap_scripts"] == []



def test_base_import_inventory_binds_stdlib_and_dynload(
    monkeypatch,
):
    import sys
    import sysconfig

    repo = Path(__file__).resolve().parents[1]
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    dynload = (
        Path(sys.base_exec_prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "lib-dynload"
    ).resolve()
    purelib = Path(sysconfig.get_path("purelib")).resolve()
    platlib = Path(sysconfig.get_path("platlib")).resolve()

    clean_sys_path = [
        str(repo),
        str(stdlib),
        str(dynload),
    ]

    for candidate in (purelib, platlib):
        value = str(candidate)
        if value not in clean_sys_path:
            clean_sys_path.append(value)

    monkeypatch.setattr(
        sys,
        "path",
        clean_sys_path,
    )

    result = environment.base_import_inventory(repo)

    assert result["stdlib"]["file_count"] > 0
    assert result["stdlib"]["sha256"]
    assert result["lib_dynload"]["file_count"] > 0
    assert result["lib_dynload"]["sha256"]
    assert result["sys_path_directories"][0] == str(repo)


def test_import_tree_rejects_external_symlink(tmp_path):
    root = tmp_path / 'root'
    outside = tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    (outside / 'module.py').write_text('value = 1\n')
    (root / 'link.py').symlink_to(outside / 'module.py')

    with pytest.raises(
        ValueError,
        match='QUALIFICATION_IMPORT_SYMLINK_OUTSIDE_SURFACES',
    ):
        environment._tree_import_identity(
            root,
            permitted_roots=(root,),
        )

def test_documented_tools_launch_path_is_normalized_and_bound(
    monkeypatch,
):
    import sys
    import sysconfig

    repo = Path(__file__).resolve().parents[1]
    tools_root = (repo / "tools").resolve()
    launch = tools_root / "qualification_environment.py"
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    dynload = (
        Path(sys.base_exec_prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "lib-dynload"
    ).resolve()
    purelib = Path(sysconfig.get_path("purelib")).resolve()
    platlib = Path(sysconfig.get_path("platlib")).resolve()

    clean_sys_path = [
        str(tools_root),
        str(stdlib),
        str(dynload),
    ]
    for candidate in (purelib, platlib):
        value = str(candidate)
        if value not in clean_sys_path:
            clean_sys_path.append(value)

    main_module = sys.modules["__main__"]
    monkeypatch.setattr(
        main_module,
        "__file__",
        str(launch),
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [str(launch)],
    )
    monkeypatch.setattr(
        sys,
        "path",
        clean_sys_path,
    )

    result = environment.base_import_inventory(repo)

    assert result["sys_path_directories"][0] == str(repo)
    assert result["repository_tools"]["file_count"] > 0
    assert result["repository_tools"]["sha256"]


def test_site_topology_rejects_unowned_symlink(
    tmp_path,
    monkeypatch,
):
    site = tmp_path / "site-packages"
    scripts = tmp_path / "bin"
    site.mkdir()
    scripts.mkdir()

    target = site / "owned.py"
    target.write_text("VALUE = 1\n")
    (site / "unowned.py").symlink_to(target)

    class FakeDist:
        files = [Path("owned.py")]
        metadata = {"Name": "fake"}

        def locate_file(self, item):
            return site / item

    real_get_path = environment.sysconfig.get_path

    def fake_get_path(label):
        if label in ("purelib", "platlib"):
            return str(site)
        if label == "scripts":
            return str(scripts)
        return real_get_path(label)

    monkeypatch.setattr(
        environment.sysconfig,
        "get_path",
        fake_get_path,
    )
    monkeypatch.setattr(
        environment.sys,
        "prefix",
        str(tmp_path),
    )

    with pytest.raises(
        ValueError,
        match="QUALIFICATION_SITE_TOPOLOGY_UNOWNED",
    ):
        environment.environment_physical_inventory(
            [FakeDist()]
        )


def test_injected_tools_path_outside_launch_is_rejected(
    monkeypatch,
):
    import sys
    import sysconfig

    repo = Path(__file__).resolve().parents[1]
    tools_root = (repo / "tools").resolve()
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    dynload = (
        Path(sys.base_exec_prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "lib-dynload"
    ).resolve()
    purelib = Path(sysconfig.get_path("purelib")).resolve()
    platlib = Path(sysconfig.get_path("platlib")).resolve()

    injected = [
        str(repo),
        str(stdlib),
        str(dynload),
    ]
    for candidate in (purelib, platlib):
        value = str(candidate)
        if value not in injected:
            injected.append(value)
    injected.append(str(tools_root))

    monkeypatch.setattr(
        sys,
        "path",
        injected,
    )

    with pytest.raises(
        ValueError,
        match="QUALIFICATION_IMPORT_PATH_UNEXPECTED",
    ):
        environment.base_import_inventory(repo)
