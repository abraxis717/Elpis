"""Injectable Git/gh/HTTP boundary for release_orchestrator; no import-time I/O."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from tools import release_orchestrator as machine
except (ModuleNotFoundError, ImportError):
    import release_orchestrator as machine

require = machine.require
publication = machine.publication


class Runner:
    def command(self, argv: list[str], *, cwd: Path, data: bytes | None = None):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_TERMINAL_PROMPT='0', GH_PROMPT_DISABLED='1')
        return subprocess.run(argv, cwd=cwd, input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env, check=False)

    def http_json(self, url: str):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise machine.ReleaseError(f'HTTP_OBSERVATION_FAILED:{exc.code}:{url}') from exc
        except (OSError, ValueError) as exc:
            raise machine.ReleaseError(f'HTTP_OBSERVATION_FAILED:{url}') from exc


class LiveBoundary:
    def __init__(self, root: Path, qualification: Path, *, runner=None, execute=False):
        self.root = root
        self.qualification = qualification
        self.runner = runner or Runner()
        self.execute = execute

    def command(self, argv, *, data=None):
        result = self.runner.command(argv, cwd=self.root, data=data)
        require(result.returncode == 0,
                f"COMMAND_FAILED:{argv[0]}:{result.returncode}:{result.stderr.decode(errors='replace').strip()}")
        return result.stdout

    def git(self, *args, data=None):
        return self.command(['git', *args], data=data).decode().strip()

    def private_directory(self):
        # Common-dir serializes linked worktrees as well as duplicate invocations.
        path = Path(self.git('rev-parse', '--git-common-dir'))
        if not path.is_absolute():
            path = self.root / path
        private = path.resolve() / 'elpis-release-orchestrator-v1'
        if not private.exists():
            private.mkdir()
            publication._fsync_directory(private.parent)
        return private

    def api(self, endpoint, *, payload=None):
        argv = ['gh', 'api', '--hostname', 'github.com', '--include',
                '--method', 'GET' if payload is None else 'POST', endpoint]
        data = None
        if payload is not None:
            require(self.execute, 'REMOTE_MUTATION_DISABLED')
            argv += ['--input', '-']
            data = machine.canonical(payload)
        result = self.runner.command(argv, cwd=self.root, data=data)
        raw = result.stdout.replace(b'\r\n', b'\n')
        header, separator, body = raw.partition(b'\n\n')
        fields = header.split(b'\n', 1)[0].split()
        require(separator != b'' and len(fields) >= 2 and fields[0].startswith(b'HTTP/'),
                'GITHUB_HTTP_RESPONSE_INVALID')
        status = int(fields[1])
        if status == 404 and payload is None:
            return None
        require(200 <= status < 300 and result.returncode == 0, f'GITHUB_API_FAILED:{status}:{endpoint}')
        return json.loads(body)

    def remote_url(self, intent):
        # Use a fixed explicit URL, never a mutable remote alias or pushurl.
        return 'https://github.com/' + intent['repository'] + '.git'

    def remote_refs(self, intent):
        tag = 'refs/tags/' + machine.tag_name(intent)
        raw = self.git('ls-remote', self.remote_url(intent), 'refs/heads/main', tag, tag + '^{}')
        result = {}
        for line in raw.splitlines():
            oid, ref = line.split('\t')
            require(ref not in result and bool(publication.HEX_RE.fullmatch(oid)), 'REMOTE_REFS_INVALID')
            result[ref] = oid
        return result

    def local_tag(self, intent):
        ref = 'refs/tags/' + machine.tag_name(intent)
        # --quiet exit 1 is absence; all other errors fail closed.
        result = self.runner.command(['git', 'show-ref', '--verify', '--quiet', ref], cwd=self.root)
        if result.returncode == 1:
            return None
        require(result.returncode == 0, 'LOCAL_TAG_OBSERVATION_FAILED')
        oid = self.git('rev-parse', '--verify', ref)
        kind = self.git('cat-file', '-t', oid)
        require(kind == 'tag', 'ANNOTATED_TAG_REQUIRED')
        peeled = self.git('rev-parse', '--verify', ref + '^{commit}')
        return {'tag_object': oid, 'tag_object_type': kind, 'peeled_commit': peeled,
                'peeled_object_type': self.git('cat-file', '-t', peeled)}

    def remote_tag(self, intent, refs=None):
        refs = self.remote_refs(intent) if refs is None else refs
        ref = 'refs/tags/' + machine.tag_name(intent)
        if ref not in refs:
            require(ref + '^{}' not in refs, 'REMOTE_TAG_REF_MISSING')
            return None
        require(ref + '^{}' in refs, 'ANNOTATED_TAG_REQUIRED')
        # An expected annotated object binds its own commit type and bytes.
        return {'tag_object': refs[ref], 'tag_object_type': 'tag',
                'peeled_commit': refs[ref + '^{}'], 'peeled_object_type': 'commit'}

    def release(self, intent):
        row = self.api(f"repos/{intent['repository']}/releases/tags/{machine.tag_name(intent)}")
        if row is None:
            return None
        require(row.get('draft') is False and row.get('prerelease') is False,
                'GITHUB_RELEASE_DRAFT_OR_PRERELEASE')
        require(row.get('tag_name') == machine.tag_name(intent) and row.get('name') == machine.tag_name(intent),
                'GITHUB_RELEASE_MISMATCH')
        require(hashlib.sha256(row.get('body', '').encode()).hexdigest() == intent['notes_sha256'],
                'GITHUB_RELEASE_NOTES_MISMATCH')
        require(row.get('target_commitish') == intent['candidate_sha'], 'GITHUB_RELEASE_TARGET_MISMATCH')
        return {'repository': intent['repository'], 'release_id': row['id'],
                'tag_name': row['tag_name'], 'published_at': row['published_at']}

    def preflight(self, intent, evidence):
        require(self.git('rev-parse', '--show-toplevel') == str(self.root), 'REPOSITORY_ROOT_MISMATCH')
        require(self.git('rev-parse', '--is-shallow-repository') == 'false', 'REPOSITORY_HISTORY_INCOMPLETE')
        require(self.git('rev-parse', 'HEAD') == intent['candidate_sha'], 'LOCAL_HEAD_MISMATCH')
        require((self.root / 'VERSION').read_text().strip() == intent['version'], 'LOCAL_VERSION_MISMATCH')
        require(machine.tag_name(intent) not in publication._failed_tags(self.root), 'FAILED_RELEASE_FORBIDDEN')
        legacy = publication._legacy_records(self.root)
        require(all(row['release_tag'] != machine.tag_name(intent) for row in legacy), 'LEGACY_RELEASE_IMMUTABLE')
        registry = publication.load_registry(self.root)
        require(registry['legacy_publication_history'] == publication._legacy_identity(self.root),
                'FROZEN_LEGACY_IDENTITY_MISMATCH')
        rows = registry['publication_assertions']
        require(not any(row['release_tag'] == machine.tag_name(intent) for row in rows)
                or 'PUBLICATION_RECEIPT_READY' in evidence, 'PREEXISTING_PUBLICATION_ASSERTION')
        # Only this release's exact appended assertion may dirty the checkout.
        dirty = self.command(['git', 'status', '--porcelain', '--untracked-files=all']).decode().rstrip('\n')
        for line in dirty.splitlines():
            require(line[3:] == publication.REGISTRY_NAME and
                    'PUBLICATION_RECEIPT_READY' in evidence, f'WORKTREE_NOT_CLEAN:{line}')
        committed = json.loads(self.command(['git', 'show', 'HEAD:' + publication.REGISTRY_NAME]))
        old = committed['publication_assertions']
        require(rows == old or (rows[:-1] == old and rows[-1] == machine.expected_assertion(intent, evidence)),
                'PUBLICATION_REGISTRY_PREFIX_CHANGED')
        require({k: v for k, v in registry.items() if k != 'publication_assertions'} ==
                {k: v for k, v in committed.items() if k != 'publication_assertions'}, 'REGISTRY_AUTHORITY_CHANGED')
        refs = self.remote_refs(intent)
        require(refs.get('refs/heads/main') in {intent['main_before'], intent['candidate_sha']}, 'MAIN_SHA_MISMATCH')
        if 'MAIN_PUSHED' in evidence:
            require(refs.get('refs/heads/main') == intent['candidate_sha'], 'JOURNAL_AHEAD_OF_REALITY:MAIN_PUSHED')
        for state, tag in (('ANNOTATED_TAG_LOCAL_CREATED', self.local_tag(intent)),
                           ('ANNOTATED_TAG_CREATED', self.remote_tag(intent, refs))):
            if state in evidence:
                require(tag is not None, 'JOURNAL_AHEAD_OF_REALITY:' + state)
                require(tag == evidence[state], 'JOURNAL_REMOTE_CONFLICT:' + state)
            if tag is not None:
                machine.validate_tag(tag, intent)
                require('MAIN_HOSTED_GREEN' in evidence, 'TAG_EXISTS_BEFORE_HOSTED_GREEN')
        release = self.release(intent)
        if 'GITHUB_RELEASE_PUBLISHED' in evidence:
            require(release is not None, 'JOURNAL_AHEAD_OF_REALITY:GITHUB_RELEASE_PUBLISHED')
            require(release == evidence['GITHUB_RELEASE_PUBLISHED'],
                    'JOURNAL_REMOTE_CONFLICT:GITHUB_RELEASE_PUBLISHED')
        if release is not None:
            require('TAG_HOSTED_GREEN' in evidence, 'RELEASE_EXISTS_BEFORE_TAG_GREEN')
        notes = (self.root / 'RELEASE_NOTES' / (machine.tag_name(intent) + '.md')).read_bytes()
        require(hashlib.sha256(notes).hexdigest() == intent['notes_sha256'], 'LOCAL_NOTES_DIGEST_MISMATCH')

    def workflows(self, state, intent):
        branch = 'main' if state == 'MAIN_HOSTED_GREEN' else machine.tag_name(intent)
        runs = {}
        waiting = False
        for key, (_, path, event) in machine.action_specs(state, intent).items():
            rows = []
            for page in range(1, 12):
                endpoint = (f"repos/{intent['repository']}/actions/workflows/{path}/runs"
                            f"?head_sha={intent['candidate_sha']}&event={event}&per_page=100&page={page}")
                result = self.api(endpoint)
                require(result is not None, f'WORKFLOW_UNAVAILABLE:{path}')
                require(result['total_count'] <= 1000, 'WORKFLOW_CENSUS_TRUNCATED')
                rows += result['workflow_runs']
                if len(rows) >= result['total_count']:
                    break
                require(len(result['workflow_runs']) == 100, 'WORKFLOW_CENSUS_INCOMPLETE')
            matches = [r for r in rows if r['head_branch'] == branch and r['head_sha'] == intent['candidate_sha']
                       and r['event'] == event]
            require(len(matches) <= 1, f'WORKFLOW_WITNESS_AMBIGUOUS:{key}')
            if not matches:
                waiting = True
                continue
            r = matches[0]
            require(r['run_attempt'] == 1, f'WORKFLOW_RERUN_FORBIDDEN:{key}')
            if r['status'] != 'completed':
                waiting = True
                continue
            # A failed required workflow wins over another workflow still pending.
            require(r['conclusion'] == 'success', f"REQUIRED_WORKFLOW_FAILED:{key}:{r['conclusion']}")
            runs[key] = {k: r[k] for k in ('path', 'event', 'head_sha', 'head_branch', 'run_attempt',
                                          'status', 'conclusion', 'created_at', 'updated_at')}
            runs[key].update(workflow=r['name'], run_id=r['id'], repository=r['repository']['full_name'])
        return None if waiting else runs

    def observe(self, state, intent, evidence):
        if state == 'LOCAL_QUALIFIED':
            raw = self.qualification.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == intent['qualification_sha256'], 'QUALIFICATION_DIGEST_MISMATCH')
            report = json.loads(raw)
            require(set(report) == {'schema', 'candidate_sha', 'manifest_sha256', 'checks'}, 'QUALIFICATION_FIELDS_INVALID')
            require(report['schema'] == 'elpis.release-orchestrator.qualification.v1', 'QUALIFICATION_SCHEMA_INVALID')
            require(report['candidate_sha'] == intent['candidate_sha'] and
                    report['manifest_sha256'] == intent['manifest_sha256'], 'QUALIFICATION_CANDIDATE_MISMATCH')
            require(set(report['checks']) == {'root_tests', 'release_lifecycle', 'negative_mutations',
                                             'installed_artifact', 'native'}, 'QUALIFICATION_CHECKS_INCOMPLETE')
            for name, check in report['checks'].items():
                require(set(check) == {'argv', 'exit_code', 'output_sha256'} and check['exit_code'] == 0 and
                        isinstance(check['argv'], list) and bool(check['argv']) and
                        all(isinstance(a, str) for a in check['argv']) and
                        bool(publication.SHA256_RE.fullmatch(check['output_sha256'])), f'QUALIFICATION_NONPASS:{name}')
            return {'candidate_sha': intent['candidate_sha'], 'qualification_sha256': intent['qualification_sha256']}
        if state == 'SEALED_CANDIDATE':
            rel = f'manifests/{machine.tag_name(intent)}.RELEASE_MANIFEST.json'
            raw = self.command(['git', 'show', intent['candidate_sha'] + ':' + rel])
            require(raw == (self.root / rel).read_bytes(), 'CHECKOUT_MANIFEST_DIFFERS_FROM_CANDIDATE')
            manifest = json.loads(raw)
            require(manifest['version'] == intent['version'] and manifest['release_tag'] == machine.tag_name(intent)
                    and manifest['schema'] == 'elpis.release-manifest.v3', 'MANIFEST_IDENTITY_MISMATCH')
            self.command([sys.executable, 'tools/verify_public_release.py'])
            self.command([sys.executable, 'tools/verify_public_release.py', '--verify-candidate-repository-identity'])
            return {'candidate_sha': intent['candidate_sha'], 'manifest_sha256': hashlib.sha256(raw).hexdigest()}
        if state == 'MAIN_PUSHED':
            sha = self.remote_refs(intent).get('refs/heads/main')
            if sha == intent['main_before'] and sha != intent['candidate_sha']:
                return None
            return {'main_sha': sha}
        if state == 'ANNOTATED_TAG_LOCAL_CREATED':
            return self.local_tag(intent)
        if state == 'ANNOTATED_TAG_CREATED':
            return self.remote_tag(intent)
        if state.endswith('_GREEN'):
            return self.workflows(state, intent)
        if state == 'GITHUB_RELEASE_PUBLISHED':
            return self.release(intent)
        if state == 'PYPI_EXTERNALLY_OBSERVED':
            row = self.runner.http_json(f"https://pypi.org/pypi/elpisai/{intent['version']}/json")
            if row is None:
                return None
            files = [{**{k: f[k] for k in ('filename', 'packagetype', 'upload_time_iso_8601', 'yanked')},
                      'sha256': f['digests']['sha256']} for f in row['urls']]
            return {'project': row['info']['name'], 'version': row['info']['version'],
                    'files': sorted(files, key=lambda f: f['filename'])}
        if state == 'PUBLICATION_RECEIPT_READY':
            receipt = machine.external_receipt(intent, evidence)
            return {'schema': machine.RECEIPT_SCHEMA, 'receipt_sha256': machine.digest(receipt), 'receipt': receipt}
        if state == 'PUBLICATION_ASSERTION_APPENDED':
            rows = publication.load_registry(self.root)['publication_assertions']
            matches = [r for r in rows if r['release_tag'] == machine.tag_name(intent)]
            require(len(matches) <= 1, 'PUBLICATION_ASSERTION_DUPLICATE')
            if not matches:
                return None
            errors = publication.validation_errors(self.root)
            require(not errors, 'PUBLICATION_ASSERTIONS_INVALID:' + '|'.join(errors))
            return matches[0]
        if state == 'CLOSED':
            return {'assertion_sha256': machine.digest(evidence['PUBLICATION_ASSERTION_APPENDED']),
                    'receipt_sha256': evidence['PUBLICATION_RECEIPT_READY']['receipt_sha256']}
        raise machine.ReleaseError('UNKNOWN_STATE:' + state)

    def mutate(self, state, intent, evidence):
        require(self.execute, 'REMOTE_MUTATION_DISABLED')
        if state == 'MAIN_PUSHED':
            self.git('merge-base', '--is-ancestor', intent['main_before'], intent['candidate_sha'])
            # Lease is only a CAS. The independent ancestry proof forbids non-FF updates.
            self.git('push', '--porcelain', '--no-follow-tags',
                     '--force-with-lease=refs/heads/main:' + intent['main_before'],
                     self.remote_url(intent), intent['candidate_sha'] + ':refs/heads/main')
            return {'main_sha': intent['candidate_sha']}
        if state == 'ANNOTATED_TAG_LOCAL_CREATED':
            oid = self.git('mktag', data=machine.tag_bytes(intent))
            require(oid == machine.tag_identity(intent)['tag_object'], 'GENERATED_TAG_OBJECT_MISMATCH')
            self.git('update-ref', 'refs/tags/' + machine.tag_name(intent), oid, '0' * len(oid))
            return machine.tag_identity(intent)
        if state == 'ANNOTATED_TAG_CREATED':
            self.git('push', '--porcelain', '--no-follow-tags', self.remote_url(intent),
                     machine.tag_identity(intent)['tag_object'] + ':refs/tags/' + machine.tag_name(intent))
            return machine.tag_identity(intent)
        if state == 'GITHUB_RELEASE_PUBLISHED':
            notes = (self.root / 'RELEASE_NOTES' / (machine.tag_name(intent) + '.md')).read_text()
            result = self.api(f"repos/{intent['repository']}/releases", payload={
                'tag_name': machine.tag_name(intent), 'target_commitish': intent['candidate_sha'],
                'name': machine.tag_name(intent), 'body': notes, 'draft': False, 'prerelease': False,
                'generate_release_notes': False})
            return {'release_id': result['id'], 'response': result}
        if state == 'PUBLICATION_ASSERTION_APPENDED':
            receipt = evidence['PUBLICATION_RECEIPT_READY']['receipt']
            path = self.private_directory() / (machine.digest(receipt) + '.receipt.json')
            if path.exists():
                require(path.read_bytes() == machine.canonical(receipt), 'RECEIPT_FILE_CONFLICT')
            else:
                publication._atomic_replace(path, machine.canonical(receipt))
            return publication.append_receipt(self.root, path)
        raise machine.ReleaseError('MUTATION_NOT_ALLOWED:' + state)
