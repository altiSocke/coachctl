"""
``update`` — one command to sync, bake, and publish.

Workflow:
  1. ``sync`` — pull new Strava activities into ``activities.db``.
  2. ``bake`` — compute dashboard data → ``<DATA_ROOT>/deploy/dist/data.json``.
  3. ``git add/commit/push`` inside the personal data repo (triggers Vercel).

The public code repo is never touched.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from . import paths


def _run(args: list[str], cwd: Path | None = None) -> int:
    return subprocess.run(args, cwd=cwd).returncode


def _has_staged_changes(cwd: Path) -> bool:
    return subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=cwd).returncode != 0


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(paths.env_file())

    # 1. Sync
    print("── sync ──────────────────────────────────────────")
    from .sync import main as sync_main

    sync_main()

    # 2. Bake
    print("\n── bake ──────────────────────────────────────────")
    from .site import bake

    out = bake()
    print(f"Baked: {out}")

    # 3. Push personal data repo
    print("\n── push personal repo ────────────────────────────")
    repo = paths.data_root()
    if not (repo / ".git").exists():
        print(f"{repo} is not a git repo — skipping push.")
        return

    commit_msg = f"bake {date.today().isoformat()}"
    rel = out.relative_to(repo)

    rc = _run(["git", "add", str(rel), "data/activities.db"], cwd=repo)
    if rc != 0:
        print("git add failed", file=sys.stderr)
        sys.exit(rc)

    if not _has_staged_changes(repo):
        print("No changes — nothing to commit.")
        return

    if (rc := _run(["git", "commit", "-m", commit_msg], cwd=repo)) != 0:
        print("git commit failed", file=sys.stderr)
        sys.exit(rc)
    if (rc := _run(["git", "push"], cwd=repo)) != 0:
        print("git push failed", file=sys.stderr)
        sys.exit(rc)

    print("\nDone — Vercel will redeploy from the personal repo.")


if __name__ == "__main__":
    main()
