from pathlib import Path, PurePosixPath

from tools import qualification_environment as environment


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
