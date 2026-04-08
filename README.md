# LinkStash

A personal link intelligence bot. Send URLs to a Telegram bot and LinkStash scrapes the content, summarises it with OpenAI, categorises it, and evaluates relevance against your personal profile. Relevant links are stored in human-readable Markdown files; irrelevant ones go to a bin.

**Supported link types:** web articles, GitHub repositories, Jupyter notebooks, PDF documents.

## Requirements

- Python 3.11+
- A Telegram bot token — create one via [@BotFather](https://t.me/botfather)
- An OpenAI API key

---

## Local setup

```bash
# 1. Clone and enter the repo
git clone <your-repo-url>
cd LinkStash

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp config.yaml.example config.yaml
# Edit config.yaml and fill in:
#   openai_api_key, telegram_bot_token, telegram_user_id

# 5. Set your personal profile (controls what is "relevant")
cp user_profile.example.md user_profile.md
# Edit user_profile.md with your current projects, interests, and goals

# 6. Start the bot
python -m src.bot
```

Send one or more URLs to your bot (one per line). Use `/start` to confirm it's alive, `/status` to see your saved link counts.

### Finding your Telegram user ID

Send a message to [@userinfobot](https://t.me/userinfobot) — it replies with your numeric user ID.

---

## Railway deployment (24/7)

Railway runs the bot as a persistent worker process. Saved links are written to disk, so you should attach a **Volume** to keep data across restarts.

### Step 1 — Push to GitHub

Make sure your repo is pushed to GitHub (no secrets — `config.yaml` is gitignored).

### Step 2 — Create a Railway project

1. Go to [railway.com](https://railway.com) → **New Project** → **Deploy from GitHub repo**
2. Select your LinkStash repository
3. Railway auto-detects Python via `runtime.txt` and `requirements.txt`

### Step 3 — Set environment variables

In the Railway dashboard → your service → **Variables**, add:

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | your OpenAI API key |
| `TELEGRAM_BOT_TOKEN` | your bot token from BotFather |
| `TELEGRAM_USER_ID` | your numeric Telegram user ID |
| `USER_PROFILE` | paste the full contents of your `user_profile.md` here |
| `MODEL_NAME` | `gpt-4.1-mini` (or any OpenAI model you prefer) |
| `DATA_DIR` | `/data` (if using a Volume — see below) or leave unset |
| `BRAIN_DIR` | optional — defaults to `/data/obsidian-brain` when `DATA_DIR=/data` |
| `GITHUB_TOKEN` | optional but recommended for brain sync — fine-grained PAT with access to the brain repo |
| `GIT_REPO_SLUG` | optional but recommended for brain sync — e.g. `youruser/linkstash-brain` |

`USER_PROFILE` supports multi-line text — Railway handles it correctly.

### Step 4 — Add a Volume (recommended)

Without a Volume, saved link data is lost every time the service restarts.

1. Railway dashboard → your service → **Volumes** → **Add Volume**
2. Mount path: `/data`
3. Set `DATA_DIR=/data` in your environment variables

By default, LinkStash now stores the Obsidian brain under `DATA_DIR/obsidian-brain`, so attaching a volume keeps the brain across restarts without checking it into the code repository.

### Step 4.5 — Recommended public/private split

If you want the LinkStash code repo to be public while keeping your brain private:

1. Keep the code in your public `linkstash` repository
2. Create a separate **private** repo just for the brain, for example `youruser/linkstash-brain`
3. Set:
   - `DATA_DIR=/data`
   - `BRAIN_DIR=/data/obsidian-brain` (or leave it unset and use the default)
   - `GITHUB_TOKEN=<token with access to the private brain repo>`
   - `GIT_REPO_SLUG=youruser/linkstash-brain`

LinkStash will initialize a dedicated git repo inside the brain directory and push only the brain files there, which keeps personal notes out of the public source repo.

### Step 5 — Deploy

Railway deploys automatically on every push to your connected branch. The first deploy triggers immediately after you set your variables.

Check **Logs** in the Railway dashboard to confirm the bot started:
```
Starting LinkStash Bot...
```

---

## Configuration reference

All settings can be provided via environment variables (takes priority) or `config.yaml`:

| Env var | config.yaml key | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | `openai_api_key` | — | OpenAI API key |
| `TELEGRAM_BOT_TOKEN` | `telegram_bot_token` | — | Telegram bot token |
| `TELEGRAM_USER_ID` | `telegram_user_id` | — | Authorised Telegram user |
| `MODEL_NAME` | `model_name` | `gpt-4.1-mini` | OpenAI model |
| `DATA_DIR` | `data_dir` | `data` | Where Markdown files are saved |
| `BRAIN_DIR` | `brain_dir` | `<data_dir>/obsidian-brain` | Where the Obsidian brain vault lives |
| `LOG_LEVEL` | `log_level` | `INFO` | Logging verbosity |
| `USER_PROFILE` | *(file only)* | — | Personal profile content (overrides `user_profile.md`) |
| `GITHUB_TOKEN` | *(env only)* | — | Token used to sync the private brain repo |
| `GIT_REPO_SLUG` | *(env only)* | — | Private repo slug for brain sync, e.g. `youruser/linkstash-brain` |

---

## Bot commands

| Command | Description |
|---|---|
| `/start` | Confirm the bot is running |
| `/status` | Total saved links, per-category counts, 3 most recent |

Send any URL (or multiple URLs, one per line) to process them.

---

## Storage

Processed links are saved to `data/` (or `DATA_DIR`) as Markdown files:

```
data/
  index.md              ← master list of all links (newest first)
  ml-general.md
  ai-tools--open-source.md
  research--papers.md
  ...
  bin.md                ← links evaluated as not relevant
```

---

## Testing

```bash
pytest tests/unit/ -q
```

All tests mock external calls — no API keys needed to run the suite.
