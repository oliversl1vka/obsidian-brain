import os
import yaml
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Config:
    openai_api_key: str
    telegram_bot_token: str
    telegram_user_id: int
    model_name: str
    max_summary_sentences: int
    data_dir: Path
    log_level: str
    brain_dir: Path
    digest_sources_file: str
    digest_schedule: str
    git_remote: str
    git_branch: str

def load_config() -> Config:
    config_path = Path("config.yaml")
    
    # Load defaults/file config
    yaml_config = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}

    # Environment variables override file config
    api_key = os.environ.get("OPENAI_API_KEY", yaml_config.get("openai_api_key", ""))
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", yaml_config.get("telegram_bot_token", ""))
    
    # User ID can be string from env, needs int conversion
    env_user_id = os.environ.get("TELEGRAM_USER_ID")
    user_id_raw = env_user_id if env_user_id is not None else yaml_config.get("telegram_user_id", 0)
    try:
        user_id = int(user_id_raw)
    except ValueError:
        user_id = 0

    model_name = os.environ.get("MODEL_NAME", yaml_config.get("model_name", "gpt-4.1-mini"))
    data_dir = Path(os.environ.get("DATA_DIR", yaml_config.get("data_dir", "data")))
    log_level = os.environ.get("LOG_LEVEL", yaml_config.get("log_level", "INFO")).upper()
    brain_dir = Path(os.environ.get("BRAIN_DIR", yaml_config.get("brain_dir", "obsidian-brain")))
    digest_sources_file = os.environ.get("DIGEST_SOURCES_FILE", yaml_config.get("digest_sources_file", "digest_sources.txt"))
    digest_schedule = os.environ.get("DIGEST_SCHEDULE", yaml_config.get("digest_schedule", "07:00"))
    git_remote = os.environ.get("GIT_REMOTE", yaml_config.get("git_remote", "origin"))
    git_branch = os.environ.get("GIT_BRANCH", yaml_config.get("git_branch", "master"))

    return Config(
        openai_api_key=api_key,
        telegram_bot_token=bot_token,
        telegram_user_id=user_id,
        model_name=model_name,
        max_summary_sentences=yaml_config.get("max_summary_sentences", 5),
        data_dir=data_dir,
        log_level=log_level,
        brain_dir=brain_dir,
        digest_sources_file=digest_sources_file,
        digest_schedule=digest_schedule,
        git_remote=git_remote,
        git_branch=git_branch,
    )

# Global config instance
settings = load_config()
