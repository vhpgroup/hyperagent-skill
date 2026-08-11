from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import __version__
from .config import Settings
from .models import HealthResponse, JobRecord, JobStatus, ReviewRequest, utcnow
from .storage import JobStore
from .workflow import HSMTWorkflow


SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = JobStore(settings.database)
        self.workflow = HSMTWorkflow(settings, self.store)
        self.queue: asyncio.Queue[tuple[str, str, dict[str, Any]]] = asyncio.Queue()
        self.worker: asyncio.Task | None = None

    async def run_worker(self) -> None:
        while True:
            action, job_id, payload = await self.queue.get()
            try:
                if action == "start":
                    await asyncio.to_thread(self.workflow.start, job_id)
                else:
                    await asyncio.to_thread(
                        self.workflow.resume, job_id, payload["decision"], payload.get("note", "")
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.store.update(
                    job_id, status=JobStatus.failed, current_step="failed", error=str(exc)
                )
            finally:
                self.queue.task_done()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    runtime = Runtime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime.worker = asyncio.create_task(runtime.run_worker())
        for job in runtime.store.list_by_status([
            JobStatus.queued, JobStatus.extracting, JobStatus.researching,
            JobStatus.matching, JobStatus.verifying, JobStatus.exporting,
        ]):
            attempt = int(job.metadata.get("attempt", 1)) + 1
            runtime.store.update(
                job.id, status=JobStatus.queued, current_step="recovered",
                metadata={**job.metadata, "attempt": attempt}, error=None,
            )
            await runtime.queue.put(("start", job.id, {}))
        yield
        if runtime.worker:
            runtime.worker.cancel()
            try:
                await runtime.worker
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title="HSMT Product Matcher Engine", version=__version__, lifespan=lifespan,
        description="Durable extraction, research, matching, human review, and Excel export API.",
    )
    app.state.runtime = runtime

    def authorize(authorization: str | None = Header(default=None)) -> None:
        if authorization != f"Bearer {settings.api_token}":
            raise HTTPException(status_code=401, detail="Invalid bearer token")

    def require_job(job_id: str) -> JobRecord:
        job = runtime.store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok", version=__version__, database=str(settings.database),
            exa_configured=bool(settings.exa_api_key),
            llm_configured=bool(settings.llm_api_key and settings.llm_model),
        )

    @app.post("/v1/jobs", response_model=JobRecord, dependencies=[Depends(authorize)])
    async def create_job(
        files: list[UploadFile] = File(...),
        project_name: str = Form(default=""),
        metadata: str = Form(default="{}"),
    ) -> JobRecord:
        try:
            parsed_metadata = json.loads(metadata)
            if not isinstance(parsed_metadata, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=422, detail="metadata must be a JSON object")
        job_id = uuid.uuid4().hex
        workspace = settings.data_dir / "jobs" / job_id
        workspace.mkdir(parents=True, exist_ok=False)
        saved: list[str] = []
        total = 0
        limit = settings.max_upload_mb * 1024 * 1024
        try:
            for upload in files:
                name = SAFE_NAME.sub("_", Path(upload.filename or "upload").name).strip("._")
                if not name or Path(name).suffix.lower() not in {".docx", ".pdf"}:
                    raise HTTPException(status_code=415, detail=f"Unsupported file: {upload.filename}")
                target = workspace / name
                with target.open("wb") as stream:
                    while chunk := await upload.read(1024 * 1024):
                        total += len(chunk)
                        if total > limit:
                            raise HTTPException(status_code=413, detail="Upload too large")
                        stream.write(chunk)
                saved.append(name)
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise
        now = utcnow()
        job = runtime.store.create(JobRecord(
            id=job_id, status=JobStatus.queued, project_name=project_name,
            created_at=now, updated_at=now, workspace=str(workspace), input_files=saved,
            metadata={**parsed_metadata, "attempt": 1}, current_step="queued",
        ))
        await runtime.queue.put(("start", job_id, {}))
        return job

    @app.get("/v1/jobs/{job_id}", response_model=JobRecord, dependencies=[Depends(authorize)])
    def get_job(job_id: str) -> JobRecord:
        return require_job(job_id)

    @app.get("/v1/jobs/{job_id}/events", dependencies=[Depends(authorize)])
    def get_events(job_id: str) -> list[dict[str, Any]]:
        require_job(job_id)
        return runtime.store.events(job_id)

    @app.post("/v1/jobs/{job_id}/review", response_model=JobRecord, dependencies=[Depends(authorize)])
    async def review(job_id: str, body: ReviewRequest) -> JobRecord:
        job = require_job(job_id)
        if job.status != JobStatus.awaiting_review:
            raise HTTPException(status_code=409, detail="Job is not awaiting review")
        if body.results is not None:
            results_name = job.artifacts.get("results", "results.json")
            (Path(job.workspace) / results_name).write_text(
                json.dumps(body.results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        await runtime.queue.put(("resume", job_id, {"decision": body.decision, "note": body.note}))
        return job

    @app.post("/v1/jobs/{job_id}/retry", response_model=JobRecord, dependencies=[Depends(authorize)])
    async def retry(job_id: str) -> JobRecord:
        job = require_job(job_id)
        if job.status not in {JobStatus.failed, JobStatus.rejected}:
            raise HTTPException(status_code=409, detail="Only failed or rejected jobs can be retried")
        updated = runtime.store.update(
            job_id, status=JobStatus.queued, progress=0, current_step="queued", error=None,
            metadata={**job.metadata, "attempt": int(job.metadata.get("attempt", 1)) + 1},
        )
        await runtime.queue.put(("start", job_id, {}))
        return updated

    @app.get("/v1/jobs/{job_id}/artifacts/{artifact}", dependencies=[Depends(authorize)])
    def artifact(job_id: str, artifact: str):
        job = require_job(job_id)
        filename = job.artifacts.get(artifact)
        if not filename:
            raise HTTPException(status_code=404, detail="Artifact not found")
        path = (Path(job.workspace) / filename).resolve()
        if path.parent != Path(job.workspace).resolve() or not path.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path, filename=path.name)

    return app


app = create_app()
