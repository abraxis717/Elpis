"""Injectable Git/gh/HTTP boundary for release_orchestrator; no import-time I/O."""
from __future__ import annotations

import hashlib
import json
import os
import ssl
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


_SEALED_ENV_DROP = frozenset({
    "GIT_NAMESPACE",
    "GIT_SHALLOW_FILE",
    "GIT_PREFIX",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_GRAFT_FILE",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG",
    "GIT_COMMON_DIR",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_REPLACE_REF_BASE",
})

_SYSTEM_CA_FILES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ssl/cert.pem",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/ca-bundle.pem",
)


def sealed_subprocess_env():
    env = dict(os.environ)
    for key in tuple(env):
        if (
            key in _SEALED_ENV_DROP
            or key.startswith("GIT_CONFIG")
            or key.startswith("GIT_SSL_")
            or key.startswith("GIT_HTTP_")
            or key == "GIT_PROXY_COMMAND"
        ):
            env.pop(key, None)

    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GH_PROMPT_DISABLED"] = "1"

    # Ignore inherited system/global Git configuration. Repository-local
    # configuration remains visible so it can be explicitly audited.
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env


def _system_tls_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED

    for candidate in _SYSTEM_CA_FILES:
        if Path(candidate).is_file():
            context.load_verify_locations(cafile=candidate)
            return context

    raise machine.ReleaseError("SYSTEM_CA_BUNDLE_UNAVAILABLE")


def _direct_https_opener():
    # Explicitly disable environment-derived proxy discovery.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=_system_tls_context()),
    )


