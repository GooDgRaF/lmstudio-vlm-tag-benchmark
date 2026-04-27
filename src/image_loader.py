from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import BenchmarkConfig


class ImageDiscoveryError(RuntimeError):
    """Image discovery error."""


@dataclass(frozen=True)
class DiscoveredImage:
    image_id: str
    image_path: str
    image_rel_path: str


def _safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "image"


def build_image_id(image_rel_path: str) -> str:
    rel = image_rel_path.replace("\\", "/")
    base = _safe_slug(Path(rel).stem)
    short_hash = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]
    return f"{base}_{short_hash}"


def discover_images(cfg: BenchmarkConfig, limit: int | None = None) -> list[DiscoveredImage]:
    image_dir = cfg.resolve_path(cfg.input.image_dir)
    if not image_dir.exists():
        raise ImageDiscoveryError(f"Input image directory does not exist: {cfg.input.image_dir}")
    if not image_dir.is_dir():
        raise ImageDiscoveryError(f"Input image path is not a directory: {cfg.input.image_dir}")

    extensions = {ext.lower() for ext in cfg.input.extensions}
    pattern = "**/*" if cfg.input.recursive else "*"
    paths = [
        path
        for path in image_dir.glob(pattern)
        if path.is_file() and path.suffix.lower() in extensions
    ]
    paths.sort(key=lambda p: str(p.relative_to(image_dir)).lower())

    if limit is None and cfg.limits.limit_images is not None:
        limit = cfg.limits.limit_images
    if limit is not None:
        paths = paths[:limit]

    discovered: list[DiscoveredImage] = []
    for path in paths:
        rel = path.relative_to(image_dir).as_posix()
        discovered.append(
            DiscoveredImage(
                image_id=build_image_id(rel),
                image_path=str(path.resolve()),
                image_rel_path=rel,
            )
        )
    return discovered

