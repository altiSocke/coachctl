# openai
Format: YAML
Top-level: object
Size: 2
Nested depth: 2

## Schema

- interface: object (4 keys)
- policy: object (1 keys)

## Preview

```yaml
interface:
  display_name: "TDD Workflow"
  short_description: "Test-driven development with coverage gates"
  brand_color: "#22C55E"
  default_prompt: "Use $tdd-workflow to drive the change with tests before implementation."
policy:
  allow_implicit_invocation: true

```