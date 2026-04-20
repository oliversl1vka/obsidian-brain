---
name: building-ai-applications-with-claude-agent-harness-patterns
description: Guidance on building AI applications with Claude using agent harness
  patterns for tool orchestration, context management, and memory persistence. Use
  when designing or improving AI autonomous agent workflows to optimize performance,
  cost, and scalability.
type: instruction
artifact_type: instruction
domain_path: development/ai-agents
source_urls:
- https://claude.com/blog/harnessing-claudes-intelligence
brain_entry: Entries/2026-04-20-harnessing-claudes-intelligence-3-key-patterns-for-building-
---

# Building AI Applications with Claude: Agent Harness Patterns

Use this guidance to design or improve AI autonomous agent workflows with Claude. Focus on maximizing Claude's evolving intelligence while balancing latency, cost, and scalability using these core agent harness patterns.

---

## When to Use

- Designing intelligent AI apps with Claude, especially multi-step or long-horizon workflows
- Creating scalable, cost-effective autonomous agents or CLI LLM agents
- Managing complex tool orchestration and context management
- Building systems that require persistent memory and adaptive context handling

---

## Core Patterns

### 1. Let Claude Orchestrate Its Own Actions

- Use a general-purpose code execution tool (e.g., bash, REPL) as part of the agent harness.
- Allow Claude to generate code that calls tools and handles logic **internally**, reducing redundant context token consumption.
- Only output from code execution is passed back to Claude's context window.
- Moves orchestration control from the harness into Claude, enabling more efficient tool chaining and filtering.

### 2. Let Claude Manage Its Own Context

- Avoid hard-coding extensive system or task-specific prompts that consume tokens unnecessarily.
- Use declarative skills with concise YAML frontmatter to provide overviews.
- Let Claude fetch detailed instructions or skill content on demand via tool calls (e.g., reading files).
- Employ context editing to prune stale or irrelevant information (e.g., old tool results).
- Use subagents (forked contexts) to isolate specific tasks when needed.

### 3. Let Claude Persist Its Own Context

- Use memory folders to store context externally, and let Claude decide what to write or read.
- Implement compaction techniques where Claude summarizes past context to maintain task continuity without exceeding token limits.
- Avoid reliance on external retrieval infrastructure; empower Claude to select what to remember.

---

## Agent Harness Design Principles

### Design Context to Maximize Cache Hits

- The Messages API is stateless — package complete context each turn.
- Cache tokens between turns by breaking prompts into reusable chunks.
- Cached tokens cost significantly less — optimize prompt design accordingly.

### Use Declarative, Typed Tools for Boundaries

- Promote key actions to dedicated typed tools rather than generic bash commands.
- Typed tools enable harness interception for:
  - UX control (e.g., modals, user inputs)
  - Security gating (e.g., user confirmation before external API calls)
  - Observability (structured logging, tracing, replay)
- Continuously reevaluate which actions deserve dedicated tools versus being inside the general bash tool.
- Use security review layers (e.g., a second Claude judging commands) judiciously.

### Continuously Prune Harness Assumptions

- Claude's capabilities improve rapidly; older safeguards may become redundant and bottlenecks.
- Reassess assumptions regularly to simplify harnesses and improve performance.

---

## Summary

- Build on Claude's known strengths with general-purpose, well-understood tools.
- Shift orchestration, context, and memory management responsibilities into Claude itself where possible.
- Use the agent harness to enforce security, UX, caching, and observability boundaries via declarative tools.
- Continuously monitor capabilities and adapt the harness to avoid unnecessary complexity.

---

## Additional Resources

- Explore the claude-api skill for examples of these patterns in action.

---

*Written by Lance Martin on the Claude Platform team. Inspired by the Anthropic blog: [Harnessing Claude's Intelligence | 3 Key Patterns for Building Apps](https://claude.com/blog/harnessing-claudes-intelligence)*
