"""
Interactive scaffolder for a new ``coachctl-personal`` repo.

Usage:
    coachctl-new-profile --target ~/workspace/coachctl-personal
    coachctl-new-profile --target /path --label bob --no-auth

Creates the per-athlete data root layout::

    <target>/
      profile/
        athlete.yaml
        plans/
        feedback/
      data/
      dist/
      raw/
      deploy/
        web.py  vercel.json  requirements.txt
      .env
      .env.example
      .gitignore
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
ATHLETE_TEMPLATE = ROOT / "config" / "athlete.yaml.template"

DEPLOY_WEB_PY = '''"""Vercel entry point — serves <repo>/dist/data.json via FastAPI."""

from pathlib import Path

from coachctl.dashboard import create_app

app = create_app(Path(__file__).parent.parent / "dist" / "data.json")
'''

DEPLOY_VERCEL_JSON = """{
  "version": 2,
  "builds": [{ "src": "web.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "web.py" }]
}
"""

DEPLOY_REQUIREMENTS = (
    "# Pin to a tagged release of the public package, or a git SHA.\n"
    "coachctl[dashboard] @ git+https://github.com/altiSocke/coachctl.git@main\n"
)

DEFAULT_GITIGNORE = """.env
__pycache__/
*.pyc
.venv/
"""

DEFAULT_ENV_EXAMPLE = """# Strava credentials (keep secret, never commit)
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_REFRESH_TOKEN=

# Optional Google Calendar push
# GOOGLE_CLIENT_ID=
# GOOGLE_CLIENT_SECRET=
# GOOGLE_REFRESH_TOKEN=
# GOOGLE_CALENDAR_ID=primary
"""


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{msg}{suffix}: ").strip()
    return value or default


def scaffold(target: Path, label: str | None = None) -> None:
    target.mkdir(parents=True, exist_ok=True)

    (target / "profile" / "plans").mkdir(parents=True, exist_ok=True)
    (target / "profile" / "feedback").mkdir(parents=True, exist_ok=True)
    (target / "data").mkdir(parents=True, exist_ok=True)
    (target / "dist").mkdir(parents=True, exist_ok=True)
    (target / "raw").mkdir(parents=True, exist_ok=True)
    (target / "deploy").mkdir(parents=True, exist_ok=True)

    yaml_dest = target / "profile" / "athlete.yaml"
    if not yaml_dest.exists():
        if ATHLETE_TEMPLATE.exists():
            shutil.copy(ATHLETE_TEMPLATE, yaml_dest)
        else:
            yaml_dest.write_text(
                f"# Athlete profile{f' for {label}' if label else ''}\n"
                "ftp: 200\nrftp: 360\nthreshold_hr: 170\nmax_hr: 185\n"
                "resting_hr: 50\nweight_kg: 70\nevents: []\ngoals: {}\n"
                "athlete_notes: []\n"
            )
        print(f"  created {yaml_dest}")

    env_dest = target / ".env"
    if not env_dest.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, env_dest)
        else:
            env_dest.write_text(DEFAULT_ENV_EXAMPLE)
        print(f"  created {env_dest}")

    env_ex = target / ".env.example"
    if not env_ex.exists():
        env_ex.write_text(DEFAULT_ENV_EXAMPLE)
        print(f"  created {env_ex}")

    gi = target / ".gitignore"
    if not gi.exists():
        gi.write_text(DEFAULT_GITIGNORE)
        print(f"  created {gi}")

    web = target / "deploy" / "web.py"
    if not web.exists():
        web.write_text(DEPLOY_WEB_PY)
        print(f"  created {web}")

    vj = target / "deploy" / "vercel.json"
    if not vj.exists():
        vj.write_text(DEPLOY_VERCEL_JSON)
        print(f"  created {vj}")

    req = target / "deploy" / "requirements.txt"
    if not req.exists():
        req.write_text(DEPLOY_REQUIREMENTS)
        print(f"  created {req}")


def run_auth(target: Path, label: str | None) -> None:
    """Run the Strava OAuth flow against the new data root."""
    os.environ["AGENT_DATA_ROOT"] = str(target)
    if label:
        os.environ["STRAVA_PROFILE"] = label

    import importlib

    import coachctl.paths as paths_mod
    import coachctl.sync as sync_mod

    importlib.reload(paths_mod)
    importlib.reload(sync_mod)

    print("\nMake sure STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET are set in:")
    print(f"  {target}/.env\n")
    input("Press Enter when ready (Ctrl+C to skip)...")

    try:
        token = sync_mod.do_auth_flow()
        print("\nOAuth complete. Running initial full sync...")
        sync_mod.sync(full=True, access_token=token)
    except KeyboardInterrupt:
        print("\nSkipped. Re-run later with: AGENT_DATA_ROOT=<path> sync --auth")


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new coachctl-personal repo.")
    parser.add_argument(
        "--target",
        help="Path to create the personal repo at (default: ../coachctl-personal)",
    )
    parser.add_argument("--label", help="Optional STRAVA_PROFILE label to embed in metadata")
    parser.add_argument("--no-auth", action="store_true", help="Scaffold only — skip Strava OAuth")
    args = parser.parse_args()

    target = args.target
    if not target:
        target = _prompt(
            "Target directory for the personal repo",
            str((ROOT.parent / "coachctl-personal").resolve()),
        )
    target_path = Path(target).expanduser().resolve()

    label = args.label
    if label and not re.match(r"^[A-Za-z0-9_-]+$", label):
        print("Error: label must be alphanumeric / underscore / hyphen.")
        sys.exit(1)

    print(f"\nScaffolding personal repo at {target_path}\n")
    scaffold(target_path, label=label)

    print(f"\nNext steps:")
    print(f"  1. Edit {target_path}/.env with your Strava credentials.")
    print(f"  2. Edit {target_path}/profile/athlete.yaml.")
    print(
        f"  3. (Optional) cd {target_path} && git init && git remote add origin <private-repo-url>"
    )
    print(f"  4. export AGENT_DATA_ROOT={target_path}")

    if not args.no_auth:
        run_auth(target_path, label)


if __name__ == "__main__":
    main()
