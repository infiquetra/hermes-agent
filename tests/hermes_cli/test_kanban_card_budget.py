"""Behavior contracts for native card-count/v1 enforcement."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "kanban.db"
    kb._INITIALIZED_PATHS.clear()
    connection = kb.connect(path)
    try:
        yield connection
    finally:
        connection.close()
        kb._INITIALIZED_PATHS.clear()


def _activation(**overrides):
    values = {
        "run_id": "run-1",
        "classifier_version": "size-classifier/v1",
        "classifier_evidence_digest": "sha256:evidence",
        "proposed_class": "tiny",
        "initial_class": "tiny",
        "classification_reason": "bounded fixture",
        "classification_authority_ref": "github://issue/89#accepted",
    }
    values.update(overrides)
    return values


def _create(conn, index: int, *, run_id: str = "run-1") -> str:
    return kb.create_task(
        conn,
        title=f"card {index}",
        assignee="worker",
        idempotency_key=f"{run_id}:card:{index}",
        budget_run_id=run_id,
    )


def test_activation_creates_one_terminal_root_and_is_idempotent(conn):
    first = kb.activate_card_budget(conn, **_activation())
    second = kb.activate_card_budget(conn, **_activation())

    assert second == first
    assert first["card_count_policy_version"] == "card-count/v1"
    assert first["state"] == "active"
    assert first["topology_count"] == 1
    assert first["consumed_card_count"] == 1
    root = kb.get_task(conn, first["root_task_id"])
    assert root is not None
    assert root.status == "done"
    assert root.budget_run_id == "run-1"


def test_conflicting_activation_replay_does_not_rewrite_history(conn):
    kb.activate_card_budget(conn, **_activation())

    with pytest.raises(ValueError, match="conflicting activation replay"):
        kb.activate_card_budget(
            conn,
            **_activation(classification_reason="different"),
        )

    status = kb.get_card_budget_status(conn, "run-1")
    assert status["classification_reason"] == "bounded fixture"


@pytest.mark.parametrize(
    ("size_class", "plan_budget", "soft", "hard"),
    [
        ("tiny", None, 6, 10),
        ("small", None, 10, 16),
        ("medium", None, 18, 28),
        ("large", 23, 23, 30),
    ],
)
def test_exact_class_limits(
    conn,
    size_class,
    plan_budget,
    soft,
    hard,
):
    status = kb.activate_card_budget(
        conn,
        **_activation(
            proposed_class=size_class,
            initial_class=size_class,
            plan_card_budget=plan_budget,
        ),
    )
    assert status["soft_card_limit"] == soft
    assert status["hard_card_limit"] == hard


def test_create_allows_hard_equality_then_wedges_hard_plus_one(conn):
    kb.activate_card_budget(conn, **_activation())
    task_ids = [_create(conn, index) for index in range(1, 10)]

    at_hard = kb.get_card_budget_status(conn, "run-1")
    assert at_hard["topology_count"] == 10
    assert at_hard["consumed_card_count"] == 10
    assert at_hard["soft_overrun_required"] is True

    with pytest.raises(kb.BudgetAdmissionDenied) as denied:
        _create(conn, 10)

    assert denied.value.projection["state"] == "wedged"
    wedged = kb.get_card_budget_status(conn, "run-1")
    assert wedged["topology_count"] == 10
    assert wedged["consumed_card_count"] == 10
    assert wedged["state"] == "wedged"
    assert "exceeds hard limit 10" in wedged["hard_stop_reason"]
    assert kb.get_task(conn, denied.value.trigger["id"]) is None
    assert len(task_ids) == 9
    assert [event["kind"] for event in wedged["events"]].count(
        "hard_stop"
    ) == 1


def test_budgeted_idempotent_replay_never_adds_topology(conn):
    kb.activate_card_budget(conn, **_activation())
    first = _create(conn, 1)
    replay = _create(conn, 1)

    assert replay == first
    assert kb.get_card_budget_status(conn, "run-1")["topology_count"] == 2


def test_archive_and_delete_never_refund_budget_units(conn):
    kb.activate_card_budget(conn, **_activation())
    task_id = _create(conn, 1)
    assert kb.archive_task(conn, task_id)
    assert kb.delete_archived_task(conn, task_id) is False
    assert kb.delete_task(conn, task_id) is False

    status = kb.get_card_budget_status(conn, "run-1")
    assert status["topology_count"] == 2
    assert status["consumed_card_count"] == 2
    assert kb.get_task(conn, task_id).status == "archived"


def test_idempotency_key_cannot_cross_budget_runs(conn):
    kb.activate_card_budget(conn, **_activation())
    kb.activate_card_budget(conn, **_activation(run_id="run-2"))
    kb.create_task(
        conn,
        title="first",
        assignee="worker",
        idempotency_key="shared-key",
        budget_run_id="run-1",
    )

    with pytest.raises(ValueError, match="already bound outside"):
        kb.create_task(
            conn,
            title="second",
            assignee="worker",
            idempotency_key="shared-key",
            budget_run_id="run-2",
        )


def test_first_claim_is_paid_by_topology_and_redispatch_adds_retry(conn):
    kb.activate_card_budget(conn, **_activation())
    task_id = _create(conn, 1)

    assert kb.claim_task(conn, task_id, claimer="test:1") is not None
    first = kb.get_card_budget_status(conn, "run-1")
    assert first["distinct_executed_card_count"] == 1
    assert first["execution_attempt_count"] == 1
    assert first["retry_dispatch_count"] == 0
    assert first["consumed_card_count"] == 2

    assert kb.block_task(conn, task_id, reason="retry", kind="transient")
    assert kb.unblock_task(conn, task_id)
    assert kb.claim_task(conn, task_id, claimer="test:2") is not None
    second = kb.get_card_budget_status(conn, "run-1")
    assert second["distinct_executed_card_count"] == 1
    assert second["execution_attempt_count"] == 2
    assert second["retry_dispatch_count"] == 1
    assert second["consumed_card_count"] == 3


def test_bound_task_fails_closed_when_run_is_malformed(conn):
    kb.activate_card_budget(conn, **_activation())
    task_id = _create(conn, 1)
    conn.execute(
        "UPDATE card_budget_runs SET card_count_policy_version = 'future/v9' "
        "WHERE id = 'run-1'"
    )

    assert kb.claim_task(conn, task_id, claimer="test:1") is None
    task = kb.get_task(conn, task_id)
    assert task is not None
    assert task.status == "ready"
    status = kb.get_card_budget_status(conn, "run-1")
    assert status["state"] == "wedged"
    assert "unsupported card-count policy" in status["hard_stop_reason"]


def test_successor_links_only_after_wedged_predecessor(conn):
    kb.activate_card_budget(conn, **_activation())
    for index in range(1, 10):
        _create(conn, index)
    with pytest.raises(kb.BudgetAdmissionDenied):
        _create(conn, 10)

    successor = kb.activate_card_budget(
        conn,
        **_activation(
            run_id="run-2",
            predecessor_run_id="run-1",
            successor_authority_ref="github://issue/89#successor-approved",
        ),
    )
    predecessor = kb.get_card_budget_status(conn, "run-1")
    assert successor["predecessor_run_id"] == "run-1"
    assert predecessor["state"] == "superseded"
    assert predecessor["successor_run_id"] == "run-2"
    assert predecessor["successor_authority_ref"] == (
        "github://issue/89#successor-approved"
    )
    assert predecessor["consumed_card_count"] == 10


def test_status_survives_connection_restart(tmp_path):
    path = tmp_path / "restart.db"
    kb._INITIALIZED_PATHS.clear()
    first = kb.connect(path)
    kb.activate_card_budget(first, **_activation())
    _create(first, 1)
    task_id = _create(first, 2)
    kb.claim_task(first, task_id, claimer="test:restart")
    before = kb.get_card_budget_status(first, "run-1")
    first.close()

    kb._INITIALIZED_PATHS.clear()
    reopened = kb.connect(path)
    try:
        after = kb.get_card_budget_status(reopened, "run-1")
        assert after["topology_count"] == before["topology_count"]
        assert after["execution_attempt_count"] == before[
            "execution_attempt_count"
        ]
        assert after["consumed_card_count"] == before["consumed_card_count"]
    finally:
        reopened.close()
        kb._INITIALIZED_PATHS.clear()


def test_two_connections_cannot_cross_hard_boundary(tmp_path):
    path = tmp_path / "concurrent.db"
    kb._INITIALIZED_PATHS.clear()
    seed = kb.connect(path)
    try:
        kb.activate_card_budget(seed, **_activation())
        for index in range(1, 9):
            _create(seed, index)
    finally:
        seed.close()

    def admit(index: int) -> str:
        connection = kb.connect(path)
        try:
            try:
                _create(connection, index)
            except kb.BudgetAdmissionDenied:
                return "denied"
            return "admitted"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(admit, (9, 10)))

    verify = kb.connect(path)
    try:
        status = kb.get_card_budget_status(verify, "run-1")
        assert sorted(results) == ["admitted", "denied"]
        assert status["topology_count"] == 10
        assert status["consumed_card_count"] == 10
        assert status["state"] == "wedged"
        assert [event["kind"] for event in status["events"]].count(
            "hard_stop"
        ) == 1
    finally:
        verify.close()
        kb._INITIALIZED_PATHS.clear()


def test_legacy_unbudgeted_task_stays_backward_compatible(conn):
    task_id = kb.create_task(conn, title="ordinary", assignee="worker")
    task = kb.get_task(conn, task_id)
    assert task is not None
    assert task.budget_run_id is None
    assert kb.claim_task(conn, task_id, claimer="test:legacy") is not None


def test_legacy_schema_migrates_additive_budget_column(tmp_path):
    path = tmp_path / "legacy.db"
    raw = sqlite3.connect(path)
    raw.execute(
        "CREATE TABLE tasks ("
        "id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT, assignee TEXT, "
        "status TEXT NOT NULL, priority INTEGER, created_by TEXT, "
        "created_at INTEGER NOT NULL, started_at INTEGER, completed_at INTEGER, "
        "workspace_kind TEXT NOT NULL, workspace_path TEXT, claim_lock TEXT, "
        "claim_expires INTEGER)"
    )
    raw.commit()
    raw.close()

    kb._INITIALIZED_PATHS.clear()
    migrated = kb.connect(path)
    try:
        columns = {
            row["name"] for row in migrated.execute("PRAGMA table_info(tasks)")
        }
        assert "budget_run_id" in columns
        assert migrated.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'card_budget_runs'"
        ).fetchone()
    finally:
        migrated.close()
        kb._INITIALIZED_PATHS.clear()
