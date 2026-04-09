import logging
from dataclasses import dataclass
from pathlib import Path

from src.brain.skill_writer import SkillWriter, WrittenArtifact
from src.brain.writer import WrittenEntry
from src.config import settings
from src.llm.skill_evaluator import SkillEvaluator
from src.llm.skill_formatter import SkillFormatter
from src.pipeline import PipelineResult

logger = logging.getLogger(__name__)


@dataclass
class SkillPipelineResult:
    action: str
    artifact_type: str
    name: str
    relative_path: str
    reasoning: str

    def format_telegram_message(self) -> str:
        verb = "created" if self.action == "created" else "updated"
        emoji = "⚡" if self.action == "created" else "🔄"
        return f"{emoji} Claude {self.artifact_type} {verb}: `{self.relative_path}`"


async def process_skill(
    result: PipelineResult,
    written_entry: WrittenEntry | None = None,
) -> SkillPipelineResult | None:
    if not settings.skills_enabled or not result.scrape_content.strip():
        return None

    writer = SkillWriter()
    candidates = writer.find_relevant_entries(result.url, result.title, result.summary)
    evaluator = SkillEvaluator()
    decision = await evaluator.evaluate_skill(result, candidates)

    if not decision.worth_creating or decision.action == "skip":
        logger.info("Claude artifact skipped for %s: %s", result.url, decision.reasoning)
        return None

    if decision.action == "merge" and decision.existing_path:
        existing_entry = next((entry for entry in candidates if entry.relative_path == decision.existing_path), None)
        if existing_entry is not None:
            decision.artifact_type = existing_entry.artifact_type
            decision.name = existing_entry.name or decision.name
            decision.domain_path = existing_entry.domain_path or decision.domain_path
            if not decision.description:
                decision.description = existing_entry.description

    existing_content = ""
    if decision.existing_path:
        try:
            existing_content = writer.read_existing_artifact(decision.existing_path)
        except FileNotFoundError:
            logger.warning("Selected merge target missing: %s", decision.existing_path)
            decision.existing_path = ""
            decision.action = "create"

    formatter = SkillFormatter()
    formatted = await formatter.format_artifact(decision, result, existing_content=existing_content)

    brain_entry_link = ""
    if written_entry is not None:
        entry_ref = Path("Entries") / written_entry.entry_path.name
        brain_entry_link = entry_ref.with_suffix("").as_posix()

    written = writer.write_artifact(
        artifact_type=decision.artifact_type,
        name=decision.name,
        description=decision.description,
        domain_path=decision.domain_path,
        content=formatted.content,
        source_url=result.url,
        references=formatted.references,
        brain_entry=brain_entry_link,
        existing_relative_path=decision.existing_path,
    )
    return _to_pipeline_result(written, decision.reasoning)


def _to_pipeline_result(written: WrittenArtifact, reasoning: str) -> SkillPipelineResult:
    return SkillPipelineResult(
        action=written.action,
        artifact_type=written.artifact_type,
        name=written.name,
        relative_path=written.relative_path,
        reasoning=reasoning,
    )
