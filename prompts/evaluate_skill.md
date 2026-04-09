Evaluate whether this source should become a Claude Code artifact.

## Source
Title: {title}
URL: {url}
Category: {category}
Summary: {summary}

## Source Content
{scrape_content}

## User Profile
{user_profile}

## Relevant Existing Claude Artifacts
{existing_artifacts}

## Task
Return ONLY valid JSON with exactly these fields:
- `worth_creating`: boolean
- `reasoning`: string — concise justification for the decision
- `artifact_type`: "skill" | "instruction" | "prompt" | "agent" | "none"
- `name`: string — kebab-case or empty string when not creating
- `description`: string — what it does and when to use it, or empty string when not creating
- `domain_path`: string — slash-separated folder path or empty string when not creating
- `action`: "create" | "merge" | "skip"
- `existing_path`: string — must exactly match one of the candidate paths above when action is `merge` or `skip`, otherwise empty string
- `merge_reasoning`: string — empty when not merging

Rules:
- If the source is not durable, actionable, and reusable for Claude Code work, set `worth_creating=false`, `artifact_type="none"`, and `action="skip"`.
- Only use `existing_path` values that appear in the relevant existing artifacts list above.
- If the source overlaps an existing artifact but adds no meaningful new information, choose `skip`.
- If the source overlaps an existing artifact and adds concrete new value, choose `merge`.
- If there are no relevant existing artifacts, use `create` or `skip`.

Example:
{"worth_creating": true, "reasoning": "The repo documents a repeatable testing workflow for browser apps.", "artifact_type": "skill", "name": "browser-regression-testing", "description": "Run structured browser regression testing workflows and capture failures. Use when validating UI changes or debugging flaky browser behavior.", "domain_path": "development/testing", "action": "create", "existing_path": "", "merge_reasoning": ""}
