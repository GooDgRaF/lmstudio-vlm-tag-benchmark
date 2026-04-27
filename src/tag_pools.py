from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import BenchmarkConfig


class TagPoolError(RuntimeError):
    """Tag pool parsing error."""


@dataclass(frozen=True)
class ExplainedTagEntry:
    id: str
    tag: str
    explanation: str


@dataclass(frozen=True)
class TagPools:
    ru_plain: list[str]
    en_plain: list[str]
    ru_explained: list[ExplainedTagEntry]
    en_explained: list[ExplainedTagEntry]

    @property
    def ru_plain_set(self) -> set[str]:
        return set(self.ru_plain)

    @property
    def en_plain_set(self) -> set[str]:
        return set(self.en_plain)

    @property
    def ru_explained_id_to_tag(self) -> dict[str, str]:
        return {entry.id: entry.tag for entry in self.ru_explained}

    @property
    def en_explained_id_to_tag(self) -> dict[str, str]:
        return {entry.id: entry.tag for entry in self.en_explained}

    @property
    def ru_explained_tag_set(self) -> set[str]:
        return {entry.tag for entry in self.ru_explained}

    @property
    def en_explained_tag_set(self) -> set[str]:
        return {entry.tag for entry in self.en_explained}

    def explained_prompt_text(self, language: str) -> str:
        entries = self.ru_explained if language == "ru" else self.en_explained
        return "\n".join(f"[{entry.id}] {entry.tag} - {entry.explanation}" for entry in entries)

    def ids_to_tags(self, language: str, ids: list[str]) -> list[str]:
        mapping = self.ru_explained_id_to_tag if language == "ru" else self.en_explained_id_to_tag
        return [mapping[item] for item in ids if item in mapping]


def _load_plain_pool(path: Path) -> list[str]:
    if not path.exists():
        raise TagPoolError(f"Tag pool file not found: {path}")
    tags: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        tags.append(value)
    return tags


def _load_explained_pool(path: Path) -> list[ExplainedTagEntry]:
    if not path.exists():
        raise TagPoolError(f"Tag pool file not found: {path}")
    entries: list[ExplainedTagEntry] = []
    seen_ids: set[str] = set()
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise TagPoolError(f"Invalid TSV format in {path} at line {i}")
        item_id, tag, explanation = (part.strip() for part in parts)
        if not item_id:
            raise TagPoolError(f"Empty ID in {path} at line {i}")
        if item_id in seen_ids:
            raise TagPoolError(f"Duplicate ID in {path}: {item_id}")
        if not tag:
            raise TagPoolError(f"Empty tag in {path} at line {i}")
        seen_ids.add(item_id)
        entries.append(ExplainedTagEntry(id=item_id, tag=tag, explanation=explanation))
    return entries


def load_tag_pools(cfg: BenchmarkConfig) -> TagPools:
    ru_plain = _load_plain_pool(cfg.resolve_path(cfg.pools.ru_plain))
    en_plain = _load_plain_pool(cfg.resolve_path(cfg.pools.en_plain))
    ru_explained = _load_explained_pool(cfg.resolve_path(cfg.pools.ru_explained))
    en_explained = _load_explained_pool(cfg.resolve_path(cfg.pools.en_explained))
    return TagPools(
        ru_plain=ru_plain,
        en_plain=en_plain,
        ru_explained=ru_explained,
        en_explained=en_explained,
    )

