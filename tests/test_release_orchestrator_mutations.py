"""Guard-disable qualification on isolated in-memory source copies.

The negative input must first fail for the named diagnostic. Disabling that
specific require must break that regression (acceptance or WRONG_GUARD_FIRED).
No remote boundary is instantiated. Prints machine-readable mutation evidence.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import release_orchestrator as m
from test_release_orchestrator import intent, runs, FakeBoundary


CASES = (
    'ANNOTATED_TAG_REQUIRED', 'TAG_PEELED_COMMIT_MISMATCH', 'TAG_OBJECT_MISMATCH',
    'MAIN_SHA_MISMATCH', 'SEALED_CANDIDATE_MISMATCH', 'WORKFLOW_SHA_MISMATCH',
    'WORKFLOW_REF_MISMATCH', 'REQUIRED_WORKFLOW_FAILED', 'WORKFLOW_RUN_ID_DUPLICATE',
    'PUBLICATION_RECEIPT_IDENTITY_MISMATCH', 'PUBLICATION_ASSERTION_CONFLICT',
    'HISTORICAL_RELEASE_IMMUTABLE',
)


def exercise(module, code, tmp_path):
    i = intent()
    if code.startswith('HISTORICAL'):
        module.validate_intent(dict(i, version='2.2.25'))
    elif code in {'ANNOTATED_TAG_REQUIRED', 'TAG_PEELED_COMMIT_MISMATCH', 'TAG_OBJECT_MISMATCH'}:
        value = m.tag_identity(i)
        value[{'ANNOTATED_TAG_REQUIRED': 'tag_object_type', 'TAG_PEELED_COMMIT_MISMATCH': 'peeled_commit',
               'TAG_OBJECT_MISMATCH': 'tag_object'}[code]] = 'wrong'
        module.validate_tag(value, i)
    elif code.startswith(('WORKFLOW_', 'REQUIRED_WORKFLOW_')):
        value = runs('MAIN_HOSTED_GREEN', i)
        if code == 'WORKFLOW_RUN_ID_DUPLICATE':
            value['main_ci']['run_id'] = value['main_reference_runtime']['run_id']
        else:
            field = {'WORKFLOW_SHA_MISMATCH': 'head_sha', 'WORKFLOW_REF_MISMATCH': 'head_branch',
                     'REQUIRED_WORKFLOW_FAILED': 'conclusion'}[code]
            value['main_ci'][field] = 'wrong'
        module.validate_actions('MAIN_HOSTED_GREEN', value, i)
    else:
        state = {'MAIN_SHA_MISMATCH': 'MAIN_PUSHED', 'SEALED_CANDIDATE_MISMATCH': 'SEALED_CANDIDATE',
                 'PUBLICATION_RECEIPT_IDENTITY_MISMATCH': 'PUBLICATION_RECEIPT_READY',
                 'PUBLICATION_ASSERTION_CONFLICT': 'PUBLICATION_ASSERTION_APPENDED'}[code]
        b = FakeBoundary(i)
        evidence = copy.deepcopy(b.values)
        evidence['GITHUB_RELEASE_PUBLISHED'] = {'repository': i['repository'], 'tag_name': m.tag_name(i),
            'release_id': 1, 'published_at': '2027-01-21T00:00:00Z'}
        module.Orchestrator(b, module.Journal(tmp_path / 'unused', i)).validate(state, {}, evidence)


def result(module, code, tmp_path):
    try:
        exercise(module, code, tmp_path)
    except ValueError as exc:
        diagnostic = str(exc)
        return (1 if diagnostic.startswith(code) else 2), diagnostic
    return 0, 'ACCEPTED_MUTATION'


@pytest.mark.parametrize('code', CASES)
def test_negative_guard_detects_its_own_removal(tmp_path, code):
    source = Path(m.__file__).read_bytes()
    normal_status, diagnostic = result(m, code, tmp_path)
    assert normal_status == 1, 'WRONG_GUARD_FIRED:' + diagnostic
    tree = ast.parse(source)
    changed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'require':
            literals = [n.value for n in ast.walk(node.args[1]) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            if any(s.startswith(code) for s in literals):
                node.args[0] = ast.Constant(value=True)
                changed += 1
    assert changed > 0
    namespace = {'__name__': 'isolated_orchestrator_mutant', '__file__': m.__file__}
    exec(compile(ast.fix_missing_locations(tree), '<isolated-orchestrator-mutant>', 'exec'), namespace)
    disabled_status, disabled_diagnostic = result(SimpleNamespace(**namespace), code, tmp_path)
    # The permanent named-diagnostic regression must detect this guard's absence.
    assert disabled_status != 1, 'GUARD_DISABLE_MUTANT_SURVIVED'
    print(json.dumps({'source_sha256': hashlib.sha256(source).hexdigest(), 'mutation': code,
                      'positive_guard_exit': normal_status, 'diagnostic': diagnostic,
                      'disabled_guard_exit': disabled_status, 'disabled_diagnostic': disabled_diagnostic,
                      'regression_detected_removal': True}, sort_keys=True))
