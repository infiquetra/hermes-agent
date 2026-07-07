"""Tests for the contributor attribution workflow wiring."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CONTRIBUTOR_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "contributor-check.yml"


def _load_workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _workflow_triggers(workflow: dict) -> dict:
    return workflow.get("on") or workflow.get(True)


def test_ci_passes_pull_request_base_ref_to_contributor_check() -> None:
    workflow = _load_workflow(CI_WORKFLOW)

    contributor_job = workflow["jobs"]["contributor-check"]

    assert contributor_job["with"]["base_ref"] == "${{ github.base_ref || 'main' }}"


def test_contributor_check_uses_base_ref_input_for_merge_base() -> None:
    workflow = _load_workflow(CONTRIBUTOR_WORKFLOW)

    triggers = _workflow_triggers(workflow)

    assert triggers["workflow_call"]["inputs"]["base_ref"]["default"] == "main"

    step_script = workflow["jobs"]["check-attribution"]["steps"][1]["run"]
    assert 'BASE_REMOTE="origin/${BASE_REF}"' in step_script
    assert 'git merge-base "${BASE_REMOTE}" HEAD' in step_script
    assert "origin/main HEAD" not in step_script
