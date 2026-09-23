from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/inference-native-r0.yml"
RUNNER = ROOT / "tools/run_inference_native_locus.py"

WORKFLOW_MARKERS = (
    "native/hacf/file_assets_r0",
    "ELPIS_FMS_FILE_LIBRARY",
    "ELPIS_INFERENCE_WORKSPACE",
    "TMPDIR",
    "libelpis_fms_file_assets_r0.so",
    "provider-sentinel.xml",
    "inference-native.xml",
    "provider-execution.json",
    "locus-execution.json",
    "tools/verify_inference_native_locus.py --check",
    "python tools/run_inference_native_locus.py",
    "--section provider",
    "--section locus",
    "scipy==1.17.1",
    "RUNNER_TEMP",
    "GITHUB_ENV",
)

RUNNER_MARKERS = (
    "ExecutionRecorder",
    "pytest_runtest_logstart",
    'authority["nodeids"]',
    'authority["nodeids_sha256"]',
    "NATIVE_EXECUTED_NODE_SET_MISMATCH",
    "NATIVE_EXECUTED_NODE_SHA256_MISMATCH",
    "NATIVE_EXECUTION_JUNIT_NONPASS",
    "PASS_NATIVE_EXECUTED_EXACT_SET",
    '"failures": 0',
    '"errors": 0',
    '"skipped": 0',
)


def _workflow_errors(text: str) -> list[str]:
    errors = []
    for marker in WORKFLOW_MARKERS:
        if marker not in text:
            errors.append("MISSING_WORKFLOW:" + marker)
    if text.count("python tools/run_inference_native_locus.py") != 2:
        errors.append("RUNNER_INVOCATION_CARDINALITY")
    if "${{ runner.temp }}" in text:
        errors.append("FORBIDDEN_JOB_LEVEL_RUNNER_CONTEXT")
    return errors


def _runner_errors(text: str) -> list[str]:
    return [
        "MISSING_RUNNER:" + marker
        for marker in RUNNER_MARKERS
        if marker not in text
    ]


def test_native_inference_workflow_contract_is_explicit_and_complete():
    assert _workflow_errors(WORKFLOW.read_text(encoding="utf-8")) == []
    assert _runner_errors(RUNNER.read_text(encoding="utf-8")) == []


def test_native_inference_workflow_detects_removed_provider_authority():
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace("ELPIS_FMS_FILE_LIBRARY", "REMOVED_FMS_FILE_LIBRARY")
    assert "MISSING_WORKFLOW:ELPIS_FMS_FILE_LIBRARY" in _workflow_errors(mutated)


def test_native_inference_workflow_detects_exact_runner_removal():
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace(
        "python tools/run_inference_native_locus.py",
        "python REMOVED_EXACT_RUNNER.py",
        1,
    )
    assert "RUNNER_INVOCATION_CARDINALITY" in _workflow_errors(mutated)


def test_native_execution_runner_detects_set_guard_removal():
    text = RUNNER.read_text(encoding="utf-8")
    mutated = text.replace(
        "NATIVE_EXECUTED_NODE_SET_MISMATCH",
        "REMOVED_NODE_SET_GUARD",
    )
    assert (
        "MISSING_RUNNER:NATIVE_EXECUTED_NODE_SET_MISMATCH"
        in _runner_errors(mutated)
    )


def test_native_execution_runner_detects_sha_guard_removal():
    text = RUNNER.read_text(encoding="utf-8")
    mutated = text.replace(
        "NATIVE_EXECUTED_NODE_SHA256_MISMATCH",
        "REMOVED_NODE_SHA_GUARD",
    )
    assert (
        "MISSING_RUNNER:NATIVE_EXECUTED_NODE_SHA256_MISMATCH"
        in _runner_errors(mutated)
    )


def test_native_inference_workflow_rejects_job_level_runner_context():
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = text.replace(
        '"${RUNNER_TEMP}/elpis-inference-native"',
        '"${{ runner.temp }}/elpis-inference-native"',
        1,
    )
    assert "FORBIDDEN_JOB_LEVEL_RUNNER_CONTEXT" in _workflow_errors(mutated)
