import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from src.brain.skill_writer import SkillManifestEntry
from src.llm.base import LLMBase
from src.pipeline import PipelineResult

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)
_VALID_ARTIFACT_TYPES = {"skill", "instruction", "prompt", "agent", "none"}
_VALID_ACTIONS = {"create", "merge", "skip"}


@dataclass
class SkillEvaluationResult:
    worth_creating: bool
    reasoning: str
    artifact_type: str
    name: str
    description: str
    domain_path: str
    action: str
    existing_path: str = ""
    merge_reasoning: str = ""


class SkillEvaluator(LLMBase):
    async def evaluate_skill(
        self,
        result: PipelineResult,
        candidates: list[SkillManifestEntry],
    ) -> SkillEvaluationResult:
        user_profile = os.environ.get("USER_PROFILE")
        if not user_profile:
            profile_path = _PROJECT_ROOT / "user_profile.md"
            try:
                user_profile = profile_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                user_profile = "No user profile found."

        candidates_text = self._format_candidates(candidates)
        context = {
            "title": result.title,
            "url": result.url,
            "category": result.category,
            "summary": result.summary,
            "scrape_content": result.scrape_content or "(no scraped content)",
            "user_profile": user_profile,
            "existing_artifacts": candidates_text,
        }

        raw = await self.generate_response(
            str(_PROJECT_ROOT / "prompts" / "evaluate_skill.md"),
            context,
            max_tokens=700,
            system_prompt_template_path=str(_PROJECT_ROOT / "prompts" / "skill_evaluator_system.md"),
        )
        try:
            parsed = _parse_json_response(raw)
            if not isinstance(parsed, dict):
                raise TypeError("Skill evaluator response parsed to non-dict type.")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Skill evaluator returned malformed JSON payload; skipping artifact generation: %s",
                exc,
            )
            return SkillEvaluationResult(
                worth_creating=False,
                reasoning="Evaluator returned malformed JSON.",
                artifact_type="none",
                name="",
                description="",
                domain_path="",
                action="skip",
                existing_path="",
                merge_reasoning="",
            )
        artifact_type = str(parsed.get("artifact_type", "none")).strip().lower()
        action = str(parsed.get("action", "skip")).strip().lower()
        existing_path = str(parsed.get("existing_path", "")).strip()
        valid_paths = {entry.relative_path for entry in candidates}

        if artifact_type not in _VALID_ARTIFACT_TYPES:
            artifact_type = "none"
        if action not in _VALID_ACTIONS:
            action = "skip"
        if existing_path and existing_path not in valid_paths:
            existing_path = ""
            if action in {"merge", "skip"}:
                action = "create" if artifact_type != "none" else "skip"

        worth_creating = bool(parsed.get("worth_creating", False)) and artifact_type != "none"
        if not worth_creating:
            return SkillEvaluationResult(
                worth_creating=False,
                reasoning=str(parsed.get("reasoning", "Filtered out as not skill-worthy.")).strip(),
                artifact_type="none",
                name="",
                description="",
                domain_path="",
                action="skip",
                existing_path="",
                merge_reasoning="",
            )

        name = _slugify(str(parsed.get("name", "")).strip())
        domain_path = _sanitize_domain_path(str(parsed.get("domain_path", "")).strip())
        description = " ".join(str(parsed.get("description", "")).strip().split())
        if not name or not domain_path or not description:
            logger.warning("Skill evaluator returned incomplete create payload; skipping artifact generation.")
            return SkillEvaluationResult(
                worth_creating=False,
                reasoning="Evaluator returned incomplete artifact metadata.",
                artifact_type="none",
                name="",
                description="",
                domain_path="",
                action="skip",
            )

        if action in {"merge", "skip"} and not existing_path:
            action = "create"

        return SkillEvaluationResult(
            worth_creating=True,
            reasoning=str(parsed.get("reasoning", "")).strip(),
            artifact_type=artifact_type,
            name=name,
            description=description,
            domain_path=domain_path,
            action=action,
            existing_path=existing_path,
            merge_reasoning=str(parsed.get("merge_reasoning", "")).strip(),
        )

    def _format_candidates(self, candidates: list[SkillManifestEntry]) -> str:
        if not candidates:
            return "(none)"

        lines = []
        for entry in candidates:
            source_suffix = ""
            if entry.source_urls:
                source_suffix = f" | source_hosts={', '.join(sorted({_source_host(url) for url in entry.source_urls if _source_host(url)}))}"
            lines.append(
                f"- path={entry.relative_path} | type={entry.artifact_type} | name={entry.name} | domain={entry.domain_path or '(root)'} | description={entry.description}{source_suffix}"
            )
        return "\n".join(lines)


def _parse_json_response(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\\n?```$", "", text.strip())
    return json.loads(text.strip())


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\\s-]", "", text)
    text = re.sub(r"[\\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:64]


def _sanitize_domain_path(text: str) -> str:
    parts = []
    for part in text.split("/"):
        slug = _slugify(part)
        if slug:
            parts.append(slug)
    return "/".join(parts)


def _source_host(url: str) -> str:
    from urllib.parse import urlparse

    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""
