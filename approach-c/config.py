"""Centralized configuration for the FAQ backend."""

from __future__ import annotations

from pathlib import Path

import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT: Path = Path(__file__).resolve().parent
DATA_DIR: Path = PROJECT_ROOT / "data"

DEFAULT_FAQ_PATH: Path = DATA_DIR / "faq.json"

BACKUP_MODEL: str = os.getenv("BACKUP_MODEL", "")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", BACKUP_MODEL)

HF_API_TOKEN: str = os.getenv("HF_API_TOKEN", "")

INFERENCE_TIMEOUT: int = int(os.getenv("INFERENCE_TIMEOUT", "30"))
LLM_MAX_NEW_TOKENS: int = int(os.getenv("LLM_MAX_NEW_TOKENS", "512"))
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

def resolve_path(path_like: str | Path, base_dir: Path | None = None) -> Path:
    path = Path(path_like).expanduser()
    if path.is_absolute():
        return path.resolve()
    if base_dir is not None:
        return (base_dir / path).resolve()
    return (PROJECT_ROOT / path).resolve()