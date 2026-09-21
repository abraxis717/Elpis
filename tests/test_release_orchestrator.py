"""Fault injection at durable boundaries; no real remote execution is possible."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import release_orchestrator as m
from tools import release_orchestrator_io as io


def intent():
    return {'schema': m.SCHEMA, 'repository': 'abraxis717/Elpis', 'version': '2.2.26',
            'candidate_sha': 'a' * 40, 'main_before': 'b' * 40, 'manifest_sha256': 'c' * 64,
            'qualification_sha256': 'd' * 64, 'notes_sha256': 'e' * 64,
            'tagger': 'Release Test <test@example.invalid> 1800576000 +0000'}


def runs(state, i):
    index = m.STATES.index(state)
    date = '2027-01-22' if state in {'RELEASE_EVENT_GREEN', 'PYPI_WORKFLOW_GREEN'} else '2027-01-20'
    return {key: {'workflow': name, 'path': '.github/workflows/' + path, 'event': event,
                  'head_sha': i['candidate_sha'], 'head_branch': 'main' if state == 'MAIN_HOSTED_GREEN' else m.tag_name(i),
                  'run_id': index * 100 + n, 'run_attempt': 1, 'status': 'completed', 'conclusion': 'success',
                  'created_at': date + 'T00:00:00Z', 'updated_at': date + 'T01:00:00Z',
                  'repository': i['repository']}
            for n, (key, (name, path, event)) in enumerate(m.action_specs(state).items())}


class Crash(BaseException):
    pass


class FakeBoundary:
    def __init__(self, i):
        self.i = i
        self.calls = []
        self.values = {
            'LOCAL_QUALIFIED': {'candidate_sha': i['candidate_sha'], 'qualification_sha256': i['qualification_sha256']},
            'SEALED_CANDIDATE': {'candidate_sha': i['candidate_sha'], 'manifest_sha256': i['manifest_sha256']},
            **{s: runs(s, i) for s in m.STATES if s.endswith('_GREEN')},
            'PYPI_EXTERNALLY_OBSERVED': {'project': 'elpisai', 'version': i['version'], 'files': [
                {'filename': 'elpisai-2.2.26-py3-none-any.whl', 'packagetype': 'bdist_wheel', 'sha256': '1' * 64,
                 'upload_time_iso_8601': '2027-01-22T01:00:00Z', 'yanked': False},
                {'filename': 'elpisai-2.2.26.tar.gz', 'packagetype': 'sdist', 'sha256': '2' * 64,
                 'upload_time_iso_8601': '2027-01-22T01:01:00Z', 'yanked': False},
            ]},
        }
        self.crash = None
        self.observe_hook = None

    def preflight(self, i, evidence):
        self.calls.append(('preflight', tuple(evidence)))
        for s in ('ANNOTATED_TAG_LOCAL_CREATED', 'ANNOTATED_TAG_CREATED'):
            if self.values.get(s) is not None:
                m.validate_tag(self.values[s], i)
                m.require('MAIN_HOSTED_GREEN' in evidence, 'TAG_EXISTS_BEFORE_HOSTED_GREEN')
        if self.values.get('GITHUB_RELEASE_PUBLISHED') is not None:
            m.require('TAG_HOSTED_GREEN' in evidence, 'RELEASE_EXISTS_BEFORE_TAG_GREEN')

    def observe(self, state, i, evidence):
        self.calls.append(('observe', state))
        if self.observe_hook:
            self.observe_hook(state)
        if state in self.values:
            return copy.deepcopy(self.values[state])
        if state == 'PUBLICATION_RECEIPT_READY':
            receipt = m.external_receipt(i, evidence)
            return {'schema': m.RECEIPT_SCHEMA, 'receipt_sha256': m.digest(receipt), 'receipt': receipt}
        if state == 'CLOSED':
            return {'assertion_sha256': m.digest(evidence['PUBLICATION_ASSERTION_APPENDED']),
                    'receipt_sha256': evidence['PUBLICATION_RECEIPT_READY']['receipt_sha256']}
        return None

    def mutate(self, state, i, evidence):
        self.calls.append(('mutate', state))
        if state == 'MAIN_PUSHED':
            result = {'main_sha': i['candidate_sha']}
        elif state.startswith('ANNOTATED_TAG'):
            # The engine must already have persisted main workflow proof.
            assert 'MAIN_HOSTED_GREEN' in evidence
            result = m.tag_identity(i)
        elif state == 'GITHUB_RELEASE_PUBLISHED':
            assert 'TAG_HOSTED_GREEN' in evidence
            result = {'repository': i['repository'], 'release_id': 923, 'tag_name': m.tag_name(i),
                      'published_at': '2027-01-21T00:00:00Z'}
        elif state == 'PUBLICATION_ASSERTION_APPENDED':
            result = m.expected_assertion(i, evidence)
        else:
            raise AssertionError(state)
        self.values[state] = result
        if self.crash == state:
            raise Crash(state)
        return copy.deepcopy(result)


def setup(tmp_path):
    i = intent()
    boundary = FakeBoundary(i)
    path = tmp_path / 'journal.json'
    return i, boundary, path


def run(i, boundary, path):
    return m.Orchestrator(boundary, m.Journal(path, i)).run()


def mutations(boundary):
    return [s for kind, s in boundary.calls if kind == 'mutate']


def test_positive_control_duplicate_invocation(tmp_path):
    i, b, p = setup(tmp_path)
    result = run(i, b, p)
    original = p.read_bytes()
    assert run(i, b, p) == result
    assert p.read_bytes() == original
    assert mutations(b) == [s for s in m.STATES if s in m.MUTATIONS]
    evidence, active = m.Journal(p, i).replay()
    assert tuple(evidence) == m.STATES and active is None
    assert m.publication._validate_external_receipt(evidence['PUBLICATION_RECEIPT_READY']['receipt'],
             tag=m.tag_name(i), peeled=i['candidate_sha'])


@pytest.mark.parametrize('state', sorted(m.MUTATIONS))
def test_remote_success_lost_response_reconciled_once(tmp_path, state):
    i, b, p = setup(tmp_path)
    b.crash = state
    with pytest.raises(Crash):
        run(i, b, p)
    assert m.Journal(p, i).replay()[1]['kind'] == 'intent'
    b.crash = None
    run(i, b, p)
    assert mutations(b).count(state) == 1


@pytest.mark.parametrize('state,kind', [(s, k) for s in m.STATES for k in ('returned', 'complete')
                                      if k == 'complete' or s in m.MUTATIONS])
def test_interrupt_after_every_durable_transition(tmp_path, monkeypatch, state, kind):
    i, b, p = setup(tmp_path)
    write = m.Journal.write
    def crash(journal, s, k, data):
        write(journal, s, k, data)
        if (s, k) == (state, kind):
            raise Crash(s)
    monkeypatch.setattr(m.Journal, 'write', crash)
    with pytest.raises(Crash):
        run(i, b, p)
    monkeypatch.setattr(m.Journal, 'write', write)
    run(i, b, p)
    assert all(mutations(b).count(s) == 1 for s in m.MUTATIONS)


@pytest.mark.parametrize('state', sorted(m.MUTATIONS))
def test_acknowledgment_is_fsynced_before_first_verification(tmp_path, state):
    i, b, p = setup(tmp_path)
    def inspect(s):
        if s == state and s in mutations(b):
            active = m.Journal(p, i).replay()[1]
            assert active['state'] == state and active['kind'] == 'returned'
            raise Crash('verification crashed')
    b.observe_hook = inspect
    with pytest.raises(Crash):
        run(i, b, p)
    b.observe_hook = None
    run(i, b, p)
    assert mutations(b).count(state) == 1


@pytest.mark.parametrize('state', sorted(m.MUTATIONS))
def test_uncertain_absence_never_retried(tmp_path, state):
    i, b, p = setup(tmp_path)
    b.crash = state
    with pytest.raises(Crash):
        run(i, b, p)
    del b.values[state]
    with pytest.raises(m.ReleaseError, match='AMBIGUOUS_MUTATION_OUTCOME:' + state):
        run(i, b, p)
    assert mutations(b).count(state) == 1


def test_stale_journal_reconciles_remote_ahead(tmp_path):
    i, b, p = setup(tmp_path)
    b.crash = 'GITHUB_RELEASE_PUBLISHED'
    with pytest.raises(Crash):
        run(i, b, p)
    # Model a backup that predates the request but retains its prerequisite proof.
    journal = json.loads(p.read_bytes())
    journal['events'].pop()
    p.write_bytes(m.canonical(journal))
    b.crash = None
    run(i, b, p)
    assert mutations(b).count('GITHUB_RELEASE_PUBLISHED') == 1


@pytest.mark.parametrize('state', sorted(m.MUTATIONS))
def test_journal_ahead_fails_closed(tmp_path, state):
    i, b, p = setup(tmp_path)
    run(i, b, p)
    del b.values[state]
    calls = list(mutations(b))
    with pytest.raises(m.ReleaseError, match='JOURNAL_AHEAD_OF_REALITY:' + state):
        run(i, b, p)
    assert mutations(b) == calls


@pytest.mark.parametrize('field,value,diagnostic', [
    ('tag_object_type', 'commit', 'ANNOTATED_TAG_REQUIRED'),
    ('peeled_commit', 'f' * 40, 'TAG_PEELED_COMMIT_MISMATCH'),
    ('tag_object', 'f' * 40, 'TAG_OBJECT_MISMATCH'),
    ('peeled_object_type', 'tree', 'PEELED_OBJECT_TYPE_MISMATCH'),
])
def test_wrong_preexisting_tag_never_repaired(tmp_path, field, value, diagnostic):
    i, b, p = setup(tmp_path)
    b.values['ANNOTATED_TAG_CREATED'] = dict(m.tag_identity(i), **{field: value})
    with pytest.raises(m.ReleaseError, match=diagnostic):
        run(i, b, p)
    assert not mutations(b)


def test_even_correct_tag_cannot_invent_main_gate(tmp_path):
    i, b, p = setup(tmp_path)
    b.values['ANNOTATED_TAG_CREATED'] = m.tag_identity(i)
    with pytest.raises(m.ReleaseError, match='TAG_EXISTS_BEFORE_HOSTED_GREEN'):
        run(i, b, p)
    assert not mutations(b)


@pytest.mark.parametrize('state', [s for s in m.STATES if s.endswith('_GREEN')])
@pytest.mark.parametrize('field,value,diagnostic', [
    ('head_sha', 'f' * 40, 'WORKFLOW_SHA_MISMATCH'),
    ('head_branch', 'wrong', 'WORKFLOW_REF_MISMATCH'),
    ('event', 'workflow_dispatch', 'WORKFLOW_EVENT_MISMATCH'),
    ('conclusion', 'failure', 'REQUIRED_WORKFLOW_FAILED'),
    ('conclusion', 'cancelled', 'REQUIRED_WORKFLOW_FAILED'),
    ('conclusion', 'skipped', 'REQUIRED_WORKFLOW_FAILED'),
    ('run_attempt', 2, 'WORKFLOW_RERUN_FORBIDDEN'),
    ('repository', 'other/Elpis', 'WORKFLOW_REPOSITORY_MISMATCH'),
    ('path', '.github/workflows/unrelated.yml', 'WORKFLOW_IDENTITY_MISMATCH'),
])
def test_workflow_guards(tmp_path, state, field, value, diagnostic):
    i, b, p = setup(tmp_path)
    next(iter(b.values[state].values()))[field] = value
    with pytest.raises(m.ReleaseError, match=diagnostic):
        run(i, b, p)
    next_state = m.STATES[m.STATES.index(state) + 1]
    assert next_state not in [e['state'] for e in json.loads(p.read_bytes())['events'] if e['kind'] == 'complete']


def test_duplicate_workflow_witness_across_events(tmp_path):
    i, b, p = setup(tmp_path)
    b.values['TAG_HOSTED_GREEN']['tag_ci']['run_id'] = b.values['MAIN_HOSTED_GREEN']['main_ci']['run_id']
    with pytest.raises(m.ReleaseError, match='WORKFLOW_RUN_ID_DUPLICATE'):
        run(i, b, p)
    assert 'GITHUB_RELEASE_PUBLISHED' not in mutations(b)


def test_changed_release_id_on_resume(tmp_path):
    i, b, p = setup(tmp_path)
    run(i, b, p)
    b.values['GITHUB_RELEASE_PUBLISHED']['release_id'] += 1
    with pytest.raises(m.ReleaseError, match='JOURNAL_REMOTE_CONFLICT:GITHUB_RELEASE_PUBLISHED'):
        run(i, b, p)


@pytest.mark.parametrize('change,diagnostic', [
    ('missing', 'PYPI_EXPECTED_EXACT_WHEEL_AND_SDIST'),
    ('digest', 'PYPI_SHA256_INVALID'),
    ('yanked', 'PYPI_FILE_YANKED'),
    ('filename', 'PYPI_FILENAME_VERSION_MISMATCH'),
    ('time', 'TIMESTAMP_INVALID'),
])
def test_incomplete_or_wrong_pypi_cannot_append(tmp_path, change, diagnostic):
    i, b, p = setup(tmp_path)
    files = b.values['PYPI_EXTERNALLY_OBSERVED']['files']
    if change == 'missing':
        files.pop()
    elif change == 'digest':
        files[0]['sha256'] = 'not a digest'
    elif change == 'yanked':
        files[0]['yanked'] = True
    elif change == 'filename':
        files[0]['filename'] = 'elpisai-2.2.25-py3-none-any.whl'
    else:
        files[0]['upload_time_iso_8601'] = 'yesterday'
    with pytest.raises(ValueError, match=diagnostic):
        run(i, b, p)
    assert 'PUBLICATION_ASSERTION_APPENDED' not in mutations(b)


def test_malformed_receipt_never_appended(tmp_path):
    i, b, p = setup(tmp_path)
    b.values['PUBLICATION_RECEIPT_READY'] = {'schema': m.RECEIPT_SCHEMA, 'receipt': {}, 'receipt_sha256': 'f' * 64}
    with pytest.raises(m.ReleaseError, match='PUBLICATION_RECEIPT_IDENTITY_MISMATCH'):
        run(i, b, p)
    assert 'PUBLICATION_ASSERTION_APPENDED' not in mutations(b)


def test_append_conflict_never_overwritten(tmp_path):
    i, b, p = setup(tmp_path)
    b.values['PUBLICATION_ASSERTION_APPENDED'] = {'release_tag': m.tag_name(i)}
    with pytest.raises(m.ReleaseError, match='PUBLICATION_ASSERTION_CONFLICT'):
        run(i, b, p)
    assert 'PUBLICATION_ASSERTION_APPENDED' not in mutations(b)


def test_main_mismatch(tmp_path):
    i, b, p = setup(tmp_path)
    b.values['MAIN_PUSHED'] = {'main_sha': 'f' * 40}
    with pytest.raises(m.ReleaseError, match='MAIN_SHA_MISMATCH'):
        run(i, b, p)
    assert not mutations(b)


def test_stale_intent_and_corrupt_journal(tmp_path):
    i, b, p = setup(tmp_path)
    run(i, b, p)
    with pytest.raises(m.ReleaseError, match='JOURNAL_INTENT_CONFLICT'):
        m.Journal(p, dict(i, candidate_sha='f' * 40))
    data = json.loads(p.read_bytes())
    data['events'][0]['data']['candidate_sha'] = 'f' * 40
    p.write_bytes(m.canonical(data))
    with pytest.raises(m.ReleaseError, match='JOURNAL_CHAIN_INVALID'):
        m.Journal(p, i)


@pytest.mark.parametrize('version', ['2.2.19', '2.2.20', '2.2.21', '2.2.22', '2.2.23', '2.2.24', '2.2.25'])
def test_published_history_immutable(version):
    with pytest.raises(m.ReleaseError, match='HISTORICAL_RELEASE_IMMUTABLE'):
        m.validate_intent(dict(intent(), version=version))


def test_default_cli_zero_commands(tmp_path, monkeypatch, capsys):
    i = intent()
    path = tmp_path / 'intent.json'
    path.write_bytes(m.canonical(i))
    def forbidden(*args, **kwargs):
        raise AssertionError('A dry-run reached the command boundary')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(io.Runner, 'http_json', forbidden)
    assert m.main(['--intent', str(path)]) == 0
    assert 'DRY_RUN_NO_COMMANDS' in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(m.ReleaseError, match='REMOTE_MUTATION_DISABLED'):
        io.LiveBoundary(tmp_path, path).mutate('MAIN_PUSHED', i, {})


def test_fsync_failure_stops_before_mutation(tmp_path, monkeypatch):
    i, b, p = setup(tmp_path)
    real = m.publication._atomic_replace
    def fail(path, raw):
        if json.loads(raw)['events'][-1]['kind'] == 'intent':
            raise OSError('injected fsync failure')
        real(path, raw)
    monkeypatch.setattr(m.publication, '_atomic_replace', fail)
    with pytest.raises(OSError, match='injected fsync failure'):
        run(i, b, p)
    assert not mutations(b)
