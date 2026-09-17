from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/INFERENCE_PLUGIN_TRUST_BOUNDARY.md"
MANIFEST = ROOT / "manifests/INFERENCE_PLUGIN_TRUST_BOUNDARY_R0.json"
DISCOVERY = (
    ROOT
    / "components/TRMFractalSpine/src/elpis_fractal_spine/plugin_discovery.py"
)
ACTIVATION = (
    ROOT
    / "components/TRMFractalSpine/src/elpis_fractal_spine/provider_activation.py"
)
MODEL_PORTS = ROOT / "components/TRMFractalSpine/registry/model_ports.toml"
PORTABILITY = ROOT / "docs/PLATFORM_PORTABILITY.md"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_threat_model_declares_exact_trusted_installed_environment_boundary():
    data = _manifest()
    assert data["schema"] == "elpis.inference-plugin-trust-boundary.v1"
    assert data["trust_boundary"] == "TRUSTED_INSTALLED_ENVIRONMENT"
    assert data["semi_untrusted_plugins_admitted"] is False
    assert data["process_isolation_claimed"] is False

    nonclaims = data["nonclaims"]
    assert nonclaims == {
        "deep_runtime_context_immutability": False,
        "pre_load_cryptographic_code_identity": False,
        "transactional_plugin_import_rollback": False,
        "caller_supplied_model_ports_identity_equivalence": False,
    }


def test_n10_through_n13_are_documented_as_boundaries_not_remediated_claims():
    data = _manifest()
    findings = data["findings"]
    assert [item["finding_id"] for item in findings] == [
        "N10", "N11", "N12", "N13"
    ]
    assert all(
        item["disposition"] == "DOCUMENTED_TRUST_BOUNDARY"
        for item in findings
    )
    assert all(item["technical_remediation_claimed"] is False for item in findings)


def test_threat_model_source_bindings_match_exact_current_objects():
    data = _manifest()
    expected = {
        str(DISCOVERY.relative_to(ROOT)): _sha(DISCOVERY),
        str(ACTIVATION.relative_to(ROOT)): _sha(ACTIVATION),
        str(MODEL_PORTS.relative_to(ROOT)): _sha(MODEL_PORTS),
        str(PORTABILITY.relative_to(ROOT)): _sha(PORTABILITY),
    }
    actual = {
        item["path"]: item["sha256"] for item in data["source_bindings"]
    }
    assert actual == expected


def test_current_code_still_exhibits_the_four_documented_findings():
    discovery = DISCOVERY.read_text(encoding="utf-8")
    activation = ACTIVATION.read_text(encoding="utf-8")

    # N10: metadata provenance is collected, but there is no pre-load code digest.
    assert "distribution_name" in discovery
    assert "distribution_version" in discovery
    assert "entry_point_value" in discovery
    assert "factory = record.entry_point.load()" in discovery
    assert "distribution_sha256" not in discovery
    assert "module_sha256" not in discovery

    # N11: the selected EntryPoint is imported in-process.
    assert "factory = record.entry_point.load()" in discovery

    # N12: activation parses the caller-supplied model_ports_path directly.
    assert "_load_model_ports(Path(model_ports_path))" in activation
    assert 'Path(path).read_text(encoding="utf-8")' in activation

    # N13: MappingProxyType protects only the copied top-level dict.
    assert "context = MappingProxyType(dict(runtime_context))" in activation


def test_human_document_matches_machine_readable_nonclaims():
    text = DOC.read_text(encoding="utf-8")
    for marker in (
        "Installed inference-driver distributions are trusted host code.",
        "does **not** claim pre-load code identity",
        "does **not** claim transactional plugin import",
        "does **not** claim arbitrary caller-supplied",
        "top-level mapping immutability",
        "semi-untrusted installed driver code: **not admitted**",
    ):
        assert marker in text


def test_existing_portability_document_already_places_installation_at_host_trust_boundary():
    text = PORTABILITY.read_text(encoding="utf-8")
    assert (
        "Installation of a local plugin wheel is the host\n"
        "trust boundary"
    ) in text
