import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.config import settings
from src.llm.base import LLMBase

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


@dataclass
class DuplicateInfo:
    new_entry: str
    existing_file: str


@dataclass
class MergeCandidate:
    new_entry: str
    target_entry: str
    reason: str


@dataclass
class AssessmentResult:
    quality_ok: bool
    suggestions: list[str] = field(default_factory=list)
    duplicates: list[DuplicateInfo] = field(default_factory=list)
    merge_candidates: list[MergeCandidate] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.suggestions or self.duplicates or self.merge_candidates)

    def format_telegram_message(self) -> str:
        lines = ["*Brain Assessment*"]
        if self.quality_ok and not self.has_findings:
            lines.append("✅ All entries look good — ready to commit.")
            return "\n".join(lines)
        if self.suggestions:
            lines.append("\n*Quality suggestions:*")
            for suggestion in self.suggestions[:4]:
                lines.append(f"  • {suggestion}")
        if self.duplicates:
            lines.append("\n*Possible duplicates:*")
            for duplicate in self.duplicates[:4]:
                lines.append(f"  ⚠️ \"{duplicate.new_entry}\" may duplicate `{duplicate.existing_file}`")
        if self.merge_candidates:
            lines.append("\n*Merge candidates:*")
            for candidate in self.merge_candidates[:4]:
                lines.append(
                    f"  🔗 \"{candidate.new_entry}\" + \"{candidate.target_entry}\" — {candidate.reason}"
                )
        return "\n".join(lines)


class BrainAssessor(LLMBase):
    async def assess_recent_changes(self) -> AssessmentResult | None:
        """Assess uncommitted changes in the configured brain repo. Returns None if no changes."""
        diff_text, new_files_content = self._collect_changes()

        if not diff_text and not new_files_content:
            logger.info("No brain changes to assess.")
            return None

        user_profile = os.environ.get("USER_PROFILE")
        if not user_profile:
            profile_path = _PROJECT_ROOT / "user_profile.md"
            try:
                user_profile = profile_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                user_profile = "No user profile found."

        context = {
            "new_files_content": new_files_content or "(none)",
            "git_diff": diff_text or "(none)",
            "user_profile": user_profile,
        }

        try:
            raw = await self.generate_response(
                str(_PROJECT_ROOT / "prompts" / "assess_diff.md"), context, max_tokens=800
            )
            return _parse_assessment(raw)
        except Exception as exc:
            logger.error(f"Assessor LLM error: {exc}")
            return AssessmentResult(quality_ok=True)

    def _collect_changes(self) -> tuple[str, str]:
        """Collect (diff_text, new_files_content) for the brain dir since last commit."""
        brain_dir = settings.brain_dir
        try:
            from git import Repo

            repo = Repo(brain_dir)
        except Exception as exc:
            logger.warning(f"Git not available for assessment: {exc}")
            return "", ""

        new_files_content = ""
        for filepath in repo.untracked_files:
            if filepath.startswith("Entries/") or filepath.startswith("Claude-Code/"):
                full_path = brain_dir / filepath
                try:
                    content = full_path.read_text(encoding="utf-8")
                    new_files_content += f"\n### {filepath}\n{content}\n"
                except Exception:
                    pass

        diff_text = ""
        try:
            diff_text = repo.git.diff("HEAD")
        except Exception as exc:
            logger.warning(f"Could not get git diff: {exc}")

        max_chars = 30_000
        if len(new_files_content) > max_chars:
            new_files_content = new_files_content[:max_chars] + "\n[truncated]"
        if len(diff_text) > max_chars:
            diff_text = diff_text[:max_chars] + "\n[truncated]"

        return diff_text, new_files_content


def _parse_assessment(text: str) -> AssessmentResult:
    text = re.sub(r"^```(?:json)?\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text.strip())
    data = json.loads(text.strip())

    duplicates = [
        DuplicateInfo(new_entry=item.get("new_entry", ""), existing_file=item.get("existing_file", ""))
        for item in data.get("duplicates", [])
        if isinstance(item, dict)
    ]
    merge_candidates = [
        MergeCandidate(
            new_entry=item.get("new_entry", ""),
            target_entry=item.get("target_entry", ""),
            reason=item.get("reason", ""),
        )
        for item in data.get("merge_candidates", [])
        if isinstance(item, dict)
    ]
    return AssessmentResult(
        quality_ok=bool(data.get("quality_ok", True)),
        suggestions=data.get("suggestions", []) or [],
        duplicates=duplicates,
        merge_candidates=merge_candidates,
    )
