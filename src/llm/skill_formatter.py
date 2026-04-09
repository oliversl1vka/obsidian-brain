import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.llm.base import LLMBase
from src.llm.skill_evaluator import SkillEvaluationResult
from src.pipeline import PipelineResult

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


@dataclass
class ReferenceFile:
    filename: str
    content: str


@dataclass
class FormattedArtifact:
    content: str
    references: list[ReferenceFile] = field(default_factory=list)


class SkillFormatter(LLMBase):
    async def format_artifact(
        self,
        decision: SkillEvaluationResult,
        result: PipelineResult,
        existing_content: str = "",
    ) -> FormattedArtifact:
        user_profile = os.environ.get("USER_PROFILE")
        if not user_profile:
            profile_path = _PROJECT_ROOT / "user_profile.md"
            try:
                user_profile = profile_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                user_profile = "No user profile found."

        context = {
            "mode": "merge" if existing_content.strip() else "create",
            "artifact_type": decision.artifact_type,
            "name": decision.name,
            "description": decision.description,
            "domain_path": decision.domain_path,
            "merge_reasoning": decision.merge_reasoning or "",
            "title": result.title,
            "url": result.url,
            "category": result.category,
            "summary": result.summary,
            "scrape_content": result.scrape_content or "(no scraped content)",
            "existing_content": existing_content or "(none)",
            "user_profile": user_profile,
        }

        try:
            raw = await self.generate_response(
                str(_PROJECT_ROOT / "prompts" / "format_skill.md"),
                context,
                max_tokens=1800,
                system_prompt_template_path=str(_PROJECT_ROOT / "prompts" / "skill_formatter_system.md"),
            )
            parsed = _parse_json_response(raw)
            content = str(parsed.get("content", "")).strip()
            references = []
            for item in parsed.get("references", []):
                if not isinstance(item, dict):
                    continue
                filename = _sanitize_filename(str(item.get("filename", "")).strip())
                file_content = str(item.get("content", "")).strip()
                if filename and file_content:
                    references.append(ReferenceFile(filename=filename, content=file_content))
            if content:
                return FormattedArtifact(content=content, references=references)
        except Exception as e:
            logger.error(f"Skill formatter error, using fallback artifact: {e}")

        return FormattedArtifact(content=_fallback_content(decision, result, existing_content), references=[])


def _parse_json_response(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\\n?```$", "", text.strip())
    return json.loads(text.strip())


def _sanitize_filename(filename: str) -> str:
    filename = filename.lower().strip()
    filename = re.sub(r"[^a-z0-9._-]", "-", filename)
    filename = re.sub(r"-+", "-", filename)
    if not filename.endswith(".md"):
        filename = f"{filename}.md"
    return filename.strip("-")


def _fallback_content(
    decision: SkillEvaluationResult,
    result: PipelineResult,
    existing_content: str,
) -> str:
    if existing_content.strip():
        return existing_content

    if decision.artifact_type == "skill":
        return (
            "---\n"
            f"name: {decision.name}\n"
            f"description: {decision.description}\n"
            "---\n\n"
            f"# {result.title}\n\n"
            "## When to Use\n"
            f"- Use when working on {decision.domain_path.replace('/', ' ')} tasks related to this source.\n\n"
            "## Workflow\n"
            f"1. Review the source summary: {result.summary}\n"
            f"2. Apply the extracted technique to the current task.\n"
            f"3. Revisit the source URL for deeper implementation detail: {result.url}\n"
        )

    title = decision.name.replace("-", " ").title()
    return (
        "---\n"
        f"name: {decision.name}\n"
        f"description: {decision.description}\n"
        f"type: {decision.artifact_type}\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Purpose\n"
        f"{result.summary}\n\n"
        "## Source\n"
        f"- {result.url}\n"
    )
