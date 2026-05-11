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
  display_name: "Security Review"
  short_description: "Security checklist and vulnerability review"
  brand_color: "#EF4444"
  default_prompt: "Use $security-review to review sensitive code with the security checklist."
policy:
  allow_implicit_invocation: true

```