from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/inference-native-r0.yml'

REQUIRED_TESTS = (
    'tests/test_inference_file_assets_r0.py',
    'tests/test_inference_rows_r0.py',
    'tests/test_inference_experts_r0.py',
    'tests/test_inference_neural_r0.py',
    'tests/test_inference_prefetch_r0.py',
    'tests/test_inference_runtime_r3.py',
    'tests/test_inference_speculative_r0.py',
    'runtime/R3/tests/',
)

PROVIDER_EXPECTED = (
    "expected = {'tests': 7, 'failures': 0, 'errors': 0, 'skipped': 0}"
)
LOCUS_EXPECTED = (
    "expected = {'tests': 149, 'failures': 0, 'errors': 0, 'skipped': 0}"
)


def _contract_errors(text: str) -> list[str]:
    errors = []
    required = (
        'native/hacf/file_assets_r0',
        'ELPIS_FMS_FILE_LIBRARY',
        'ELPIS_INFERENCE_WORKSPACE',
        'TMPDIR',
        'libelpis_fms_file_assets_r0.so',
        'provider-sentinel.xml',
        PROVIDER_EXPECTED,
        'NATIVE_PROVIDER_CORE_CARDINALITY_NONPASS',
        'NATIVE_PROVIDER_CORE_7_OF_7_PASS',
        '--junitxml=',
        'inference-native.xml',
        LOCUS_EXPECTED,
        'NATIVE_INFERENCE_LOCUS_CARDINALITY_NONPASS',
        'NATIVE_INFERENCE_LOCUS_149_OF_149_PASS',
        '-p no:cacheprovider',
        "PYTHONDONTWRITEBYTECODE: '1'",
    ) + REQUIRED_TESTS
    for marker in required:
        if marker not in text:
            errors.append('MISSING:' + marker)
    return errors


def test_native_inference_workflow_contract_is_explicit_and_complete():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert _contract_errors(text) == []


def test_native_inference_workflow_detects_removed_provider_authority():
    text = WORKFLOW.read_text(encoding='utf-8')
    mutated = text.replace('ELPIS_FMS_FILE_LIBRARY', 'REMOVED_FMS_FILE_LIBRARY')
    assert 'MISSING:ELPIS_FMS_FILE_LIBRARY' in _contract_errors(mutated)


def test_native_inference_workflow_detects_provider_cardinality_guard_removal():
    text = WORKFLOW.read_text(encoding='utf-8')
    mutated = text.replace(
        'NATIVE_PROVIDER_CORE_CARDINALITY_NONPASS',
        'REMOVED_PROVIDER_CARDINALITY_GUARD',
    )
    assert 'MISSING:NATIVE_PROVIDER_CORE_CARDINALITY_NONPASS' in _contract_errors(mutated)


def test_native_inference_workflow_detects_provider_exact_count_removal():
    text = WORKFLOW.read_text(encoding='utf-8')
    mutated = text.replace(PROVIDER_EXPECTED, 'expected = {}')
    assert 'MISSING:' + PROVIDER_EXPECTED in _contract_errors(mutated)


def test_native_inference_workflow_detects_locus_exact_count_removal():
    text = WORKFLOW.read_text(encoding='utf-8')
    mutated = text.replace(LOCUS_EXPECTED, 'expected = {}')
    assert 'MISSING:' + LOCUS_EXPECTED in _contract_errors(mutated)
