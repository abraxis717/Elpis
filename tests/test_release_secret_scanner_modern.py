from __future__ import annotations

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_public_release.py"


def _scan(tmp_path: Path, text: str):
    probe = tmp_path / "probe.txt"
    probe.write_text(text, encoding="utf-8")
    ns = runpy.run_path(str(VERIFIER))
    scan = ns["scan_findings"]
    scan.__globals__["REPO"] = tmp_path
    findings, errors = scan()
    assert errors == []
    return findings


def _kinds(findings):
    return {
        kind
        for (_path, kind, _digest), count in findings.items()
        if count
    }


def test_modern_openai_project_key_is_detected(tmp_path: Path) -> None:
    token = "sk-" + "proj-" + ("A" * 40)
    kinds = _kinds(_scan(tmp_path, token))
    assert "SECRET:OpenAI-style key" in kinds


def test_modern_openai_service_account_key_is_detected(
    tmp_path: Path,
) -> None:
    token = "sk-" + "svcacct-" + ("B" * 40)
    kinds = _kinds(_scan(tmp_path, token))
    assert "SECRET:OpenAI-style key" in kinds


def test_aws_temporary_access_key_id_is_detected(
    tmp_path: Path,
) -> None:
    token = "AS" + "IA" + ("A1" * 8)
    kinds = _kinds(_scan(tmp_path, token))
    assert "SECRET:AWS key" in kinds


def test_gitlab_pat_is_detected(tmp_path: Path) -> None:
    token = "gl" + "pat-" + ("C" * 24)
    kinds = _kinds(_scan(tmp_path, token))
    assert "SECRET:GitLab PAT" in kinds


def test_slack_bot_token_is_detected(tmp_path: Path) -> None:
    token = "xo" + "xb-" + "1234567890-abcdefghij-ABCDEFGHIJ"
    kinds = _kinds(_scan(tmp_path, token))
    assert "SECRET:Slack token" in kinds


def test_openssh_private_key_header_is_detected(
    tmp_path: Path,
) -> None:
    marker = "-----BEGIN OPEN" + "SSH PRIVATE KEY-----"
    kinds = _kinds(_scan(tmp_path, marker))
    assert "SECRET:private key" in kinds


def test_rsa_private_key_header_is_detected(tmp_path: Path) -> None:
    marker = "-----BEGIN R" + "SA PRIVATE KEY-----"
    kinds = _kinds(_scan(tmp_path, marker))
    assert "SECRET:private key" in kinds


def test_short_and_public_near_misses_are_not_detected(
    tmp_path: Path,
) -> None:
    probes = "\n".join(
        [
            "sk-" + "proj-short",
            "AS" + "IA" + ("A" * 15),
            "gl" + "pat-short",
            "xo" + "xb-short",
            "-----BEGIN OPEN" + "SSH PUBLIC KEY-----",
        ]
    )
    assert _kinds(_scan(tmp_path, probes)) == set()


def test_token_embedded_in_identifier_is_not_detected(
    tmp_path: Path,
) -> None:
    token = "prefix_" + "gl" + "pat-" + ("D" * 24) + "_suffix"
    assert _kinds(_scan(tmp_path, token)) == set()


def test_current_repository_has_no_unallowlisted_new_secret_findings() -> None:
    ns = runpy.run_path(str(VERIFIER))
    ok, errors = ns["check_private_data"]()
    assert ok, errors
