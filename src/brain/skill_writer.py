import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import yaml

from src.config import settings

if TYPE_CHECKING:
    from src.llm.skill_formatter import ReferenceFile

logger = logging.getLogger(__name__)
_ARTIFACT_DIRS = {
    "skill": "skills",
    "instruction": "instructions",
    "prompt": "prompts",
    "agent": "agents",
}


@dataclass
class SkillManifestEntry:
    artifact_type: str
    name: str
    description: str
    domain_path: str
    relative_path: str
    source_urls: list[str] = field(default_factory=list)


@dataclass
class WrittenArtifact:
    artifact_type: str
    name: str
    relative_path: str
    path: Path
    action: str
    domain_path: str


class SkillWriter:
    def __init__(self):
        self.root: Path = settings.skills_dir

    def ensure_structure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in _ARTIFACT_DIRS.values():
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def read_existing_artifact(self, relative_path: str) -> str:
        path = self.root / relative_path
        return path.read_text(encoding="utf-8")

    def get_skill_manifest(self) -> list[SkillManifestEntry]:
        if not self.root.exists():
            return []

        manifest: list[SkillManifestEntry] = []
        for artifact_type, base_dir_name in _ARTIFACT_DIRS.items():
            base_dir = self.root / base_dir_name
            if not base_dir.exists():
                continue
            for md_file in base_dir.rglob("*.md"):
                relative_path = md_file.relative_to(self.root).as_posix()
                if relative_path == "index.md":
                    continue
                if "/references/" in relative_path or relative_path.endswith("_references/index.md"):
                    continue
                if artifact_type == "skill" and md_file.name != "SKILL.md":
                    continue
                if artifact_type != "skill" and md_file.parent.name.endswith("_references"):
                    continue
                metadata = _parse_frontmatter(md_file)
                domain_path, name = _derive_path_parts(self.root, md_file, artifact_type)
                description = str(metadata.get("description", "")).strip()
                source_urls = _coerce_urls(metadata.get("source_urls", metadata.get("source_url", [])))
                manifest.append(
                    SkillManifestEntry(
                        artifact_type=artifact_type,
                        name=str(metadata.get("name", name)).strip() or name,
                        description=description,
                        domain_path=domain_path,
                        relative_path=relative_path,
                        source_urls=source_urls,
                    )
                )
        manifest.sort(key=lambda item: (item.artifact_type, item.domain_path, item.name))
        return manifest

    def find_relevant_entries(self, url: str, title: str, summary: str, limit: int = 8) -> list[SkillManifestEntry]:
        query_tokens = _tokenize(" ".join([title, summary, urlparse(url).netloc, urlparse(url).path.replace("/", " ")]))
        host = urlparse(url).netloc.lower()
        scored: list[tuple[int, SkillManifestEntry]] = []
        for entry in self.get_skill_manifest():
            entry_tokens = _tokenize(" ".join([
                entry.name,
                entry.description,
                entry.domain_path.replace("/", " "),
                entry.relative_path.replace("/", " "),
                " ".join(entry.source_urls),
            ]))
            overlap = len(query_tokens & entry_tokens)
            score = overlap * 3
            normalized_name = entry.name.replace("-", " ")
            if normalized_name and normalized_name in f"{title} {summary}".lower():
                score += 6
            if any(_safe_host(source_url) == host for source_url in entry.source_urls):
                score += 4
            if host and host in entry.relative_path.lower():
                score += 2
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [entry for _, entry in scored[:limit]]

    def write_artifact(
        self,
        artifact_type: str,
        name: str,
        description: str,
        domain_path: str,
        content: str,
        source_url: str,
        references: list["ReferenceFile"] | None = None,
        brain_entry: str = "",
        existing_relative_path: str = "",
    ) -> WrittenArtifact:
        self.ensure_structure()
        target_path = self._resolve_main_path(artifact_type, domain_path, name, existing_relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        was_existing = target_path.exists()
        existing_metadata = _parse_frontmatter(target_path) if target_path.exists() else {}

        merged_source_urls = _merge_source_urls(existing_metadata.get("source_urls", []), source_url)
        metadata = {
            "name": name,
            "description": description,
        }
        if artifact_type != "skill":
            metadata["type"] = artifact_type
        metadata["artifact_type"] = artifact_type
        metadata["domain_path"] = domain_path
        metadata["source_urls"] = merged_source_urls
        if brain_entry:
            metadata["brain_entry"] = brain_entry

        rendered = _with_frontmatter(content, metadata)
        target_path.write_text(rendered, encoding="utf-8")

        for reference in references or []:
            ref_path = self._resolve_reference_path(target_path, reference.filename)
            ref_path.parent.mkdir(parents=True, exist_ok=True)
            ref_path.write_text(reference.content.strip() + "\n", encoding="utf-8")

        self._write_index()
        relative_path = target_path.relative_to(self.root).as_posix()
        action = "updated" if was_existing or bool(existing_relative_path) else "created"
        logger.info("Claude artifact %s: %s", action, relative_path)
        return WrittenArtifact(
            artifact_type=artifact_type,
            name=name,
            relative_path=relative_path,
            path=target_path,
            action=action,
            domain_path=domain_path,
        )

    def _resolve_main_path(self, artifact_type: str, domain_path: str, name: str, existing_relative_path: str) -> Path:
        if existing_relative_path:
            return self.root / existing_relative_path
        base_dir = self.root / _ARTIFACT_DIRS[artifact_type]
        domain_dir = base_dir / Path(domain_path) if domain_path else base_dir
        if artifact_type == "skill":
            return domain_dir / name / "SKILL.md"
        return domain_dir / f"{name}.md"

    def _resolve_reference_path(self, main_path: Path, filename: str) -> Path:
        if main_path.name == "SKILL.md":
            return main_path.parent / "references" / filename
        return main_path.parent / f"{main_path.stem}_references" / filename

    def _write_index(self) -> None:
        self.ensure_structure()
        entries = self.get_skill_manifest()
        sections = [
            "# Claude Code Artifacts",
            "",
            "> Generated alongside the brain vault for direct Claude Code reuse.",
            "",
        ]
        for artifact_type in ["skill", "instruction", "prompt", "agent"]:
            group = [entry for entry in entries if entry.artifact_type == artifact_type]
            title = {"skill": "Skills", "instruction": "Instructions", "prompt": "Prompts", "agent": "Agents"}[artifact_type]
            sections.append(f"## {title}")
            if not group:
                sections.append("\n- (none)\n")
                continue
            for entry in group:
                source_suffix = ""
                if entry.source_urls:
                    source_suffix = f" | sources: {', '.join(entry.source_urls[:2])}"
                sections.append(
                    f"- `{entry.name}` → [{entry.relative_path}]({entry.relative_path}) — {entry.description}{source_suffix}"
                )
            sections.append("")
        (self.root / "index.md").write_text("\n".join(sections).strip() + "\n", encoding="utf-8")


def _derive_path_parts(root: Path, md_file: Path, artifact_type: str) -> tuple[str, str]:
    relative = md_file.relative_to(root)
    parts = relative.parts
    if artifact_type == "skill":
        domain_path = "/".join(parts[1:-2])
        name = parts[-2]
        return domain_path, name
    domain_path = "/".join(parts[1:-1])
    return domain_path, md_file.stem


def _parse_frontmatter(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    _, _, remainder = text.partition("---\n")
    frontmatter_text, separator, _ = remainder.partition("\n---\n")
    if not separator:
        return {}
    parsed = yaml.safe_load(frontmatter_text) or {}
    return parsed if isinstance(parsed, dict) else {}


def _with_frontmatter(content: str, metadata: dict) -> str:
    body = content.strip()
    existing_body = body
    if body.startswith("---\n"):
        _, _, remainder = body.partition("---\n")
        _, separator, body_after = remainder.partition("\n---\n")
        if separator:
            existing_body = body_after.strip()
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{frontmatter}\n---\n\n{existing_body}\n"


def _coerce_urls(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _merge_source_urls(existing: object, new_url: str) -> list[str]:
    urls = _coerce_urls(existing)
    if new_url and new_url not in urls:
        urls.append(new_url)
    return urls


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _safe_host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""
