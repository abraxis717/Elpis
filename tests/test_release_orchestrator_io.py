"""Exercise the production boundary with recorded HTTP and isolated local Git."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import release_orchestrator as m
from tools import release_orchestrator_io as io
from test_release_orchestrator import intent, runs, FakeBoundary, Crash, run, mutations


class RecordedRunner:
    def __init__(self, replies=()):
        self.replies = list(replies)
        self.calls = []

    def command(self, argv, *, cwd, data=None):
        self.calls.append((argv, data))
        assert self.replies, f'unexpected command: {argv}'
        return self.replies.pop(0)


def response(value, status=200, code=0):
    return subprocess.CompletedProcess([], code,
        f'HTTP/2.0 {status} Status\r\nContent-Type: application/json\r\n\r\n'.encode() + m.canonical(value), b'')


@pytest.mark.parametrize('status,diagnostic', [(401, 'GITHUB_API_FAILED:401'), (403, 'GITHUB_API_FAILED:403'),
                                             (429, 'GITHUB_API_FAILED:429'), (500, 'GITHUB_API_FAILED:500')])
def test_http_failures_are_not_absence(tmp_path, status, diagnostic):
    runner = RecordedRunner([response({'message': 'failed'}, status, 1)])
    boundary = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=runner)
    with pytest.raises(m.ReleaseError, match=diagnostic):
        boundary.api('repos/abraxis717/Elpis/releases/tags/Elpis2.2.26')
    assert len(runner.calls) == 1


def test_http_404_and_transport_failure_distinct(tmp_path):
    runner = RecordedRunner([response({}, 404, 1), subprocess.CompletedProcess([], 1, b'', b'network unavailable')])
    boundary = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=runner)
    assert boundary.api('absent') is None
    with pytest.raises(m.ReleaseError, match='GITHUB_HTTP_RESPONSE_INVALID'):
        boundary.api('unknown')


def api_run(row):
    result = dict(row)
    result['id'] = result.pop('run_id')
    result['name'] = result.pop('workflow')
    result['repository'] = {'full_name': result['repository']}
    return result


def test_production_workflow_census_and_exact_witnesses(tmp_path):
    i = intent()
    expected = runs('MAIN_HOSTED_GREEN', i)
    replies = [response({'total_count': 1, 'workflow_runs': [api_run(r)]}) for r in expected.values()]
    runner = RecordedRunner(replies)
    b = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=runner)
    assert b.workflows('MAIN_HOSTED_GREEN', i) == expected
    assert all('head_sha=' + i['candidate_sha'] in call[0][-1] for call in runner.calls)


def test_production_workflow_duplicate_not_arbitrarily_selected(tmp_path):
    row = api_run(next(iter(runs('MAIN_HOSTED_GREEN', intent()).values())))
    runner = RecordedRunner([response({'total_count': 2, 'workflow_runs': [row, dict(row, id=99999)]})])
    b = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=runner)
    with pytest.raises(m.ReleaseError, match='WORKFLOW_WITNESS_AMBIGUOUS:main_ci'):
        b.workflows('MAIN_HOSTED_GREEN', intent())


def test_failed_workflow_wins_over_pending(tmp_path):
    rows = list(runs('MAIN_HOSTED_GREEN', intent()).values())
    rows[0]['status'] = 'queued'
    rows[1]['conclusion'] = 'failure'
    runner = RecordedRunner([response({'total_count': 1, 'workflow_runs': [api_run(r)]}) for r in rows[:2]])
    b = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=runner)
    with pytest.raises(m.ReleaseError, match='REQUIRED_WORKFLOW_FAILED:main_reference_runtime:failure'):
        b.workflows('MAIN_HOSTED_GREEN', intent())


@pytest.mark.parametrize('total,rows,diagnostic', [(1001, [], 'WORKFLOW_CENSUS_TRUNCATED'),
                                                (2, [], 'WORKFLOW_CENSUS_INCOMPLETE')])
def test_incomplete_workflow_census(tmp_path, total, rows, diagnostic):
    runner = RecordedRunner([response({'total_count': total, 'workflow_runs': rows})])
    b = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=runner)
    with pytest.raises(m.ReleaseError, match=diagnostic):
        b.workflows('MAIN_HOSTED_GREEN', intent())


@pytest.mark.parametrize('field,value,diagnostic', [
    ('draft', True, 'GITHUB_RELEASE_DRAFT_OR_PRERELEASE'),
    ('prerelease', True, 'GITHUB_RELEASE_DRAFT_OR_PRERELEASE'),
    ('tag_name', 'Elpis2.2.25', 'GITHUB_RELEASE_MISMATCH'),
    ('body', 'wrong', 'GITHUB_RELEASE_NOTES_MISMATCH'),
    ('target_commitish', 'main', 'GITHUB_RELEASE_TARGET_MISMATCH'),
])
def test_production_release_mismatch(tmp_path, field, value, diagnostic):
    i = intent()
    i['notes_sha256'] = hashlib.sha256(b'notes').hexdigest()
    row = {'draft': False, 'prerelease': False, 'tag_name': m.tag_name(i), 'name': m.tag_name(i),
           'body': 'notes', 'target_commitish': i['candidate_sha']}
    row[field] = value
    b = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=RecordedRunner([response(row)]))
    with pytest.raises(m.ReleaseError, match=diagnostic):
        b.release(i)


def test_production_remote_lightweight_and_wrong_peeled(tmp_path):
    b = io.LiveBoundary(tmp_path, tmp_path / 'q', runner=RecordedRunner())
    i = intent()
    ref = 'refs/tags/' + m.tag_name(i)
    with pytest.raises(m.ReleaseError, match='ANNOTATED_TAG_REQUIRED'):
        b.remote_tag(i, {ref: i['candidate_sha']})
    tag = b.remote_tag(i, {ref: m.tag_identity(i)['tag_object'], ref + '^{}': 'f' * 40})
    with pytest.raises(m.ReleaseError, match='TAG_PEELED_COMMIT_MISMATCH'):
        m.validate_tag(tag, i)


class LocalOnlyRunner(io.Runner):
    """Even a broken orchestrator cannot push or access HTTP in this fixture."""
    def command(self, argv, *, cwd, data=None):
        assert argv[0] == 'git' and argv[1] not in {'push', 'fetch', 'ls-remote', 'clone'}
        return super().command(argv, cwd=cwd, data=data)

    def http_json(self, url):
        raise AssertionError('network forbidden')


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def seed(repo):
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'manifests').mkdir()
    (repo / 'VERSION').write_text('2.2.26\n')
    (repo / 'RELEASE_NOTES').mkdir()
    (repo / 'RELEASE_NOTES/Elpis2.2.26.md').write_text('notes\n')
    manifest = {'release_tag': 'Elpis2.2.26', 'version': '2.2.26'}
    (repo / 'manifests/Elpis2.2.26.RELEASE_MANIFEST.json').write_bytes(m.canonical(manifest))
    (repo / 'PUBLISHED_RELEASES.json').write_bytes(m.canonical({
        'schema': 'elpis.published-releases.v1', 'source_of_truth': 'refs/tags/Elpis<semver>', 'published_releases': []}))
    (repo / 'FAILED_RELEASES.json').write_bytes(m.canonical({'schema': 'elpis.failed-releases.v1', 'failed_releases': []}))
    (repo / 'PUBLICATION_ASSERTIONS.json').write_bytes(m.canonical(m.publication.empty_registry(repo)))
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'fixture seal')
    i = intent()
    i['candidate_sha'] = git(repo, 'rev-parse', 'HEAD')
    i['notes_sha256'] = hashlib.sha256(b'notes\n').hexdigest()
    i['manifest_sha256'] = hashlib.sha256(m.canonical(manifest)).hexdigest()
    return i


def test_actual_local_tag_object_and_v2_append_restart(tmp_path):
    repo = tmp_path / 'repo'
    i = seed(repo)
    b = FakeBoundary(i)
    live = io.LiveBoundary(repo, tmp_path / 'q', runner=LocalOnlyRunner(), execute=True)
    original_mutate = b.mutate
    original_observe = b.observe
    def mutate(state, i, evidence):
        if state in {'ANNOTATED_TAG_LOCAL_CREATED', 'PUBLICATION_ASSERTION_APPENDED'}:
            b.calls.append(('mutate', state))
            result = live.mutate(state, i, evidence)
            b.values[state] = result
            if state == 'PUBLICATION_ASSERTION_APPENDED':
                raise Crash('registry replaced before journal acknowledgment')
            return result
        return original_mutate(state, i, evidence)
    def observe(state, i, evidence):
        if state in {'ANNOTATED_TAG_LOCAL_CREATED', 'PUBLICATION_ASSERTION_APPENDED'}:
            return live.observe(state, i, evidence)
        return original_observe(state, i, evidence)
    b.mutate, b.observe = mutate, observe
    frozen = (repo / 'PUBLISHED_RELEASES.json').read_bytes()
    p = tmp_path / 'journal'
    with pytest.raises(Crash):
        run(i, b, p)
    assert live.local_tag(i) == m.tag_identity(i)
    assert git(repo, 'cat-file', '-p', m.tag_identity(i)['tag_object']) + '\n' == m.tag_bytes(i).decode()
    run(i, b, p)
    assert mutations(b).count('PUBLICATION_ASSERTION_APPENDED') == 1
    assert len(m.publication.load_registry(repo)['publication_assertions']) == 1
    assert not m.publication.validation_errors(repo)
    assert (repo / 'PUBLISHED_RELEASES.json').read_bytes() == frozen
    # Exercise production preflight on the legitimate dirty registry after append.
    remote_refs = {'refs/heads/main': i['candidate_sha'],
                   'refs/tags/' + m.tag_name(i): m.tag_identity(i)['tag_object'],
                   'refs/tags/' + m.tag_name(i) + '^{}': i['candidate_sha']}
    live.remote_refs = lambda i: remote_refs
    live.release = lambda i: b.values['GITHUB_RELEASE_PUBLISHED']
    evidence, _ = m.Journal(p, i).replay()
    live.preflight(i, evidence)
    del remote_refs['refs/tags/' + m.tag_name(i)]
    del remote_refs['refs/tags/' + m.tag_name(i) + '^{}']
    with pytest.raises(m.ReleaseError, match='JOURNAL_AHEAD_OF_REALITY:ANNOTATED_TAG_CREATED'):
        live.preflight(i, evidence)
    remote_refs['refs/tags/' + m.tag_name(i)] = m.tag_identity(i)['tag_object']
    remote_refs['refs/tags/' + m.tag_name(i) + '^{}'] = i['candidate_sha']
    live.release = lambda i: None
    with pytest.raises(m.ReleaseError, match='JOURNAL_AHEAD_OF_REALITY:GITHUB_RELEASE_PUBLISHED'):
        live.preflight(i, evidence)
    (repo / 'VERSION').write_text('2.2.27\n')
    with pytest.raises(m.ReleaseError, match='LOCAL_VERSION_MISMATCH'):
        live.preflight(i, evidence)


def test_local_tag_compare_and_swap_cannot_overwrite(tmp_path):
    repo = tmp_path / 'repo'
    i = seed(repo)
    git(repo, 'tag', m.tag_name(i))
    before = git(repo, 'rev-parse', m.tag_name(i))
    b = io.LiveBoundary(repo, tmp_path / 'q', runner=LocalOnlyRunner(), execute=True)
    with pytest.raises(m.ReleaseError, match='COMMAND_FAILED:git'):
        b.mutate('ANNOTATED_TAG_LOCAL_CREATED', i, {})
    assert git(repo, 'rev-parse', m.tag_name(i)) == before


def test_failed_workflow_stays_failed_after_remote_changes(tmp_path):
    i = intent()
    b = FakeBoundary(i)
    b.values['MAIN_HOSTED_GREEN']['main_ci']['conclusion'] = 'failure'
    p = tmp_path / 'journal'
    with pytest.raises(m.ReleaseError, match='REQUIRED_WORKFLOW_FAILED:main_ci:failure'):
        run(i, b, p)
    b.values['MAIN_HOSTED_GREEN']['main_ci']['conclusion'] = 'success'
    with pytest.raises(m.ReleaseError, match='RELEASE_PERMANENTLY_FAILED:REQUIRED_WORKFLOW_FAILED'):
        run(i, b, p)
    assert 'ANNOTATED_TAG_LOCAL_CREATED' not in mutations(b)


def test_journal_atomic_write_fsyncs_file_and_directory(tmp_path, monkeypatch):
    events = []
    real_fsync = io.os.fsync
    real_replace = io.os.replace
    def fsync(fd):
        events.append('fsync')
        real_fsync(fd)
    def replace(source, dest):
        events.append('replace')
        real_replace(source, dest)
    monkeypatch.setattr(io.os, 'fsync', fsync)
    monkeypatch.setattr(io.os, 'replace', replace)
    journal = m.Journal(tmp_path / 'journal', intent())
    journal.write('LOCAL_QUALIFIED', 'complete', {'candidate_sha': 'a' * 40, 'qualification_sha256': 'd' * 64})
    assert events == ['fsync', 'replace', 'fsync']


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX process lock qualification')
def test_duplicate_process_waits_for_common_repository_lock(tmp_path):
    import select
    lock = tmp_path / 'common.lock'
    source = (
        'from pathlib import Path\n'
        'from tools.publication_assertions_v2 import _exclusive_lock\n'
        'import sys\n'
        'print("ready", flush=True)\n'
        'with _exclusive_lock(Path(sys.argv[1])):\n'
        '    print("acquired", flush=True)\n'
    )
    child = None
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(m.__file__).parents[1])
    try:
        with m.publication._exclusive_lock(lock):
            child = subprocess.Popen([sys.executable, '-c', source, str(lock)],
                cwd=Path(m.__file__).parents[1], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert child.stdout.readline() == b'ready\n'
            assert not select.select([child.stdout], [], [], 0.1)[0]
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0 and out == b'acquired\n' and not err
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
