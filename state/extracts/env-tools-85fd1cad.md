"""Environment diagnostics — surfaces data root + profile state for the coach."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .. import paths


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def check_environment() -> str:
        """
        Report the agent's environment configuration.

        Returns a JSON object with:
          - ``ok``: bool — true if the agent can operate (data root resolves).
          - ``data_root``: resolved path or null.
          - ``data_root_source``: 'env' | 'sibling' | 'legacy' | null.
          - ``profile_label``: STRAVA_PROFILE value (informational; '' if unset).
          - ``code_root``: this checkout.
          - ``warnings``: list of soft issues (missing .env, missing athlete.yaml,
            empty activities DB, missing data.json, etc.).
          - ``errors``: list of hard issues blocking operation.
          - ``next_steps``: human-readable remediation steps when not OK.

        Call this at the very start of every conversation. If ``ok`` is false,
        stop and walk the athlete through ``next_steps`` instead of continuing
        the normal startup flow.
        """
        env_data_root = os.environ.get("AGENT_DATA_ROOT", "").strip()
        profile = os.environ.get("STRAVA_PROFILE", "").strip()

        result: dict = {
            "ok": False,
            "data_root": None,
            "data_root_source": None,
            "profile_label": profile,
            "code_root": str(paths.code_root()),
            "warnings": [],
            "errors": [],
            "next_steps": [],
        }

        # 1. Resolve data root
        try:
            dr = paths.data_root()
            result["data_root"] = str(dr)

            if env_data_root:
                result["data_root_source"] = "env"
            elif (paths.code_root().parent / "coachctl-personal").exists():
                result["data_root_source"] = "sibling"
            else:
                result["data_root_source"] = "legacy"
                result["warnings"].append(
                    "Using deprecated wiki/personal/<profile> layout. "
                    "Migrate to a sibling coachctl-personal repo."
                )
        except RuntimeError as e:
            result["errors"].append(f"Data root unresolved: {e}")
            result["next_steps"] = [
                "Run: uv run new-profile --target ~/workspace/coachctl-personal",
                "Then: export AGENT_DATA_ROOT=~/workspace/coachctl-personal",
                "Restart OpenCode so the MCP server picks up the new env.",
            ]
            return json.dumps(result, indent=2)

        # 2. Required artefacts inside data root
        env_file = paths.env_file()
        if not env_file.exists():
            result["errors"].append(f"Missing secrets file: {env_file}")
            result["next_steps"].append(
                f"Create {env_file} with STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, "
                "STRAVA_REFRESH_TOKEN. Use .env.example as template."
            )
        else:
            try:
                content = env_file.read_text("utf-8")
            except OSError as e:
                result["warnings"].append(f"Cannot read .env: {e}")
                content = ""
            for var in ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"):
                if var not in content or f"{var}=\n" in content or f"{var}=your_" in content:
                    result["warnings"].append(f"{var} appears unset in {env_file.name}")

        athlete = paths.athlete_yaml()
        if not athlete.exists():
            result["errors"].append(f"Missing athlete config: {athlete}")
            result["next_steps"].append(
                f"Create {athlete} with FTP, rFTP, threshold_hr, max_hr, weight_kg, events."
            )

        db = paths.db_path()
        if not db.exists():
            result["warnings"].append(
                f"Activities DB not yet created at {db}. Run: uv run sync --auth (first time) "
                "or uv run sync (incremental)."
            )

        data_json = paths.data_json()
        if not data_json.exists():
            result["warnings"].append(
                f"Dashboard data not yet baked at {data_json}. Run: uv run bake."
            )

        # 3. Profile label is informational
        if not profile:
            result["warnings"].append("STRAVA_PROFILE unset (optional — used as a label only).")

        result["ok"] = not result["errors"]
        if result["ok"] and not result["next_steps"]:
            result["next_steps"] = []
        return json.dumps(result, indent=2)
