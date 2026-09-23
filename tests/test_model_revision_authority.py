import hashlib
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
from elpis_reference import model


def test_revision_matches_packaged_authority():
    authority = json.loads((Path(model.__file__).parent / "vendor/fprm/AUTHORITY.json").read_text())
    assert model.MODEL_REVISION == authority["checkpoint"]["upstream_revision"] == "6e871275e9b8f95036c6003fd6366f3811565ac6"
    assert model.MODEL_SHA256 == authority["checkpoint"]["sha256"]


@pytest.mark.parametrize("corrupt", [False, True])
def test_download_is_revision_pinned_and_digest_checked(tmp_path, monkeypatch, corrupt):
    raw = tmp_path / "download"
    raw.write_bytes(b"correct fixture")
    monkeypatch.setattr(model, "MODEL_SHA256", hashlib.sha256(raw.read_bytes()).hexdigest())
    if corrupt:
        raw.write_bytes(b"corrupt fixture")
    observed = []
    def download(**kwargs):
        observed.append(kwargs)
        return str(raw)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(hf_hub_download=download))
    monkeypatch.setattr(model, "require_torch", lambda: None)
    validated = []
    monkeypatch.setattr(model, "verify_model", lambda path: validated.append(path))
    if corrupt:
        with pytest.raises(RuntimeError, match="authority mismatch"):
            model.fetch_model(tmp_path / "cache")
        assert not validated
        assert not (tmp_path / "cache" / model.MODEL_FILENAME).exists()
    else:
        path = model.fetch_model(tmp_path / "cache")
        assert path.read_bytes() == raw.read_bytes() and validated == [path]
    assert observed[0]["revision"] == model.MODEL_REVISION
    assert observed[0]["repo_id"] == model.MODEL_REPO
