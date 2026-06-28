#!/usr/bin/env python3
"""Phase 261 D-01 per-file sha256 audit: repo src/wanctl/ tree vs prod /opt/wanctl/.

Builds sorted sha256 manifests for the deploy-managed code surface (D-01 set):
  - Repo side: all non-pyc files under src/wanctl/ (110 files: 109 .py + dashboard.tcss)
  - Prod side: the same tree under /opt/wanctl (scripts/ pruned; audited separately)

Emit token PHASE261_AUDIT_SRC_TREE_EQUAL (exit 0) or
         PHASE261_AUDIT_SRC_TREE_MISMATCH (exit 1).

Additionally audits the deploy.sh-installed /opt/wanctl/scripts subset and
flags any extra non-managed files.

This is a standalone proof script — it does NOT import wanctl (SAFE-22 clean).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANAGED_SCRIPTS = (
    "analyze_baseline.py",
    "validate-deployment.sh",
    "wanctl-history",
    "wanctl-operator-summary",
    "compact-metrics-dbs.sh",
)

DEFAULT_SSH_HOST = "cake-shaper"
REPO_SRC_DIR = Path("src/wanctl")
PROD_CODE_DIR = "/opt/wanctl"
PROD_SCRIPTS_DIR = "/opt/wanctl/scripts"


# ---------------------------------------------------------------------------
# Helpers (phase227-rollback.sh idiom translated to Python)
# ---------------------------------------------------------------------------


def require_command(cmd: str) -> str | None:
    """Check that *cmd* is available on PATH; exit 1 if not."""
    if shutil.which(cmd) is None:
        print(f"ERROR: required command missing: {cmd}", file=sys.stderr)
        sys.exit(1)
    return cmd


def ssh(host: str, remote_cmd: str) -> str:
    """Run *remote_cmd* via ssh on *host* and return stdout stripped."""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, remote_cmd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ssh {host} returned {result.returncode}: {result.stderr.strip()}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Manifest builders
# ---------------------------------------------------------------------------


def build_repo_manifest(src_dir: Path) -> list[str]:
    """Build sorted sha256 manifest of all non-pyc files under *src_dir*.

    Returns list of lines "hash  ./path" sorted by path (second column).
    """
    entries: list[str] = []
    for fpath in sorted(src_dir.rglob("*")):
        if fpath.is_file():
            name = fpath.name
            parts = fpath.parts
            if name.endswith(".pyc"):
                continue
            if "__pycache__" in parts:
                continue
            rel = fpath.relative_to(src_dir)
            sha = subprocess.check_output(["sha256sum", str(fpath)], text=True).split()[0]
            entries.append(f"{sha}  ./{rel}")
    # Sort by path (second column after two-space separator)
    entries.sort(key=lambda l: l.split("  ", 1)[1])
    return entries


def build_prod_manifest(host: str, prod_dir: str) -> list[str]:
    """Build sorted sha256 manifest of all non-pyc files under *prod_dir* on *host*.

    Prunes the scripts/ subdirectory (audited separately).
    Uses ``ssh sudo sha256sum`` to compute hashes on-host.

    Returns list of lines "hash  ./path" sorted by path.
    """
    # find . -path ./scripts -prune -o <filters> -print0 | xargs -0 sha256sum | sort -k2
    remote_cmd = (
        f"cd {prod_dir} && sudo find . -path ./scripts -prune -o "
        '-type f -not -name "*.pyc" -not -path "*__pycache__*" -print0 | '
        "sudo xargs -0 sha256sum | sort -k2"
    )
    raw = ssh(host, remote_cmd)
    if not raw:
        return []
    lines = [line for line in raw.splitlines() if line.strip()]
    # Lines are already sorted by sort -k2 on the remote side
    return lines


# ---------------------------------------------------------------------------
# Scripts audit
# ---------------------------------------------------------------------------


def audit_managed_scripts(host: str) -> list[dict[str, str]]:
    """Compare each deploy.sh-installed script's prod sha256 to repo source.

    Returns list of result dicts with keys: file, status, repo_sha, prod_sha.
    """
    results: list[dict[str, str]] = []
    for fname in MANAGED_SCRIPTS:
        # Determine repo path
        if fname == "analyze_baseline.py":
            repo_path = Path("scripts/analyze_baseline.py")
        else:
            repo_path = Path("scripts", fname)

        if not repo_path.exists():
            results.append(
                {
                    "file": fname,
                    "status": "MISSING_REPO",
                    "repo_sha": "N/A",
                    "prod_sha": "N/A",
                }
            )
            continue

        repo_sha = subprocess.check_output(["sha256sum", str(repo_path)], text=True).split()[0]

        try:
            prod_sha = ssh(
                host,
                f"sudo sha256sum {PROD_SCRIPTS_DIR}/{fname}",
            ).split()[0]
        except RuntimeError:
            results.append(
                {
                    "file": fname,
                    "status": "MISSING_PROD",
                    "repo_sha": repo_sha,
                    "prod_sha": "N/A",
                }
            )
            continue

        status = "OK" if repo_sha == prod_sha else "MISMATCH"
        results.append(
            {
                "file": fname,
                "status": status,
                "repo_sha": repo_sha,
                "prod_sha": prod_sha,
            }
        )
    return results


def find_extra_scripts(host: str) -> list[str]:
    """Find files under /opt/wanctl/scripts NOT in the managed set.

    Returns list of filenames flagged for disposition.
    """
    remote_cmd = (
        f"cd {PROD_SCRIPTS_DIR} && sudo find . -type f "
        '-not -path "*__pycache__*" -not -name "*.pyc" | sort'
    )
    raw = ssh(host, remote_cmd)
    all_files = set()
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("./"):
            all_files.add(line[2:])
        elif line:
            all_files.add(line)

    managed_set = set(MANAGED_SCRIPTS)
    extras = sorted(all_files - managed_set)
    return extras


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ssh-host",
        default=DEFAULT_SSH_HOST,
        help="Target host (default: %(default)s)",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to write raw manifest files into",
    )
    parser.add_argument(
        "--repo-src-dir",
        type=Path,
        default=REPO_SRC_DIR,
        help="Repo source tree root (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    # Guard required commands
    for cmd in ("sha256sum", "ssh", "sort"):
        require_command(cmd)

    # Validate repo source dir
    if not args.repo_src_dir.is_dir():
        print(
            f"ERROR: repo source dir does not exist: {args.repo_src_dir}",
            file=sys.stderr,
        )
        return 1

    # Ensure evidence dir exists
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    # -- Build manifests --
    print("Building repo manifest...")
    repo_manifest = build_repo_manifest(args.repo_src_dir)
    print(f"  repo: {len(repo_manifest)} files")

    print("Building prod manifest...")
    try:
        prod_manifest = build_prod_manifest(args.ssh_host, PROD_CODE_DIR)
    except RuntimeError as exc:
        print(f"ERROR: failed to build prod manifest: {exc}", file=sys.stderr)
        return 1
    print(f"  prod: {len(prod_manifest)} files")

    # -- Write raw manifests to evidence --
    repo_path = args.evidence_dir / "phase261-sha256-manifest-repo.txt"
    prod_path = args.evidence_dir / "phase261-sha256-manifest-prod.txt"
    repo_path.write_text("\n".join(repo_manifest) + "\n", encoding="utf-8")
    prod_path.write_text("\n".join(prod_manifest) + "\n", encoding="utf-8")
    print(f"Evidence manifests: {repo_path}, {prod_path}")

    # -- Diff manifests --
    tree_match = repo_manifest == prod_manifest

    if tree_match:
        verdict = "PHASE261_AUDIT_SRC_TREE_EQUAL"
    else:
        verdict = "PHASE261_AUDIT_SRC_TREE_MISMATCH"
        # Show which files differ
        repo_by_path = {l.split("  ", 1)[1]: l.split("  ", 1)[0] for l in repo_manifest}
        prod_by_path = {l.split("  ", 1)[1]: l.split("  ", 1)[0] for l in prod_manifest}
        all_paths = sorted(set(repo_by_path.keys()) | set(prod_by_path.keys()))
        for p in all_paths:
            r_sha = repo_by_path.get(p, "<missing>")
            p_sha = prod_by_path.get(p, "<missing>")
            if r_sha != p_sha:
                print(f"  DIFF {p} repo={r_sha} prod={p_sha}")

    # -- Audit managed scripts under /opt/wanctl/scripts --
    print("Auditing managed scripts...")
    try:
        script_results = audit_managed_scripts(args.ssh_host)
        for sr in script_results:
            print(f"  scripts/{sr['file']}: {sr['status']}")
    except RuntimeError as exc:
        print(f"WARNING: script audit failed: {exc}", file=sys.stderr)
        script_results = []

    # -- Enumerate extra non-managed scripts --
    print("Checking for extra scripts...")
    try:
        extras = find_extra_scripts(args.ssh_host)
        for ef in extras:
            print(f"  flagged-for-disposition: scripts/{ef}")
    except RuntimeError as exc:
        print(f"WARNING: extra script check failed: {exc}", file=sys.stderr)

    # -- Emit verdict --
    print(verdict)
    return 0 if tree_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
