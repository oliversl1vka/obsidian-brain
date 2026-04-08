import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.llm.base import LLMBase
from src.pipeline import PipelineResult

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


@dataclass
class FormattedEntry:
    title: str
    url: str
    date: str
    category: str
    context: str
    insight: str
    application: str
    tags: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


class EntryFormatter(LLMBase):
    async def format_entry(self, result: PipelineResult, existing_titles: list[str]) -> FormattedEntry:
        """Format a PipelineResult into a structured knowledge entry via LLM."""
        user_profile = os.environ.get("USER_PROFILE")
        if not user_profile:
            profile_path = _PROJECT_ROOT / "user_profile.md"
            try:
                user_profile = profile_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                user_profile = "No user profile found."

        titles_text = "\n".join(f"- {t}" for t in existing_titles[:50]) if existing_titles else "(none yet)"

        context = {
            "title": result.title,
            "url": result.url,
            "category": result.category,
            "summary": result.summary,
            "user_profile": user_profile,
            "existing_titles": titles_text,
        }

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            raw = await self.generate_response(
                str(_PROJECT_ROOT / "prompts" / "format_entry.md"), context, max_tokens=600
            )
            parsed = _parse_json_response(raw)
            return FormattedEntry(
                title=result.title,
                url=result.url,
                date=date_str,
                category=result.category,
                context=parsed.get("context", result.summary),
                insight=parsed.get("insight", result.summary),
                application=parsed.get("application", ""),
                tags=parsed.get("tags", []),
                see_also=parsed.get("see_also", []),
            )
        except Exception as e:
            logger.error(f"Formatter LLM error, using fallback entry: {e}")
            return FormattedEntry(
                title=result.title,
                url=result.url,
                date=date_str,
                category=result.category,
                context="Saved for future reference.",
                insight=result.summary,
                application="",
                tags=[],
                see_also=[],
            )


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, stripping any markdown code fences."""
    text = re.sub(r"^```(?:json)?\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text.strip())
    return json.loads(text.strip())
