"""Utility module for loading and indexing exam question sets."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Tuple

# Regular expression for allowed slug names
_SLUG_RE = re.compile(r"^[a-z0-9_\-]+$")


class ExamMeta(TypedDict):
    mode: str
    category: str
    slug: str
    path: Path
    title: str
    num_questions: int
    time_per_question_sec: int


_INDEX: Dict[str, ExamMeta] = {}
_CACHE: Dict[str, Tuple[float, dict]] = {}


def get_data_root() -> Path:
    """Return the root directory containing exam JSON files."""
    env = os.environ.get("EXAM_DATA_DIR")
    if env:
        return Path(env)
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root / "exams",
        repo_root / "spi_exam_flask_app" / "data" / "exams",
    ]
    for path in candidates:
        if path.exists():
            return path
    return Path(__file__).parent / "data" / "exams"


def _validate_question(question: dict) -> bool:
    if not isinstance(question, dict):
        return False
    if "options" not in question or "answer_index" not in question or "prompt_html" not in question:
        return False
    options = question.get("options")
    if not isinstance(options, list) or len(options) < 2:
        return False
    ai = question.get("answer_index")
    if not isinstance(ai, int) or not (0 <= ai < len(options)):
        return False
    return True


def _validate_exam(data: dict, mode: str, category: str, slug: str) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("version") != 1:
        return False
    if data.get("mode") != mode or data.get("category") != category or data.get("slug") != slug:
        return False
    if not isinstance(data.get("title"), str) or not data["title"]:
        return False
    if not isinstance(data.get("description"), str):
        return False
    t = data.get("time_per_question_sec")
    if not isinstance(t, int) or not (1 <= t <= 600):
        return False
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        return False
    for q in questions:
        if not _validate_question(q):
            return False
    return True


def build_index() -> Dict[str, ExamMeta]:
    """Scan the data directory and build an index of available exam sets."""
    root = get_data_root()
    index: Dict[str, ExamMeta] = {}
    if not root.exists():
        return index
    for mode_dir in root.iterdir():
        if not mode_dir.is_dir():
            continue
        mode = mode_dir.name
        for cat_dir in mode_dir.iterdir():
            if not cat_dir.is_dir():
                continue
            category = cat_dir.name
            for json_file in cat_dir.glob("*.json"):
                slug = json_file.stem
                try:
                    with json_file.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue
                if not _validate_exam(data, mode, category, slug):
                    continue
                index[slug] = ExamMeta(
                    mode=mode,
                    category=category,
                    slug=slug,
                    path=json_file,
                    title=data["title"],
                    num_questions=len(data["questions"]),
                    time_per_question_sec=data["time_per_question_sec"],
                )
    global _INDEX
    _INDEX = index
    return index


def list_modes(index: Dict[str, ExamMeta]) -> List[str]:
    return sorted({meta["mode"] for meta in index.values()})


def list_categories(index: Dict[str, ExamMeta], mode: str) -> List[str]:
    return sorted({meta["category"] for meta in index.values() if meta["mode"] == mode})


def list_sets(index: Dict[str, ExamMeta], mode: str, category: str) -> List[ExamMeta]:
    return sorted(
        [meta for meta in index.values() if meta["mode"] == mode and meta["category"] == category],
        key=lambda m: m["slug"],
    )


def load_set(slug: str) -> dict:
    """Load a question set by slug.  Results are cached based on mtime."""
    if not _SLUG_RE.match(slug):
        raise ValueError("invalid slug")
    meta = _INDEX.get(slug)
    if not meta:
        raise KeyError(slug)
    path = meta["path"]
    mtime = path.stat().st_mtime
    cached = _CACHE.get(slug)
    if cached and cached[0] >= mtime:
        return cached[1]
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not _validate_exam(data, meta["mode"], meta["category"], meta["slug"]):
        raise ValueError("invalid exam data")
    _CACHE[slug] = (mtime, data)
    return data

