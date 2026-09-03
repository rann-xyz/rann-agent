"""
Skill registry and metadata management.

Provides a centralized registry for discovering, registering, and managing
skills with full metadata, categorization, search, and persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class SkillMetadata:
    """Metadata describing a registered skill."""

    name: str
    description: str
    category: str
    version: str = "1.0.0"
    author: str = "unknown"
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SkillMetadata:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class SkillRegistry:
    """
    Central registry for skill registration, discovery, and management.

    Supports loading skill metadata from a directory of JSON files,
    in-memory registration, search by tags/category, and enable/disable.
    """

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self._skills: dict[str, SkillMetadata] = {}
        self._skills_dir = skills_dir
        self._logger = logger.bind(component="skill_registry")

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _registry_path(self) -> Path:
        base = self._skills_dir or Path("~/.rann-agent").expanduser()
        return base / "skills_registry.json"

    def save(self) -> None:
        """Persist the in-memory registry to JSON."""
        path = self._registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {sid: meta.to_dict() for sid, meta in self._skills.items()}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        self._logger.debug("registry_saved", path=str(path), count=len(self._skills))

    def load(self) -> None:
        """Load persisted registry from JSON, merging with in-memory entries."""
        path = self._registry_path()
        if not path.exists():
            self._logger.debug("registry_not_found", path=str(path))
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            for sid, meta_dict in data.items():
                meta = SkillMetadata.from_dict(meta_dict)
                # Don't overwrite programmatically registered skills
                if sid not in self._skills:
                    self._skills[sid] = meta
            self._logger.info("registry_loaded", path=str(path), count=len(self._skills))
        except (json.JSONDecodeError, TypeError) as exc:
            self._logger.error("registry_load_failed", path=str(path), error=str(exc))

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    def register(self, skill_id: str, metadata: SkillMetadata) -> None:
        """Register or update a skill's metadata."""
        metadata.updated_at = datetime.utcnow().isoformat()
        is_new = skill_id not in self._skills
        self._skills[skill_id] = metadata
        self.save()
        action = "registered" if is_new else "updated"
        self._logger.info("skill_registered", skill_id=skill_id, action=action)

    def unregister(self, skill_id: str) -> bool:
        """Remove a skill from the registry. Returns True if it existed."""
        if skill_id in self._skills:
            del self._skills[skill_id]
            self.save()
            self._logger.info("skill_unregistered", skill_id=skill_id)
            return True
        return False

    # -------------------------------------------------------------------------
    # Accessors
    # -------------------------------------------------------------------------

    def get(self, skill_id: str) -> Optional[SkillMetadata]:
        """Retrieve metadata for a specific skill."""
        return self._skills.get(skill_id)

    def list_all(self) -> list[SkillMetadata]:
        """Return all registered skill metadata."""
        return list(self._skills.values())

    def list_by_category(self, category: str) -> list[SkillMetadata]:
        """Return skills belonging to a given category."""
        return [m for m in self._skills.values() if m.category == category]

    def list_enabled(self) -> list[SkillMetadata]:
        """Return only enabled skills."""
        return [m for m in self._skills.values() if m.enabled]

    def list_disabled(self) -> list[SkillMetadata]:
        """Return only disabled skills."""
        return [m for m in self._skills.values() if not m.enabled]

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(self, query: str) -> list[SkillMetadata]:
        """
        Simple substring search across name, description, tags, and author.
        Case-insensitive.
        """
        lower = query.lower()
        results: list[SkillMetadata] = []
        for meta in self._skills.values():
            if (
                lower in meta.name.lower()
                or lower in meta.description.lower()
                or lower in meta.author.lower()
                or any(lower in tag.lower() for tag in meta.tags)
            ):
                results.append(meta)
        self._logger.debug("search_performed", query=query, results=len(results))
        return results

    def search_by_tag(self, tag: str) -> list[SkillMetadata]:
        """Return skills that have the given tag."""
        lower = tag.lower()
        return [m for m in self._skills.values() if any(lower in t.lower() for t in m.tags)]

    # -------------------------------------------------------------------------
    # Enable / Disable
    # -------------------------------------------------------------------------

    def enable(self, skill_id: str) -> bool:
        """Enable a skill. Returns True if the skill was found and enabled."""
        meta = self._skills.get(skill_id)
        if meta is None:
            return False
        meta.enabled = True
        meta.updated_at = datetime.utcnow().isoformat()
        self.save()
        self._logger.info("skill_enabled", skill_id=skill_id)
        return True

    def disable(self, skill_id: str) -> bool:
        """Disable a skill. Returns True if the skill was found and disabled."""
        meta = self._skills.get(skill_id)
        if meta is None:
            return False
        meta.enabled = False
        meta.updated_at = datetime.utcnow().isoformat()
        self.save()
        self._logger.info("skill_disabled", skill_id=skill_id)
        return True

    # -------------------------------------------------------------------------
    # Directory scanner
    # -------------------------------------------------------------------------

    def scan_skills_dir(self, path: Path) -> int:
        """
        Recursively scan *path* for JSON files and register them as skills.
        Each JSON file must contain a top-level object with at least ``name``
        and ``description`` fields conforming to SkillMetadata.
        The file stem (filename without extension) is used as the skill_id.
        """
        count = 0
        if not path.is_dir():
            self._logger.warning("skills_dir_not_found", path=str(path))
            return 0

        for json_file in path.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as fh:
                    data = json.load(fh)
                skill_id = json_file.stem
                metadata = SkillMetadata.from_dict(data)
                self.register(skill_id, metadata)
                count += 1
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                self._logger.warning(
                    "skill_file_skipped",
                    file=str(json_file),
                    error=str(exc),
                )
                continue

        self._logger.info("skills_dir_scanned", path=str(path), registered=count)
        return count