class Runner:
    def command(self, argv: list[str], *, cwd: Path, data: bytes | None = None):
        env = sealed_subprocess_env()
        return subprocess.run(argv, cwd=cwd, input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env, check=False)

    def http_json(self, url: str):
        try:
            with _direct_https_opener().open(url, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise machine.ReleaseError(f'HTTP_OBSERVATION_FAILED:{exc.code}:{url}') from exc
        except (OSError, ValueError, ssl.SSLError) as exc:
            raise machine.ReleaseError(f'HTTP_OBSERVATION_FAILED:{url}') from exc


def qualified_distribution_artifacts(report, version):
    checks = report.get("checks")
    require(
        isinstance(checks, dict),
        "QUALIFICATION_CHECKS_INVALID",
    )

    installed = checks.get("installed_artifact")
    require(
        isinstance(installed, dict),
        "QUALIFICATION_INSTALLED_ARTIFACT_INVALID",
    )

    artifacts = installed.get("artifacts")
    require(
        isinstance(artifacts, list) and len(artifacts) == 2,
        "QUALIFICATION_DISTRIBUTION_ARTIFACTS_INVALID",
    )

    normalized = []
    filenames = set()
    package_types = set()

    for item in artifacts:
        require(
            isinstance(item, dict)
            and set(item) == {
                "filename",
                "packagetype",
                "sha256",
            },
            "QUALIFICATION_DISTRIBUTION_ARTIFACT_FIELDS_INVALID",
        )

        filename = item["filename"]
        package_type = item["packagetype"]
        sha256 = item["sha256"]

        require(
            isinstance(filename, str) and bool(filename),
            "QUALIFICATION_DISTRIBUTION_FILENAME_INVALID",
        )
        require(
            package_type in {"sdist", "bdist_wheel"},
            "QUALIFICATION_DISTRIBUTION_TYPE_INVALID",
        )
        require(
            isinstance(sha256, str)
            and bool(publication.SHA256_RE.fullmatch(sha256)),
            "QUALIFICATION_DISTRIBUTION_SHA256_INVALID",
        )
        require(
            filename not in filenames,
            "QUALIFICATION_DISTRIBUTION_FILENAME_DUPLICATE",
        )

        filenames.add(filename)
        package_types.add(package_type)

        prefix = "elpisai-" + version
        if package_type == "sdist":
            require(
                filename == prefix + ".tar.gz",
                "QUALIFICATION_SDIST_FILENAME_INVALID",
            )
        else:
            require(
                filename.startswith(prefix + "-")
                and filename.endswith(".whl"),
                "QUALIFICATION_WHEEL_FILENAME_INVALID",
            )

        normalized.append(
            {
                "filename": filename,
                "packagetype": package_type,
                "sha256": sha256,
            }
        )

    require(
        package_types == {"sdist", "bdist_wheel"},
        "QUALIFICATION_DISTRIBUTION_TYPE_SET_INVALID",
    )

    return sorted(
        normalized,
        key=lambda item: item["filename"],
    )


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

    def git_result(self, *args, data=None):
        if args and args[0] in {
            'ls-remote',
            'push',
            'fetch',
        }:
            self.verify_git_transport_policy()

        argv = [
            'git',
            '--no-replace-objects',
            '-c',
            'core.hooksPath=/dev/null',
        ]
        if args and args[0] == 'push':
            argv.extend([
                '-c',
                'credential.helper=!gh auth git-credential',
            ])
        argv.extend(args)

        return self.runner.command(
            argv,
            cwd=self.root,
            data=data,
        )

    def git_bytes(self, *args, data=None):
        result = self.git_result(*args, data=data)
        require(
            result.returncode == 0,
            'COMMAND_FAILED:git:'
            + str(result.returncode)
            + ':'
            + result.stderr.decode(
                errors='replace'
            ).strip(),
        )
        return result.stdout

    def git(self, *args, data=None):
        return self.git_bytes(
            *args,
            data=data,
        ).decode().strip()

    def verify_git_transport_policy(self):
        checks = (
            (
                r'^url\..*\.(insteadOf|pushInsteadOf)$',
                'EFFECTIVE_GIT_URL_REWRITE_FORBIDDEN',
            ),
            (
                r'^(http\..*|remote\..*\.proxy|core\.gitProxy)$',
                'EFFECTIVE_GIT_HTTPS_OVERRIDE_FORBIDDEN',
            ),
        )

        for pattern, diagnostic in checks:
            result = self.runner.command(
                [
                    'git',
                    '--no-replace-objects',
                    'config',
                    '--show-origin',
                    '--show-scope',
                    '--get-regexp',
                    pattern,
                ],
                cwd=self.root,
            )

            require(
                result.returncode in {0, 1},
                'EFFECTIVE_GIT_CONFIG_OBSERVATION_FAILED',
            )
            require(
                result.returncode == 1
                or not result.stdout.strip(),
                diagnostic,
            )

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
        result = self.git_result(
            'show-ref',
            '--verify',
            '--quiet',
            ref,
        )
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
        require(
            row.get('target_commitish')
            == intent['candidate_sha'],
            'GITHUB_RELEASE_TARGET_MISMATCH',
        )
        machine.validate_release_body(
            intent,
            row.get('body', ''),
        )
        return {'repository': intent['repository'], 'release_id': row['id'],
                'tag_name': row['tag_name'], 'published_at': row['published_at']}

    def preflight(self, intent, evidence):
        if intent.get('schema') == machine.SIGNED_SCHEMA:
            self.verify_origin(intent)
            import importlib
            environment = importlib.import_module('tools.qualification_environment' if __package__ else 'qualification_environment')
            require(json.loads(self.qualification.read_bytes()).get('environment') == environment.authority(self.root),
                    'QUALIFICATION_ENVIRONMENT_CHANGED')
        require(self.git('rev-parse', '--show-toplevel') == str(self.root), 'REPOSITORY_ROOT_MISMATCH')
        require(self.git('rev-parse', '--is-shallow-repository') == 'false', 'REPOSITORY_HISTORY_INCOMPLETE')
        self.verify_git_transport_policy()
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
        dirty = self.git_bytes(
            'status',
            '--porcelain',
            '--untracked-files=all',
        ).decode().rstrip('\n')
        for line in dirty.splitlines():
            require(line[3:] == publication.REGISTRY_NAME and
                    'PUBLICATION_RECEIPT_READY' in evidence, f'WORKTREE_NOT_CLEAN:{line}')
        committed = json.loads(
            self.git_bytes(
                'show',
                'HEAD:' + publication.REGISTRY_NAME,
            )
        )
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
            signed = intent.get('schema') == machine.SIGNED_SCHEMA
            require(set(report) == {'schema', 'candidate_sha', 'manifest_sha256', 'checks'} | ({'environment'} if signed else set()), 'QUALIFICATION_FIELDS_INVALID')
            require(report['schema'] == 'elpis.release-orchestrator.qualification.' + ('v2' if signed else 'v1'), 'QUALIFICATION_SCHEMA_INVALID')
            require(report['candidate_sha'] == intent['candidate_sha'] and
                    report['manifest_sha256'] == intent['manifest_sha256'], 'QUALIFICATION_CANDIDATE_MISMATCH')
            require(set(report['checks']) == {'root_tests', 'release_lifecycle', 'negative_mutations',
                                             'installed_artifact', 'native'}, 'QUALIFICATION_CHECKS_INCOMPLETE')
            for name, check in report['checks'].items():
                expected_fields = {
                    'argv',
                    'exit_code',
                    'output_sha256',
                }
                if signed and name == 'installed_artifact':
                    expected_fields.add('artifacts')
                require(
                    set(check) == expected_fields
                    and check['exit_code'] == 0
                    and isinstance(check['argv'], list)
                    and bool(check['argv'])
                    and all(isinstance(a, str) for a in check['argv'])
                    and bool(
                        publication.SHA256_RE.fullmatch(
                            check['output_sha256']
                        )
                    ),
                    f'QUALIFICATION_NONPASS:{name}',
                )
            if signed:
                artifacts = qualified_distribution_artifacts(
                    report,
                    intent['version'],
                )
                require(
                    artifacts
                    == intent['distribution_artifacts'],
                    'QUALIFICATION_DISTRIBUTION_IDENTITY_MISMATCH',
                )
            return {'candidate_sha': intent['candidate_sha'], 'qualification_sha256': intent['qualification_sha256']}
        if state == 'SEALED_CANDIDATE':
            rel = f'manifests/{machine.tag_name(intent)}.RELEASE_MANIFEST.json'
            raw = self.git_bytes(
                'show',
                intent['candidate_sha'] + ':' + rel,
            )
            require(raw == (self.root / rel).read_bytes(), 'CHECKOUT_MANIFEST_DIFFERS_FROM_CANDIDATE')
            manifest = json.loads(raw)
            require(manifest['version'] == intent['version'] and manifest['release_tag'] == machine.tag_name(intent)
                    and manifest['schema'] == 'elpis.release-manifest.v3', 'MANIFEST_IDENTITY_MISMATCH')
            self.command([sys.executable, 'tools/verify_public_release.py', '--candidate'])
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
            row = self.runner.http_json(
                f"https://pypi.org/pypi/elpisai/{intent['version']}/json"
            )
            if row is None:
                return None

            files = [
                {
                    **{
                        k: f[k]
                        for k in (
                            'filename',
                            'packagetype',
                            'upload_time_iso_8601',
                            'yanked',
                        )
                    },
                    'sha256': f['digests']['sha256'],
                }
                for f in row['urls']
            ]
            observed = {
                'project': row['info']['name'],
                'version': row['info']['version'],
                'files': sorted(
                    files,
                    key=lambda f: f['filename'],
                ),
            }

            if intent.get('schema') == machine.SIGNED_SCHEMA:
                qualification_raw = self.qualification.read_bytes()
                require(
                    hashlib.sha256(qualification_raw).hexdigest()
                    == intent['qualification_sha256'],
                    'QUALIFICATION_DIGEST_MISMATCH',
                )

                qualification_report = json.loads(
                    qualification_raw
                )
                expected_artifacts = (
                    qualified_distribution_artifacts(
                        qualification_report,
                        intent['version'],
                    )
                )
                observed_artifacts = sorted(
                    [
                        {
                            'filename': item['filename'],
                            'packagetype': item['packagetype'],
                            'sha256': item['sha256'],
                        }
                        for item in observed['files']
                    ],
                    key=lambda item: item['filename'],
                )

                require(
                    observed_artifacts == expected_artifacts,
                    'PYPI_ARTIFACT_IDENTITY_MISMATCH',
                )

            return observed
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

    def verify_origin(self, intent):
        # Import without consulting modules from the archived release.
        import importlib
        module = importlib.import_module('tools.release_origin' if __package__ else 'release_origin')
        path = os.environ.get('ELPIS_ALLOWED_SIGNERS')
        proof = module.verify_tag(self.root, intent['signed_tag_object'], intent['candidate_sha'],
                                  machine.tag_name(intent), Path(path) if path else None)
        require(proof['allowed_signers_sha256'] == intent['allowed_signers_sha256'], 'SIGNER_AUTHORITY_CHANGED')
        return proof

    def reconcile(self, state, intent, evidence):
        """Absence is not evidence of never having published.

        Collect external witnesses before a forensic stop. GitHub's present-day
        APIs cannot prove that a deleted tag/run/release never existed. No 500
        or empty query is converted into authorization to replay publication.
        """
        witnesses = {'remote_refs': self.remote_refs(intent)}
        if state == 'ANNOTATED_TAG_CREATED':
            tag = machine.tag_name(intent)
            witnesses['release'] = self.api(f"repos/{intent['repository']}/releases/tags/{tag}")
            witnesses['pypi'] = self.runner.http_json(f"https://pypi.org/pypi/elpisai/{intent['version']}/json")
            runs = []
            for page in range(1, 12):
                result = self.api(f"repos/{intent['repository']}/actions/runs?branch={tag}&per_page=100&page={page}")
                require(result is not None and result['total_count'] <= 1000, 'RECONCILIATION_CENSUS_INCOMPLETE')
                runs.extend(result['workflow_runs'])
                if len(runs) >= result['total_count']:
                    break
                require(len(result['workflow_runs']) == 100, 'RECONCILIATION_CENSUS_INCOMPLETE')
            witnesses['actions'] = runs
            if runs or witnesses['release'] or witnesses['pypi']:
                return {'outcome': 'PREVIOUS_SIDE_EFFECT', 'witnesses': witnesses}
        return {'outcome': 'ABSENT_UNPROVEN', 'witnesses': witnesses}

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
            if intent.get('schema') == machine.SIGNED_SCHEMA:
                self.verify_origin(intent)
                oid = intent['signed_tag_object']
            else:
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
                'name': machine.tag_name(intent),
                'body': machine.release_body(intent, notes),
                'draft': False, 'prerelease': False,
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
