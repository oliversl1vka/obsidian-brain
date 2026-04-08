import logging
import json
from pathlib import Path
from datetime import datetime, timezone

def setup_logging(log_level: str = "INFO"):
    """Configure base Python logging."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / "pipeline.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

def log_api_call(model: str, prompt: str, response: str, prompt_tokens: int, completion_tokens: int):
    """Log OpenAI API calls in JSONL format for auditing."""
    log_file = Path("logs") / "api_calls.log"
    
    # Truncate prompt if it's too massive for logging
    if len(prompt) > 1000:
        prompt = prompt[:1000] + "... [truncated]"
        
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt": prompt,
        "response": response,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": prompt_tokens + completion_tokens
        }
    }
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
