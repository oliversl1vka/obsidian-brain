---
name: altk-evolve-on-the-job-learning-for-ai-agent
description: Implement the ALTK-Evolve continuous learning system to extract, consolidate,
  and inject reusable guidelines from agent interaction traces, improving agent generalization
  and reliability on complex, multi-step tasks. Use when building AI agents that need
  to learn principles from experience and adapt over time without prompt context bloat.
artifact_type: skill
domain_path: ai/agentic-pipeline
source_urls:
- https://huggingface.co/blog/ibm-research/altk-evolve
brain_entry: Entries/2026-04-09-altkevolve-onthejob-learning-for-ai-agents
---

# ALTK-Evolve On-the-Job Learning Skill for AI Agents

Implement a continuous learning subsystem that extracts, consolidates, and injects reusable principled guidelines from agent interaction traces. This system enables agents to improve and generalize over time, especially on complex, multi-step tasks, without bloating prompt context.

## When to Use

- Building AI agents that require long-term memory beyond re-reading past transcripts.
- Handling complex, multi-step tasks where consistent and adaptive behavior is critical.
- Wanting to capture principles and strategies from past experience, not just episodic logs.
- Using LLM-powered agents that need automatic knowledge refinement and injection.

## Overview

ALTK-Evolve implements a bidirectional memory pipeline:

1. **Downward flow (Extraction):** Capture full agent interaction trajectories (user inputs, reasoning steps, tool calls/results) in an observability layer (e.g., Langfuse, OpenTelemetry-compatible). Extract structural patterns as candidate guidelines or policies.

2. **Upward flow (Consolidation & Scoring):** Run background jobs to merge duplicates, prune poor quality rules, and prioritize effective strategies. This creates a high-quality evolving library of reusable entities.

3. **Retrieval & Injection:** At runtime, retrieve only relevant distilled guidelines via the interaction layer and inject them into the agent’s prompt or memory just-in-time, avoiding prompt size bloat.

## Workflow

1. **Enable trace capture:** Instrument your agent to log structured interaction trajectories capturing all relevant context and results.
2. **Extract candidate guidelines:** Use pluggable extractors to parse logs and generate candidate principles, policies, or standard operating procedures.
3. **Consolidate guidelines:** Periodically merge similar rules, prune ineffective ones, and promote high-quality strategies based on success scores.
4. **Inject guidance:** At task start or during execution, retrieve relevant prioritized guidelines and provide them as supplemental context.
5. **Iterate:** Continue logging new runs, extracting and consolidating new guidance to improve agent performance over time.

## Integration Options

- **No-code:** Use the ALTK-Evolve Claude Code plugin (`evolve-lite`) for immediate integration. Automatically extracts and retrieves guidelines stored as files without rebuilding your stack.
- **Low-code:** Enable tracing and sync traces with Arize Phoenix UI or compatible tools. Compatible with popular LLM clients and agent frameworks.
- **Pro-code:** Integrate tightly with MCP-based architectures like CUGA for minimal overhead bidirectional guideline exchange.

## Key Benefits

- **Principle learning, not memorization:** Agents learn strategies that generalize to unseen tasks.
- **Improved reliability:** Significant gains on hard, multi-step tasks via consistent application of learned guidelines.
- **Context control:** Just-in-time injection avoids prompt bloat and reduces flaky behavior.
- **Progressive evolution:** Continuous refinement of knowledge ensures up-to-date guidance.

## Guidelines for Use

- Ensure your agent’s interaction logs are detailed and structured to enable meaningful extraction.
- Configure consolidation frequency to balance freshness and noise control.
- Align guideline retrieval filters with task context to maximize relevance.
- Monitor scenario goal completion and consistency to verify impact.

## References

- Code repo: https://github.com/AgentToolkit/altk-evolve
- Docs & tutorials: https://agenttoolkit.github.io/altk-evolve
- Research paper: https://arxiv.org/abs/2603.10600

---

## Example

Integrate evolve-lite plugin in Claude Code:

```bash
claude plugin marketplace add AgentToolkit/altk-evolve
claude plugin install evolve-lite@evolve-marketplace
```

This deploys an automated pipeline capturing trajectories and injecting guidelines without code changes.

For custom integrations, instrument trace logging and sync with consolidation jobs to continuously evolve your agent’s knowledge base.

Use evaluation metrics like Scenario Goal Completion (SGC) to monitor improvements, expecting gains up to ~14% on hard tasks.


---
