from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "deploy-dry-run-gate.sh"
GITHUB_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-dry-run.yml"
GITEA_WORKFLOW = ROOT / ".gitea" / "workflows" / "deploy-dry-run.yml"


def _run_gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GATE), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )


def test_deploy_dry_run_gate_renders_deploy_and_rollback_without_mutation() -> None:
    result = _run_gate(
        "--wan",
        "spectrum",
        "--target-host",
        "cake-shaper",
        "--deploy-mode",
        "spectrum-cake-autorate",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "DRY RUN - no changes will be made" in output
    assert "rsync src/wanctl/ to cake-shaper:/opt/wanctl/" in output
    assert "Rollback sequence:" in output
    assert "Return-to-cake sequence" in output
    assert "mutation only with --confirm" in output
    assert "OK: manual deploy dry-run gate" in output


def test_deploy_dry_run_gate_rejects_mismatched_cake_autorate_mode() -> None:
    result = _run_gate(
        "--wan",
        "att",
        "--target-host",
        "cake-shaper",
        "--deploy-mode",
        "spectrum-cake-autorate",
    )

    assert result.returncode == 2
    assert "requires --wan spectrum" in result.stderr


def _load_workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def test_manual_deploy_dry_run_workflows_are_mirrored_and_manual_only() -> None:
    github_text = GITHUB_WORKFLOW.read_text()
    gitea_text = GITEA_WORKFLOW.read_text()
    assert github_text == gitea_text

    workflow = _load_workflow(GITHUB_WORKFLOW)
    assert workflow["on"] == {
        "workflow_dispatch": {
            "inputs": {
                "wan": {
                    "description": "WAN to render",
                    "required": True,
                    "default": "spectrum",
                    "type": "choice",
                    "options": ["spectrum", "att"],
                },
                "target_host": {
                    "description": "Target host rendered into the dry-run plan only",
                    "required": True,
                    "default": "cake-shaper",
                    "type": "string",
                },
                "deploy_mode": {
                    "description": "Deployment shape to render",
                    "required": True,
                    "default": "spectrum-cake-autorate",
                    "type": "choice",
                    "options": [
                        "base",
                        "steering",
                        "spectrum-cake-autorate",
                        "att-cake-autorate",
                    ],
                },
            }
        }
    }
    assert "push" not in workflow["on"]
    assert "pull_request" not in workflow["on"]

    steps = workflow["jobs"]["dry-run"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps if "run" in step)
    assert "make ci" in commands
    assert "scripts/deploy-dry-run-gate.sh" in commands
    assert "--deploy-mode" in commands
    assert "--dry-run" not in commands  # centralized in the gate script, not user input


def test_deploy_dry_run_gate_script_is_fail_closed() -> None:
    text = GATE.read_text()
    assert "bash scripts/deploy.sh" in text
    assert "--dry-run" in text
    assert "bash \"$ROLLBACK_SCRIPT\"" in text
    assert "grep -q \"DRY RUN - no changes will be made\"" in text
    assert "grep -q \"mutation only with --confirm\"" in text
    rollback_invocation = next(
        line for line in text.splitlines() if "bash \"$ROLLBACK_SCRIPT\"" in line
    )
    assert "--dry-run" in rollback_invocation
    assert "--confirm" not in rollback_invocation
