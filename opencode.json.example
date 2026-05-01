{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "coachctl": {
      "type": "local",
      "command": ["uv", "run", "coachctl", "serve"],
      "environment": {
        "AGENT_DATA_ROOT": "{env:AGENT_DATA_ROOT}",
        "STRAVA_PROFILE": "{env:STRAVA_PROFILE}"
      },
      "enabled": true
    },
    "garmin": {
      "type": "local",
      "command": ["<path-to-garmin-mcp>/.venv/bin/garmin-mcp"],
      "enabled": false
    },
    "coros": {
      "type": "local",
      "command": ["<path-to-coros-mcp>/.venv/bin/coros-mcp", "serve"],
      "enabled": false
    }
  }
}
