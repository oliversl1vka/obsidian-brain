---
name: copilot-cli-rubber-duck-review-instruction
description: Guidance on using GitHub Copilot CLI's Rubber Duck feature that pairs
  complementary AI models for second-opinion critique of code plans, implementations,
  and tests to reduce compounding errors and improve code quality, especially for
  complex and multi-file tasks. Use this instruction when adopting Copilot CLI for
  high-assurance coding workflows requiring automated peer review.
type: instruction
artifact_type: instruction
domain_path: development/cli-ai-agents
source_urls:
- https://github.blog/ai-and-ml/github-copilot/github-copilot-cli-combines-model-families-for-a-second-opinion/
brain_entry: Entries/2026-04-13-github-copilot-cli-combines-model-families-for-a-second-opin
---

# Copilot CLI Rubber Duck Review Instruction

## Purpose
Leverage GitHub Copilot CLI's experimental Rubber Duck feature to get independent cross-model critiques on code plans, implementations, and tests. This reduces blind spots and compounding errors commonly found in single-model coding agents, improving code quality and reliability for complex or multi-file development tasks.

## When to Use
- Working on complex refactors or architectural changes spanning multiple files
- Performing high-stakes coding where bugs or architectural issues have costly impact
- Seeking a second opinion on code plans before implementation
- Validating completeness and correctness of test coverage before running tests
- Breaking through agent stalls or loops during generation

## Workflow
1. **Enable Rubber Duck**
   - Install GitHub Copilot CLI and run the `/experimental` command to activate experimental features.
   - Select any Claude model from the model picker to enable Rubber Duck powered by GPT-5.4 as the reviewer.

2. **Invoke Rubber Duck Review**
   - Automatic invocation at key checkpoints:
     - After drafting a plan: catches design or architectural flaws early.
     - After complex implementations: surfaces edge cases and overlooked details.
     - After writing tests, before execution: detects gaps and flawed test assertions.
   - On-demand invocation:
     - At any moment, request Copilot to critique its current work to get Rubber Duck feedback.
     - Useful when the agent appears stuck or uncertain.

3. **Review Feedback**
   - Examine the focused critique listing missed details, assumptions to question, or bugs.
   - Consider Rubber Duck’s suggestions and revise the code or plan accordingly.
   - Rubber Duck feedback includes cross-file conflicts and subtle bugs often missed by a single-model agent.

4. **Iterate**
   - Use Rubber Duck iteratively at each hard checkpoint until issues are minimized.
   - Incorporate Rubber Duck’s insights into the coding and testing cycle to improve final quality.

## Guidelines
- Use Rubber Duck particularly for tasks with 3+ files or requiring 70+ steps for best impact.
- Prefer using Claude models as orchestrators with GPT-5.4 as Rubber Duck reviewer for optimal results.
- Trust Rubber Duck to run sparingly and strategically without interrupting flow.
- Combine Rubber Duck critique with own code review practices for maximum assurance.
- Report issues or feedback to GitHub Copilot CLI discussion channels to support feature improvement.

## Benefits
- Closes approximately 75% of the performance gap between baseline and top-tier models on complex tasks.
- Detects serious issues such as infinite loops in schedulers, silent overwrite bugs, and cross-file state conflicts.
- Offers a fresh perspective unbound by the original model’s training data biases.
- Enhances confidence in automated coding agents handling production or critical code.

## Summary
GitHub Copilot CLI’s Rubber Duck is a lightweight, second-opinion AI reviewer that integrates smoothly into the coding workflow. Enable it via `/experimental` mode and Claude models to catch subtle bugs, architectural flaws, and test gaps automatically or on demand. Adopt Rubber Duck reviews for safer, higher quality code generation in demanding or high-assurance development scenarios.
