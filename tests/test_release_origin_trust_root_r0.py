import os
from pathlib import Path

import pytest

from tools import release_origin


def test_external_hardlink_to_repository_storage_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    repo.mkdir()
    external.mkdir()

    inside = repo / "repository-owned-signers"
    inside.write_text("authority\n")
    authority = external / "allowed_signers"
    os.link(inside, authority)

    with pytest.raises(
        ValueError,
        match="ORIGIN_TRUST_ROOT_IN_REPOSITORY_STORAGE",
    ):
        release_origin._validate_trust_root_storage(repo, authority)


def test_group_writable_signer_authority_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    repo.mkdir()
    external.mkdir()

    authority = external / "allowed_signers"
    authority.write_text("authority\n")
    authority.chmod(0o660)

    with pytest.raises(
        ValueError,
        match="ORIGIN_TRUST_ROOT_MODE_UNSAFE",
    ):
        release_origin._validate_trust_root_storage(repo, authority)


def test_world_writable_signer_authority_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    repo.mkdir()
    external.mkdir()

    authority = external / "allowed_signers"
    authority.write_text("authority\n")
    authority.chmod(0o666)

    with pytest.raises(
        ValueError,
        match="ORIGIN_TRUST_ROOT_MODE_UNSAFE",
    ):
        release_origin._validate_trust_root_storage(repo, authority)


def test_independent_owner_only_signer_authority_is_accepted(tmp_path):
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    repo.mkdir()
    external.mkdir()

    authority = external / "allowed_signers"
    authority.write_text("authority\n")
    authority.chmod(0o600)

    identity = release_origin._validate_trust_root_storage(
        repo, authority
    )

    st = authority.stat()
    assert identity[:2] == (st.st_dev, st.st_ino)
    assert identity[3] == os.geteuid()
