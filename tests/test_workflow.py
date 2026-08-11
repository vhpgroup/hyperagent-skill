from pathlib import Path

from hsmt_engine.models import JobRecord, JobStatus, utcnow
from hsmt_engine.storage import JobStore
from hsmt_engine.workflow import HSMTWorkflow


def test_workflow_pauses_for_review_then_exports(settings, sample_docx, tmp_path):
    workspace = settings.data_dir / "jobs" / "job-flow"
    workspace.mkdir(parents=True)
    target = workspace / sample_docx.name
    target.write_bytes(sample_docx.read_bytes())
    store = JobStore(settings.database)
    now = utcnow()
    store.create(JobRecord(
        id="job-flow", status=JobStatus.queued, created_at=now, updated_at=now,
        workspace=str(workspace), input_files=[target.name], metadata={"attempt": 1},
    ))
    workflow = HSMTWorkflow(settings, store)
    workflow.start("job-flow")
    waiting = store.get("job-flow")
    assert waiting.status == JobStatus.awaiting_review
    assert (workspace / "results.json").is_file()

    workflow.resume("job-flow", "approve", "reviewed in test")
    completed = store.get("job-flow")
    assert completed.status == JobStatus.completed
    assert Path(completed.workspace, completed.artifacts["excel"]).is_file()
