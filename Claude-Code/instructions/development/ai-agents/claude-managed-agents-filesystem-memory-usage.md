---
name: claude-managed-agents-filesystem-memory-usage
description: Guidance on deploying and managing Claude Managed Agents with built-in
  filesystem-based persistent memory. Use when adopting memory features to enable
  agents to learn across sessions, share memory safely with scoped permissions and
  auditability, and improve task automation workflows in production environments.
type: instruction
artifact_type: instruction
domain_path: development/ai-agents
source_urls:
- https://claude.com/blog/claude-managed-agents-memory
brain_entry: Entries/2026-04-24-built-in-memory-for-claude-managed-agents-claude
---

# Claude Managed Agents Filesystem Memory Usage

## When to Use

- Deploying Claude Managed Agents that require persistent memory across sessions.
- Building task automation workflows that benefit from agents learning and improving over time.
- Sharing memory stores safely among multiple agents with controlled access.
- Auditing, versioning, and rolling back agent memories in production environments.

## Overview

Claude Managed Agents now support a public beta of a built-in filesystem-based persistent memory. This memory system:

- Stores agent memories as files on a mounted filesystem.
- Enables agents to learn from every session and share knowledge.
- Offers full developer control with exportable files and a comprehensive API.
- Supports scoped permissions, audit logs, and concurrent multi-agent access.
- Integrates naturally with bash and CLI tooling within agents.

## Deployment and Management Workflow

1. **Enable Memory:** Use the Claude Console or CLI to deploy agents with memory enabled.

2. **Memory Store Setup:** Configure memory stores as filesystem mounts with defined access scopes (e.g., org-wide read-only vs. per-user read/write).

3. **Agent Usage:** Agents read and write memories as files, preserving structured, task-relevant context.

4. **Concurrency & Access Control:** Multiple agents access the store concurrently without overwriting each other's data, enforced by scoped permissions.

5. **Audit & Traceability:** All memory changes are logged with session and agent info, visible in the Claude Console session events.

6. **Memory Management:**
   - Export memory files for backup or external analysis.
   - Roll back to previous versions as needed.
   - Redact sensitive information selectively from history.

## Guidelines

- Design memory scopes carefully to limit write access and reduce risk of unintended overwrites.
- Leverage audit logs to monitor agent learning and diagnose issues in production.
- Use memory to persist complex task context, corrections, or insights that span multiple sessions.
- Integrate memory file operations with existing CLI workflows for smooth automation.

## Use Cases

- **Netflix:** Reduces manual prompt tuning by persisting corrections and insights across sessions.
- **Rakuten:** Cuts first-pass errors by 97% with task-focused agents learning from all sessions.
- **Wisedocs:** Speeds document verification by 30% through spotting recurring issues in memory.
- **Ando:** Builds workplace messaging platform using memory instead of custom memory infrastructure.

## Resources

- Access the Claude Console or use the CLI to get started with agent memory.
- Refer to official Claude Managed Agents documentation for API details and advanced configuration.

Transform your AI agents into intelligent, stateful collaborators with filesystem memory for robust, production-grade workflows.
