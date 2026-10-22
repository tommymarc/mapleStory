"""Import official monster image resources without altering image data."""

from dataclasses import dataclass
import os
import re
import shutil
import zipfile


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
DEATH_FRAME_PATTERN = re.compile(
    r"(^|[_-])(die|dead|death)\d*($|[_-])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MonsterImportResult:
    imported_paths: tuple[str, ...]
    skipped_death_frames: int


def is_death_frame(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    return DEATH_FRAME_PATTERN.search(stem) is not None


def safe_filename_stem(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff-]+", "_", stem).strip("_")
    if stem in ("", ".", ".."):
        raise ValueError(f"Invalid monster image filename: {filename}")
    return stem


def unique_image_path(directory, filename):
    extension = os.path.splitext(filename)[1].lower()
    stem = safe_filename_stem(filename)
    candidate = os.path.join(directory, f"{stem}{extension}")
    suffix = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{stem}_{suffix}{extension}")
        suffix += 1
    return candidate


def import_monster_images(source_paths, target_dir):
    """Copy supported images from files or ZIP archives into a monster folder."""
    os.makedirs(target_dir, exist_ok=True)
    imported_paths = []
    skipped_death_frames = 0

    for source_path in source_paths:
        if source_path.lower().endswith(".zip"):
            with zipfile.ZipFile(source_path) as archive:
                for info in archive.infolist():
                    filename = os.path.basename(info.filename)
                    extension = os.path.splitext(filename)[1].lower()
                    if info.is_dir() or extension not in IMAGE_EXTENSIONS:
                        continue
                    if is_death_frame(filename):
                        skipped_death_frames += 1
                        continue
                    target_path = unique_image_path(target_dir, filename)
                    with archive.open(info) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    imported_paths.append(target_path)
            continue

        extension = os.path.splitext(source_path)[1].lower()
        if extension not in IMAGE_EXTENSIONS:
            continue
        filename = os.path.basename(source_path)
        if is_death_frame(filename):
            skipped_death_frames += 1
            continue
        target_path = unique_image_path(target_dir, filename)
        shutil.copy2(source_path, target_path)
        imported_paths.append(target_path)

    if not imported_paths:
        raise ValueError("没有找到可导入的怪物图片")

    return MonsterImportResult(
        imported_paths=tuple(imported_paths),
        skipped_death_frames=skipped_death_frames,
    )
