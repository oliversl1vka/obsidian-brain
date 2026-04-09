Create or update a Claude Code artifact from the source below.

## Mode
{mode}

## Target Artifact
Artifact type: {artifact_type}
Name: {name}
Description: {description}
Domain path: {domain_path}
Merge reasoning: {merge_reasoning}

## Source
Title: {title}
URL: {url}
Category: {category}
Summary: {summary}

## Source Content
{scrape_content}

## Existing Artifact Content
{existing_content}

## User Profile
{user_profile}

## Task
Return ONLY valid JSON with exactly this structure:
{
  "content": "full markdown content for the main file",
  "references": [
    {
      "filename": "short-kebab-name.md",
      "content": "markdown content"
    }
  ]
}

Rules:
- `content` must already include the YAML frontmatter.
- Use zero reference files when the main artifact is already concise.
- Create reference files only for supporting detail that would make the main file too long or noisy.
- Keep filenames lowercase kebab-case ending in `.md`.
- For `skill`, the main content should be ready for `SKILL.md`.
- For `instruction`, `prompt`, and `agent`, the main content should be ready for a single `.md` file.
