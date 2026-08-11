from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    queued = "queued"
    extracting = "extracting"
    researching = "researching"
    matching = "matching"
    verifying = "verifying"
    awaiting_review = "awaiting_review"
    exporting = "exporting"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"


class JobRecord(BaseModel):
    id: str
    status: JobStatus
    project_name: str = ""
    created_at: str
    updated_at: str
    progress: int = 0
    current_step: str = ""
    error: str | None = None
    workspace: str
    input_files: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = ""
    results: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    exa_configured: bool
    llm_configured: bool
