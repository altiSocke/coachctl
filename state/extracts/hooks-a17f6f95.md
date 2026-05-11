# hooks
Format: JSON
Top-level: object
Size: 1
Nested depth: 6

## Schema

- hooks: object (2 keys)

## Preview

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node .codex/hooks/swarmvault-graph-first.js session-start"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "node .codex/hooks/swarmvault-graph-first.js pre-tool-use"
          }
        ]
      }
    ]
  }
}

```