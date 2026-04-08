# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the bot locally
python src/bot.py

# Run unit tests
pytest tests/unit/ -q

# Run all tests (unit + integration)
pytest tests/

# Lint
ruff check .
```

## Setup

Requires `config.yaml` (copy from `config.yaml.example`) with `openai_api_key`, `telegram_bot_token`, and `telegram_user_id`. Also requires `user_profile.md` (copy from `user_profile.example.md`).

For Railway deployment, set environment variables instead: `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `USER_PROFILE` (full profile content as multi-line text), `DATA_DIR=/data` (with volume mounted at `/data`).

## Architecture

LinkStash is a Telegram bot that takes URLs, scrapes their content, summarizes and categorizes them via OpenAI LLM, evaluates relevance against a user profile, and stores results as Markdown files.

**Processing pipeline** (per URL, orchestrated by `src/pipeline.py`):
1. Duplicate check (URL normalization → scan all `.md` files)
2. Scrape content → `ScrapeResult`
3. LLM summarize → 1–5 sentence summary tailored to user profile
4. LLM categorize → one of the categories defined in `config.yaml`
5. LLM evaluate → `notify` (write to category file) or `do not notify` (write to `bin.md`)
6. Write entry to `data/<category-slug>.md` and update `data/index.md`

**Scraper factory** (`src/scrapers/base.py`): `get_scraper_for_url()` dispatches to `PdfScraper`, `GitHubScraper`, `NotebookScraper`, or `ArticleScraper` based on URL pattern. Unsupported binary extensions (`.zip`, `.exe`, etc.) are rejected immediately.

**LLM modules** (`src/llm/`): All inherit `LLMBase`, which loads a prompt template from `prompts/`, formats it with a context dict, calls OpenAI async API, and logs the call to `logs/api_calls.log` (JSONL). Prompt templates live in `prompts/summarize.md`, `prompts/categorize.md`, `prompts/evaluate.md`.

**Storage** (`src/storage/writer.py`): Markdown files in `data/` — one file per category plus `bin.md` and `index.md`. Entries prepended (newest first). URL normalization strips fragments, sorts query params, and lowercases for deduplication.

**Config** (`src/config.py`): Loads `config.yaml` then overrides with env vars. Returns a `Config` dataclass singleton. Categories are defined in `config.yaml` under `categories:`.

**Bot security**: Only the `telegram_user_id` from config is allowed to send commands. All other senders are silently ignored.

## Key Patterns

- All I/O is `async/await` (httpx, OpenAI client, Telegram handlers)
- Each pipeline step returns a result dataclass with a `status` field — no bare `except:` blocks
- Private methods prefixed with `_`; public API is the `scrape()` / `generate_response()` methods on base classes
- Tests use `pytest-asyncio`; external calls (HTTP, OpenAI) are mocked — no live network in unit tests
- Absolute imports from `src.*` throughout; `PYTHONPATH` must include the repo root (Railway sets `PYTHONPATH=/app`)
