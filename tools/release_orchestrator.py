#!/usr/bin/env python3
"""Crash-safe release closeout. Default CLI operation performs no commands.

Input is an exactly identified, locally qualified committed seal. This tool
never rewrites a seal. See docs/RELEASE_ORCHESTRATOR_V1.md for the v1 contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Protocol

try:
    from tools import publication_assertions_v2 as publication
except (ModuleNotFoundError, ImportError):
    import publication_assertions_v2 as publication

SCHEMA = 'elpis.release-orchestrator.intent.v1'
SIGNED_SCHEMA = 'elpis.release-orchestrator.intent.v2'
JOURNAL_SCHEMA = 'elpis.release-orchestrator.journal.v1'
RECEIPT_SCHEMA = 'elpis.release-orchestrator.receipt.v1'
STATES = (
    'LOCAL_QUALIFIED', 'SEALED_CANDIDATE', 'MAIN_PUSHED', 'MAIN_HOSTED_GREEN',
    'ANNOTATED_TAG_LOCAL_CREATED', 'ANNOTATED_TAG_CREATED', 'TAG_HOSTED_GREEN',
    'GITHUB_RELEASE_PUBLISHED', 'RELEASE_EVENT_GREEN', 'PYPI_WORKFLOW_GREEN',
    'PYPI_EXTERNALLY_OBSERVED', 'PUBLICATION_RECEIPT_READY',
    'PUBLICATION_ASSERTION_APPENDED', 'CLOSED',
)
MUTATIONS = frozenset({
    'MAIN_PUSHED', 'ANNOTATED_TAG_LOCAL_CREATED', 'ANNOTATED_TAG_CREATED',
    'GITHUB_RELEASE_PUBLISHED', 'PUBLICATION_ASSERTION_APPENDED',
})
WORKFLOWS = {
    'ci': ('CI', 'ci.yml'),
    'reference_runtime': ('reference-runtime', 'reference-runtime.yml'),
    'component_attribution': ('Component attribution', 'component-attribution.yml'),
    'platform_matrix': ('platform-matrix', 'platform-matrix.yml'),
}
NATIVE_WORKFLOW = ('inference-native-r0', 'inference-native-r0.yml')
NATIVE_REQUIRED_FROM = (2, 2, 28)


def required_workflows(intent: dict) -> dict:
    result = dict(WORKFLOWS)
    version = tuple(map(int, intent['version'].split('.')))
    if version >= NATIVE_REQUIRED_FROM:
        result['inference_native'] = NATIVE_WORKFLOW
    return result


class ReleaseError(ValueError):
    """Conflict requiring investigation; never permission to repair authority."""


class Waiting(ReleaseError):
    """Observation pending. Exit 75; resume the same intent."""


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ReleaseError(diagnostic)


def canonical(value: Any) -> bytes:
    return publication._canonical_bytes(value)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()



DISTRIBUTION_AUTHORITY_SCHEMA = "elpis.distribution-artifacts.v1"
DISTRIBUTION_AUTHORITY_BEGIN = "<!-- ELPIS_DISTRIBUTION_ARTIFACTS_V1\n"
DISTRIBUTION_AUTHORITY_END = "\n-->"


def validate_distribution_artifacts(value, version):
    require(
        isinstance(value, list) and len(value) == 2,
        "DISTRIBUTION_ARTIFACTS_INVALID",
    )

    rows = []
    filenames = set()
    types = set()

    for item in value:
        require(
            isinstance(item, dict)
            and set(item)
            == {"filename", "packagetype", "sha256"},
            "DISTRIBUTION_ARTIFACT_FIELDS_INVALID",
        )

        filename = item["filename"]
        kind = item["packagetype"]
        digest_value = item["sha256"]

        require(
            isinstance(filename, str)
            and bool(filename),
            "DISTRIBUTION_ARTIFACT_FILENAME_INVALID",
        )
        require(
            kind in {"sdist", "bdist_wheel"},
            "DISTRIBUTION_ARTIFACT_TYPE_INVALID",
        )
        require(
            isinstance(digest_value, str)
            and bool(
                publication.SHA256_RE.fullmatch(
                    digest_value
                )
            ),
            "DISTRIBUTION_ARTIFACT_SHA256_INVALID",
        )
        require(
            filename not in filenames,
            "DISTRIBUTION_ARTIFACT_FILENAME_DUPLICATE",
        )

        filenames.add(filename)
        types.add(kind)

        prefix = "elpisai-" + version
        if kind == "sdist":
            require(
                filename == prefix + ".tar.gz",
                "DISTRIBUTION_SDIST_FILENAME_INVALID",
            )
        else:
            require(
                filename.startswith(prefix + "-")
                and filename.endswith(".whl"),
                "DISTRIBUTION_WHEEL_FILENAME_INVALID",
            )

        rows.append(
            {
                "filename": filename,
                "packagetype": kind,
                "sha256": digest_value,
            }
        )

    require(
        types == {"sdist", "bdist_wheel"},
        "DISTRIBUTION_ARTIFACT_TYPE_SET_INVALID",
    )

    return sorted(
        rows,
        key=lambda item: item["filename"],
    )


def distribution_authority(intent):
    return {
        "schema": DISTRIBUTION_AUTHORITY_SCHEMA,
        "version": intent["version"],
        "files": validate_distribution_artifacts(
            intent["distribution_artifacts"],
            intent["version"],
        ),
    }


def release_body(intent, notes):
    if intent.get("schema") != SIGNED_SCHEMA:
        return notes

    authority = canonical(
        distribution_authority(intent)
    ).decode("utf-8").strip()

    return (
        notes
        + "\n"
        + DISTRIBUTION_AUTHORITY_BEGIN
        + authority
        + DISTRIBUTION_AUTHORITY_END
        + "\n"
    )


def validate_release_body(intent, body):
    require(
        isinstance(body, str),
        "GITHUB_RELEASE_BODY_INVALID",
    )

    if intent.get("schema") != SIGNED_SCHEMA:
        require(
            hashlib.sha256(body.encode()).hexdigest()
            == intent["notes_sha256"],
            "GITHUB_RELEASE_NOTES_MISMATCH",
        )
        return

    separator = "\n" + DISTRIBUTION_AUTHORITY_BEGIN

    require(
        body.count(separator) == 1
        and body.count(DISTRIBUTION_AUTHORITY_END) == 1,
        "GITHUB_RELEASE_ARTIFACT_AUTHORITY_INVALID",
    )

    notes, remainder = body.split(separator, 1)
    raw, suffix = remainder.split(
        DISTRIBUTION_AUTHORITY_END,
        1,
    )

    require(
        suffix == "\n",
        "GITHUB_RELEASE_ARTIFACT_AUTHORITY_INVALID",
    )

    require(
        hashlib.sha256(notes.encode()).hexdigest()
        == intent["notes_sha256"],
        "GITHUB_RELEASE_NOTES_MISMATCH",
    )

    try:
        observed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReleaseError(
            "GITHUB_RELEASE_ARTIFACT_AUTHORITY_INVALID:"
            + str(exc)
        ) from exc

    require(
        observed == distribution_authority(intent),
        "GITHUB_RELEASE_ARTIFACT_AUTHORITY_MISMATCH",
    )

def validate_intent(value: dict) -> dict:
    signed = isinstance(value, dict) and value.get('schema') == SIGNED_SCHEMA
    require(isinstance(value, dict) and set(value) == {
        'schema', 'repository', 'version', 'candidate_sha', 'manifest_sha256',
        'main_before', 'tagger', 'qualification_sha256', 'notes_sha256',
    } | ({
        'signed_tag_object',
        'allowed_signers_sha256',
        'distribution_artifacts',
    } if signed else set()), 'INTENT_FIELDS_INVALID')
    require(value['schema'] in {SCHEMA, SIGNED_SCHEMA}, 'INTENT_SCHEMA_INVALID')
    require(value['repository'] == 'abraxis717/Elpis', 'REPOSITORY_MISMATCH')
    version = value['version']
    require(isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version)
            is not None, 'VERSION_INVALID')
    require(tuple(map(int, version.split('.'))) > (2, 2, 25),
            'HISTORICAL_RELEASE_IMMUTABLE:through-2.2.25')
    require(tuple(map(int, version.split('.'))) < (2, 2, 31) or signed, 'SIGNED_INTENT_REQUIRED')
    if signed:
        require(bool(publication.HEX_RE.fullmatch(value['signed_tag_object'])), 'SIGNED_TAG_OBJECT_INVALID')
        require(bool(publication.SHA256_RE.fullmatch(value['allowed_signers_sha256'])), 'SIGNERS_DIGEST_INVALID')
        value['distribution_artifacts'] = validate_distribution_artifacts(
            value['distribution_artifacts'],
            value['version'],
        )
    for field in ('candidate_sha', 'main_before'):
        require(isinstance(value[field], str) and bool(publication.HEX_RE.fullmatch(value[field])),
                f'OBJECT_ID_INVALID:{field}')
    for field in ('manifest_sha256', 'qualification_sha256', 'notes_sha256'):
        require(isinstance(value[field], str) and bool(publication.SHA256_RE.fullmatch(value[field])),
                f'SHA256_INVALID:{field}')
    require(isinstance(value['tagger'], str) and bool(re.fullmatch(
        r'[^<>\r\n]+ <[^<>\s]+> [0-9]+ [+-][0-9]{4}', value['tagger'])), 'TAGGER_INVALID')
    require(len(value['candidate_sha']) == len(value['main_before']), 'OBJECT_FORMAT_MISMATCH')
    return json.loads(canonical(value))


def tag_name(intent: dict) -> str:
    return 'Elpis' + intent['version']


def tag_bytes(intent: dict) -> bytes:
    require(intent.get('schema') != SIGNED_SCHEMA, 'SIGNED_TAG_BYTES_MUST_BE_OBSERVED')
    return (f"object {intent['candidate_sha']}\ntype commit\ntag {tag_name(intent)}\n"
            f"tagger {intent['tagger']}\n\n{tag_name(intent)}\n").encode()


def tag_identity(intent: dict) -> dict:
    if intent.get('schema') == SIGNED_SCHEMA:
        oid = intent['signed_tag_object']
    else:
        raw = tag_bytes(intent)
        algorithm = hashlib.sha1 if len(intent['candidate_sha']) == 40 else hashlib.sha256
        oid = algorithm(f'tag {len(raw)}\0'.encode() + raw).hexdigest()
    return {'tag_object': oid, 'tag_object_type': 'tag',
            'peeled_commit': intent['candidate_sha'], 'peeled_object_type': 'commit'}


def validate_tag(observed: dict, intent: dict) -> None:
    require(observed.get('tag_object_type') == 'tag', 'ANNOTATED_TAG_REQUIRED')
    require(observed.get('peeled_object_type') == 'commit', 'PEELED_OBJECT_TYPE_MISMATCH')
    require(observed.get('peeled_commit') == intent['candidate_sha'], 'TAG_PEELED_COMMIT_MISMATCH')
    require(observed == tag_identity(intent), 'TAG_OBJECT_MISMATCH')


def action_specs(state: str, intent: dict) -> dict:
    if state in {'MAIN_HOSTED_GREEN', 'TAG_HOSTED_GREEN'}:
        prefix = 'main_' if state == 'MAIN_HOSTED_GREEN' else 'tag_'
        return {prefix + key: (name, path, 'push')
                for key, (name, path) in required_workflows(intent).items()}
    if state == 'RELEASE_EVENT_GREEN':
        return {'release_event_ci': ('CI', 'ci.yml', 'release')}
    return {'pypi_publish': ('pypi-publish', 'pypi-publish.yaml', 'release')}


def timestamp(value: str) -> float:
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None, 'TIMESTAMP_TIMEZONE_REQUIRED')
        return parsed.timestamp()
    except (ValueError, TypeError, AttributeError) as exc:
        raise ReleaseError(f'TIMESTAMP_INVALID:{value}') from exc


def validate_actions(state: str, runs: dict, intent: dict) -> None:
    specs = action_specs(state, intent)
    require(set(runs) == set(specs), f'WORKFLOW_WITNESS_SET_MISMATCH:{state}')
    ids = []
    for key, (name, path, event) in specs.items():
        run = runs[key]
        require(set(run) == {'workflow', 'path', 'event', 'head_sha', 'head_branch',
                            'run_id', 'run_attempt', 'status', 'conclusion', 'created_at',
                            'updated_at', 'repository'}, f'WORKFLOW_FIELDS_INVALID:{key}')
        require(run['repository'] == intent['repository'], f'WORKFLOW_REPOSITORY_MISMATCH:{key}')
        require(run['workflow'] == name and run['path'] == '.github/workflows/' + path,
                f'WORKFLOW_IDENTITY_MISMATCH:{key}')
        require(run['event'] == event, f'WORKFLOW_EVENT_MISMATCH:{key}')
        require(run['head_sha'] == intent['candidate_sha'], f'WORKFLOW_SHA_MISMATCH:{key}')
        branch = 'main' if state == 'MAIN_HOSTED_GREEN' else tag_name(intent)
        require(run['head_branch'] == branch, f'WORKFLOW_REF_MISMATCH:{key}')
        require(type(run['run_id']) is int and run['run_id'] > 0, f'WORKFLOW_RUN_ID_INVALID:{key}')
        require(run['run_attempt'] == 1, f'WORKFLOW_RERUN_FORBIDDEN:{key}')
        require(run['status'] == 'completed', f'WORKFLOW_NOT_COMPLETE:{key}')
        require(run['conclusion'] == 'success', f"REQUIRED_WORKFLOW_FAILED:{key}:{run['conclusion']}")
        require(timestamp(run['updated_at']) >= timestamp(run['created_at']), f'WORKFLOW_TIME_ORDER:{key}')
        ids.append(run['run_id'])
    require(len(ids) == len(set(ids)), 'WORKFLOW_RUN_ID_DUPLICATE')


def external_receipt(intent: dict, evidence: dict) -> dict:
    actions = {}
    for state in ('TAG_HOSTED_GREEN', 'RELEASE_EVENT_GREEN', 'PYPI_WORKFLOW_GREEN'):
        for name, run in evidence[state].items():
            actions[name] = {key: run[key] for key in ('workflow', 'event', 'head_sha', 'run_id', 'conclusion')}
    receipt = {'release_tag': tag_name(intent), 'github_actions': actions,
               'github_release': evidence['GITHUB_RELEASE_PUBLISHED'],
               'pypi': evidence['PYPI_EXTERNALLY_OBSERVED']}
    return publication._validate_external_receipt(receipt, tag=tag_name(intent), peeled=intent['candidate_sha'])


def expected_assertion(intent: dict, evidence: dict) -> dict:
    receipt = external_receipt(intent, evidence)
    return {**receipt, **tag_identity(intent), 'version': intent['version'],
            'manifest_path': f'manifests/{tag_name(intent)}.RELEASE_MANIFEST.json',
            'manifest_sha256': intent['manifest_sha256']}


class Boundary(Protocol):
    """Absence must be distinct from transport/authentication errors.

    mutate returns on command success WITHOUT read-after-write verification.
    Exceptions have unknown outcomes. Adapters must never retry mutations.
    """
    def preflight(self, intent: dict, evidence: dict) -> None: ...
    def observe(self, state: str, intent: dict, evidence: dict) -> Any: ...
    def mutate(self, state: str, intent: dict, evidence: dict) -> Any: ...


class Journal:
    """Atomic, fsynced, hash-chained log. Caller holds repository-wide lock."""
    def __init__(self, path: Path, intent: dict):
        self.path = path
        self.intent = validate_intent(intent)
        if path.exists():
            try:
                self.data = json.loads(path.read_bytes())
            except (ValueError, OSError) as exc:
                raise ReleaseError('JOURNAL_UNREADABLE') from exc
            require(isinstance(self.data, dict) and set(self.data) == {'schema', 'intent', 'events'},
                    'JOURNAL_FIELDS_INVALID')
            require(self.data['schema'] == JOURNAL_SCHEMA, 'JOURNAL_SCHEMA_INVALID')
            require(self.data['intent'] == self.intent, 'JOURNAL_INTENT_CONFLICT')
        else:
            self.data = {'schema': JOURNAL_SCHEMA, 'intent': self.intent, 'events': []}
        self.replay()

    def replay(self) -> tuple[dict, dict | None]:
        evidence: dict = {}
        active = None
        previous = digest(self.intent)
        require(isinstance(self.data['events'], list), 'JOURNAL_EVENTS_INVALID')
        for index, event in enumerate(self.data['events']):
            require(isinstance(event, dict) and set(event) ==
                    {'seq', 'previous', 'state', 'kind', 'data', 'sha256'}, 'JOURNAL_EVENT_INVALID')
            unsigned = {key: value for key, value in event.items() if key != 'sha256'}
            require(event['seq'] == index and event['previous'] == previous and
                    event['sha256'] == digest(unsigned), 'JOURNAL_CHAIN_INVALID')
            if event['kind'] == 'failed':
                require(index == len(self.data['events']) - 1 and event['state'] == 'FAILED',
                        'JOURNAL_FAILURE_ORDER_INVALID')
                raise ReleaseError('RELEASE_PERMANENTLY_FAILED:' + event['data']['diagnostic'])
            require(len(evidence) < len(STATES) and event['state'] == STATES[len(evidence)],
                    'JOURNAL_STATE_ORDER_INVALID')
            kind = event['kind']
            if kind == 'intent':
                require(active is None and event['state'] in MUTATIONS, 'JOURNAL_INTENT_ORDER_INVALID')
                active = event
            elif kind == 'returned':
                require(active is not None and active['kind'] in {'intent', 'dispatch'}, 'JOURNAL_RETURN_ORDER_INVALID')
                active = event
            elif kind == 'dispatch':
                require(active is not None and active['kind'] == 'intent', 'JOURNAL_DISPATCH_ORDER_INVALID')
                active = event
            elif kind == 'reconciliation':
                require(active is not None and active['kind'] in {'dispatch', 'returned', 'intent'},
                        'JOURNAL_RECONCILIATION_ORDER_INVALID')
                # Observation never erases the durable possibility of a side effect.
            elif kind == 'complete':
                evidence[event['state']] = event['data']
                active = None
            else:
                raise ReleaseError('JOURNAL_EVENT_KIND_INVALID')
            previous = event['sha256']
        return evidence, active

    def write(self, state: str, kind: str, data: Any) -> None:
        events = self.data['events']
        event = {'seq': len(events), 'previous': events[-1]['sha256'] if events else digest(self.intent),
                 'state': state, 'kind': kind, 'data': data}
        event['sha256'] = digest(event)
        events.append(event)
        self.replay()
        publication._atomic_replace(self.path, canonical(self.data))


class Orchestrator:
    def __init__(self, boundary: Boundary, journal: Journal):
        self.boundary = boundary
        self.journal = journal
        self.intent = journal.intent

    def validate(self, state: str, value: Any, evidence: dict) -> None:
        i = self.intent
        if state == 'LOCAL_QUALIFIED':
            require(value == {'candidate_sha': i['candidate_sha'], 'qualification_sha256':
                              i['qualification_sha256']}, 'LOCAL_QUALIFICATION_MISMATCH')
        elif state == 'SEALED_CANDIDATE':
            require(value == {'candidate_sha': i['candidate_sha'], 'manifest_sha256':
                              i['manifest_sha256']}, 'SEALED_CANDIDATE_MISMATCH')
        elif state == 'MAIN_PUSHED':
            require(value == {'main_sha': i['candidate_sha']}, 'MAIN_SHA_MISMATCH')
        elif state in {'ANNOTATED_TAG_LOCAL_CREATED', 'ANNOTATED_TAG_CREATED'}:
            validate_tag(value, i)
        elif state in {'MAIN_HOSTED_GREEN', 'TAG_HOSTED_GREEN', 'RELEASE_EVENT_GREEN', 'PYPI_WORKFLOW_GREEN'}:
            validate_actions(state, value, i)
            old_ids = [r['run_id'] for s, rows in evidence.items() if s.endswith('_GREEN') for r in rows.values()]
            require(not set(old_ids) & {r['run_id'] for r in value.values()}, 'WORKFLOW_RUN_ID_DUPLICATE')
            if state in {'RELEASE_EVENT_GREEN', 'PYPI_WORKFLOW_GREEN'}:
                published = timestamp(evidence['GITHUB_RELEASE_PUBLISHED']['published_at'])
                require(all(timestamp(r['created_at']) >= published for r in value.values()),
                        'WORKFLOW_PREDATES_RELEASE')
        elif state == 'GITHUB_RELEASE_PUBLISHED':
            require(isinstance(value, dict) and set(value) ==
                    {'repository', 'release_id', 'tag_name', 'published_at'}, 'GITHUB_RELEASE_FIELDS_INVALID')
            require(value['repository'] == i['repository'] and value['tag_name'] == tag_name(i),
                    'GITHUB_RELEASE_MISMATCH')
            require(type(value['release_id']) is int and value['release_id'] > 0, 'GITHUB_RELEASE_ID_INVALID')
            published = timestamp(value['published_at'])
            require(all(timestamp(r['updated_at']) <= published for r in evidence['TAG_HOSTED_GREEN'].values()),
                    'RELEASE_PREDATES_TAG_QUALIFICATION')
        elif state == 'PYPI_EXTERNALLY_OBSERVED':
            receipt = external_receipt(i, dict(evidence, PYPI_EXTERNALLY_OBSERVED=value))
            require(receipt['pypi'] == value, 'PYPI_NONCANONICAL')
            if i.get('schema') == SIGNED_SCHEMA:
                observed_artifacts = sorted(
                    [
                        {
                            'filename': file['filename'],
                            'packagetype': file['packagetype'],
                            'sha256': file['sha256'],
                        }
                        for file in value['files']
                    ],
                    key=lambda item: item['filename'],
                )
                require(
                    observed_artifacts
                    == i['distribution_artifacts'],
                    'PYPI_ARTIFACT_IDENTITY_MISMATCH',
                )
            for file in value['files']:
                require(timestamp(file['upload_time_iso_8601']) >= timestamp(
                    evidence['GITHUB_RELEASE_PUBLISHED']['published_at']), 'PYPI_PREDATES_RELEASE')
                prefix = 'elpisai-' + i['version']
                expected = (file['filename'] == prefix + '.tar.gz' if file['packagetype'] == 'sdist'
                            else file['filename'].startswith(prefix + '-') and file['filename'].endswith('.whl'))
                require(expected, 'PYPI_FILENAME_VERSION_MISMATCH')
        elif state == 'PUBLICATION_RECEIPT_READY':
            receipt = external_receipt(i, evidence)
            require(value == {'schema': RECEIPT_SCHEMA, 'receipt_sha256': digest(receipt),
                              'receipt': receipt}, 'PUBLICATION_RECEIPT_IDENTITY_MISMATCH')
        elif state == 'PUBLICATION_ASSERTION_APPENDED':
            require(value == expected_assertion(i, evidence), 'PUBLICATION_ASSERTION_CONFLICT')
        elif state == 'CLOSED':
            require(value == {'assertion_sha256': digest(evidence['PUBLICATION_ASSERTION_APPENDED']),
                              'receipt_sha256': evidence['PUBLICATION_RECEIPT_READY']['receipt_sha256']},
                    'CLOSEOUT_IDENTITY_MISMATCH')

    def run(self) -> dict:
        try:
            return self._run()
        except ReleaseError as exc:
            if str(exc).startswith(('REQUIRED_WORKFLOW_FAILED:', 'WORKFLOW_RERUN_FORBIDDEN:')):
                # Failed release qualification is immutable even if a remote run
                # is later deleted or rerun. A successor needs a new intent.
                events = self.journal.data['events']
                event = {'seq': len(events), 'previous': events[-1]['sha256'],
                         'state': 'FAILED', 'kind': 'failed',
                         'data': {'diagnostic': str(exc)}}
                event['sha256'] = digest(event)
                events.append(event)
                publication._atomic_replace(self.journal.path, canonical(self.journal.data))
            raise

    def _run(self) -> dict:
        evidence, active = self.journal.replay()
        self.boundary.preflight(self.intent, evidence)
        verified: dict = {}
        for state, stored in evidence.items():
            self.validate(state, stored, verified)
            observed = self.boundary.observe(state, self.intent, verified)
            require(observed is not None, f'JOURNAL_AHEAD_OF_REALITY:{state}')
            self.validate(state, observed, verified)
            require(observed == stored, f'JOURNAL_REMOTE_CONFLICT:{state}')
            verified[state] = stored
        for state in STATES[len(evidence):]:
            self.boundary.preflight(self.intent, evidence)
            observed = self.boundary.observe(state, self.intent, evidence)
            if observed is None:
                if active is not None:
                    # Legacy journals lack a dispatch marker. Their intent is
                    # ambiguous; only new intents explicitly promise no dispatch.
                    undispatched = (active['kind'] == 'intent' and
                                    active['data'].get('dispatch_protocol') == 1)
                    if not undispatched:
                        reconcile = getattr(self.boundary, 'reconcile', None)
                        result = reconcile(state, self.intent, evidence) if reconcile else {
                            'outcome': 'ABSENT_UNPROVEN', 'witnesses': {}}
                        self.journal.write(state, 'reconciliation', result)
                        raise ReleaseError(f'AMBIGUOUS_MUTATION_OUTCOME:{state}:{active["kind"]}:' + result['outcome'])
                if state not in MUTATIONS:
                    raise Waiting(f'WAITING_FOR_OBSERVATION:{state}')
                if active is None:
                    self.journal.write(state, 'intent', {'intent_sha256': digest(self.intent), 'dispatch_protocol': 1})
                self.journal.write(state, 'dispatch', {'intent_sha256': digest(self.intent)})
                returned = self.boundary.mutate(state, self.intent, evidence)
                # FIRST operation after success: durable acknowledgment, BEFORE verification.
                self.journal.write(state, 'returned', returned)
                observed = self.boundary.observe(state, self.intent, evidence)
                require(observed is not None, f'ACKNOWLEDGED_MUTATION_NOT_OBSERVED:{state}')
                if state == 'GITHUB_RELEASE_PUBLISHED':
                    require(returned['release_id'] == observed['release_id'], 'GITHUB_RELEASE_ID_CONFLICT')
            elif active is not None and active['kind'] == 'returned' and state == 'GITHUB_RELEASE_PUBLISHED':
                require(active['data']['release_id'] == observed['release_id'], 'GITHUB_RELEASE_ID_CONFLICT')
            self.validate(state, observed, evidence)
            self.journal.write(state, 'complete', observed)
            evidence[state] = observed
            active = None
        return evidence['CLOSED']


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intent', required=True, type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--execute', action='store_true', help='enable local and remote mutations')
    parser.add_argument('--wait-seconds', type=int, default=3600, help='bounded wait for asynchronous workflows/PyPI')
    parser.add_argument('--poll-seconds', type=int, default=30)
    args = parser.parse_args(argv)
    try:
        intent = validate_intent(json.loads(args.intent.read_bytes()))
        require(args.wait_seconds >= 0 and 1 <= args.poll_seconds <= 60, 'WAIT_CONFIGURATION_INVALID')
        if not args.execute:
            print(json.dumps({'mode': 'DRY_RUN_NO_COMMANDS', 'intent': intent, 'states': STATES,
                              'tag_identity': tag_identity(intent)}, indent=2))
            return 0
        require(args.qualification is not None, 'QUALIFICATION_REPORT_REQUIRED')
        try:
            from tools.release_orchestrator_io import LiveBoundary
        except (ModuleNotFoundError, ImportError):
            from release_orchestrator_io import LiveBoundary
        boundary = LiveBoundary(args.root.resolve(), args.qualification.resolve(), execute=True)
        private = boundary.private_directory()
        with publication._exclusive_lock(private / 'orchestrator.lock'):
            deadline = time.monotonic() + args.wait_seconds
            while True:
                journal = Journal(private / (tag_name(intent) + '.journal.json'), intent)
                try:
                    result = Orchestrator(boundary, journal).run()
                    print(json.dumps(result, sort_keys=True))
                    break
                except Waiting as exc:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise
                    print(str(exc), file=sys.stderr, flush=True)
                    time.sleep(min(args.poll_seconds, remaining))
        return 0
    except Waiting as exc:
        print(str(exc), file=sys.stderr)
        return 75
    except (ReleaseError, publication.PublicationAuthorityError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
