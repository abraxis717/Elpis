import pytest

from tools import full_release as release


STAGE = "PUBLICATION_ASSERTION_COMMIT"


def intent(digest):
    return {
        "parent": "a" * 40,
        "path": "PUBLICATION_ASSERTIONS.json",
        "sha256": digest,
    }


def test_active_intent_rejects_changed_payload_authority(
    tmp_path,
):
    journal = release.OuterJournal(
        tmp_path / "journal.json"
    )

    original = intent("1" * 64)
    changed = intent("2" * 64)

    journal.begin(STAGE, original)

    with pytest.raises(
        release.FullReleaseError,
        match="FULL_RELEASE_JOURNAL_INTENT_CONFLICT",
    ):
        journal.begin(STAGE, changed)


def test_returned_stage_still_binds_original_intent(
    tmp_path,
):
    journal = release.OuterJournal(
        tmp_path / "journal.json"
    )

    original = intent("1" * 64)
    changed = intent("2" * 64)

    journal.begin(STAGE, original)
    journal.returned(
        STAGE,
        {"commit": "b" * 40},
    )

    # Exact restart is idempotent.
    journal.begin(STAGE, original)

    with pytest.raises(
        release.FullReleaseError,
        match="FULL_RELEASE_JOURNAL_INTENT_CONFLICT",
    ):
        journal.begin(STAGE, changed)


def test_completed_stage_still_binds_original_intent(
    tmp_path,
):
    journal = release.OuterJournal(
        tmp_path / "journal.json"
    )

    original = intent("1" * 64)
    changed = intent("2" * 64)

    journal.begin(STAGE, original)
    journal.returned(
        STAGE,
        {"commit": "b" * 40},
    )
    journal.complete(
        STAGE,
        {"commit": "b" * 40},
    )

    journal.begin(STAGE, original)

    with pytest.raises(
        release.FullReleaseError,
        match="FULL_RELEASE_JOURNAL_INTENT_CONFLICT",
    ):
        journal.begin(STAGE, changed)


def test_repeated_return_must_match_original_return(
    tmp_path,
):
    journal = release.OuterJournal(
        tmp_path / "journal.json"
    )

    journal.begin(STAGE, intent("1" * 64))
    journal.returned(
        STAGE,
        {"commit": "b" * 40},
    )

    journal.returned(
        STAGE,
        {"commit": "b" * 40},
    )

    with pytest.raises(
        release.FullReleaseError,
        match="FULL_RELEASE_JOURNAL_RETURN_CONFLICT",
    ):
        journal.returned(
            STAGE,
            {"commit": "c" * 40},
        )


def test_repeated_completion_must_match_original_completion(
    tmp_path,
):
    journal = release.OuterJournal(
        tmp_path / "journal.json"
    )

    journal.begin(STAGE, intent("1" * 64))
    journal.returned(
        STAGE,
        {"commit": "b" * 40},
    )
    journal.complete(
        STAGE,
        {"commit": "b" * 40},
    )

    journal.complete(
        STAGE,
        {"commit": "b" * 40},
    )

    with pytest.raises(
        release.FullReleaseError,
        match="FULL_RELEASE_JOURNAL_COMPLETE_CONFLICT",
    ):
        journal.complete(
            STAGE,
            {"commit": "c" * 40},
        )



def test_replay_rejects_duplicate_returned_transition(tmp_path):
    path = tmp_path / 'journal.json'
    journal = release.OuterJournal(path)
    journal.begin(STAGE, intent('1' * 64))
    journal.returned(STAGE, {'commit': 'b' * 40})

    previous = journal.data['events'][-1]['sha256']
    event = {
        'seq': len(journal.data['events']),
        'previous': previous,
        'stage': STAGE,
        'kind': 'returned',
        'data': {'commit': 'b' * 40},
    }
    event['sha256'] = release.journal_digest(event)
    journal.data['events'].append(event)
    release.atomic_json(path, journal.data)

    with pytest.raises(
        release.FullReleaseError,
        match='FULL_RELEASE_JOURNAL_STAGE_EVENT_DUPLICATE',
    ):
        release.OuterJournal(path)

@pytest.mark.parametrize(
    "later_stage",
    [
        "assertion_commit",
        "ratification_commit",
        "final_main_push",
    ],
)
@pytest.mark.parametrize(
    "later_kind",
    ["intent", "returned"],
)
def test_completed_seal_reconciliation_allows_later_pending_stage(
    tmp_path,
    later_stage,
    later_kind,
):
    journal = release.OuterJournal(
        tmp_path / "journal.json"
    )
    seal_intent = {
        "development_sha": "a" * 40,
        "manifest": "manifests/Elpis2.2.31.RELEASE_MANIFEST.json",
    }
    observed = {
        "candidate_sha": "b" * 40,
        "manifest_sha256": "c" * 64,
    }

    journal.begin("seal_commit", seal_intent)
    journal.returned("seal_commit", observed)
    journal.complete("seal_commit", observed)

    later_intent = {"value": later_stage}
    journal.begin(later_stage, later_intent)

    if later_kind == "returned":
        journal.returned(
            later_stage,
            {"result": later_stage},
        )

    release.reconcile_seal_journal(
        journal,
        intent=seal_intent,
        observed=observed,
    )

    assert journal.completed("seal_commit")
    active = journal.active()
    assert active is not None
    assert active["stage"] == later_stage
    assert active["kind"] == later_kind
