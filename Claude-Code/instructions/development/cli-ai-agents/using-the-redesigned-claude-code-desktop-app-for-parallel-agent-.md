---
name: using-the-redesigned-claude-code-desktop-app-for-parallel-agent-
description: Guidance on using the redesigned Claude Code desktop app for managing
  parallel agent sessions, workspace layout, integrated dev tools, and CLI plugin
  parity. Use when adopting or upgrading to the new desktop app to improve workflow
  efficiency with multiple AI agent coding tasks.
type: instruction
artifact_type: instruction
domain_path: development/cli-ai-agents
source_urls:
- https://claude.com/blog/claude-code-desktop-redesign
brain_entry: Entries/2026-04-20-redesigning-claude-code-on-desktop-for-parallel-agents-claud
---

# Using the Redesigned Claude Code Desktop App for Parallel Agent Sessions

## When to Use

- Adopting or upgrading to the redesigned Claude Code desktop app
- Managing multiple simultaneous AI coding agent sessions
- Coordinating parallel workflows like refactors, bug fixes, and test writing across repos
- Improving efficiency by orchestrating multiple agent tasks with integrated dev tools

## Key Features & Workflows

### Session Management Sidebar

- View all active and recent sessions in a single sidebar.
- Filter sessions by status, project, or environment.
- Group sessions by project for faster navigation.
- Sessions archive automatically when their PR merges or closes to reduce clutter.

### Parallel Work Orchestration

- Run multiple Claude Code tasks in parallel (e.g., refactors, fixes, tests in different repos).
- Monitor streaming responses live as Claude generates outputs.
- Switch quickly among sessions via keyboard shortcuts (e.g., `⌘ + /` or `Ctrl + /` for shortcut list).

### Workspace Layout

- Drag-and-drop panes to customize workspace layout.
- Arrange terminal, preview, diff viewer, and chat into grids suited to your workflow.

### Integrated Developer Tools

- Use the built-in terminal and file editor to review, tweak, and ship Claude’s code without leaving the app.
- Open side chats to branch off conversations without affecting main task threads (keyboard shortcut `⌘ + ;` or `Ctrl + ;`).

### CLI Plugin Parity & Remote Support

- Run Claude Code CLI plugins inside the desktop app identically to terminal usage.
- Manage sessions locally or in the cloud.
- SSH support now extended to Mac (in addition to Linux) for targeting remote machines.

### Interface Verbosity & Usage Monitoring

- Choose from three view modes:
  - Verbose (full transparency into Claude’s tool calls)
  - Normal (balanced detail)
  - Summary (just results)
- View context window and session usage from a usage button.

### Performance Improvements

- Rebuilt for increased reliability and speed.
- Streaming response support enhances responsiveness.

## Guidelines for Effective Use

- Always keep multiple sessions organized via the sidebar filters and groups.
- Use keyboard shortcuts extensively to switch sessions, spawn new ones, or open side chats.
- Leverage the drag-and-drop grid layout to tailor your workspace for multitasking.
- Utilize side chats to ask clarifying questions without confusing main session tasks.
- Integrate your existing CLI plugins into the desktop app for a seamless transition.
- Use SSH support to leverage remote computing resources from Mac or Linux.

## Getting Started

1. Download or update to the latest Claude Code desktop app.
2. Familiarize yourself with the sidebar session management and workspace layout.
3. Install or configure any CLI plugins your projects depend on.
4. Start running parallel agents across repositories.
5. Use side chats and integrated tools to review and ship results efficiently.

Explore official documentation and resources for advanced usage.

---

*This instruction summarizes durable best practices for leveraging the redesigned Claude Code desktop app to optimize parallel AI agent coding workflows.*
