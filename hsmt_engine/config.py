from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    root: Path
    data_dir: Path
    database: Path
    api_token: str
    api_host: str
    api_port: int
    max_upload_mb: int
    exa_api_key: str | None
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str | None
    research_results: int

    @classmethod
    def load(cls) -> "Settings":
        root = Path(os.getenv("HSMT_ENGINE_ROOT", Path(__file__).resolve().parents[1])).resolve()
        data_dir = Path(os.getenv("HSMT_DATA_DIR", root / "var" / "hsmt-engine")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        token = os.getenv("HSMT_API_TOKEN", "").strip()
        if not token:
            token = secrets.token_urlsafe(32)
        return cls(
            root=root,
            data_dir=data_dir,
            database=Path(os.getenv("HSMT_DATABASE", data_dir / "jobs.sqlite3")).resolve(),
            api_token=token,
            api_host=os.getenv("HSMT_API_HOST", "127.0.0.1"),
            api_port=_int("HSMT_API_PORT", 8787),
            max_upload_mb=_int("HSMT_MAX_UPLOAD_MB", 100),
            exa_api_key=os.getenv("EXA_API_KEY") or None,
            llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None,
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_model=os.getenv("LLM_MODEL") or None,
            research_results=_int("HSMT_RESEARCH_RESULTS", 5),
        )
