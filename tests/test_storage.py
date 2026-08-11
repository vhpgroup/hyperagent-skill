from hsmt_engine.models import JobRecord, JobStatus, utcnow
from hsmt_engine.storage import JobStore


def test_job_store_round_trip(settings, tmp_path):
    store = JobStore(settings.database)
    now = utcnow()
    record = JobRecord(
        id="job-1", status=JobStatus.queued, created_at=now, updated_at=now,
        workspace=str(tmp_path), input_files=["input.docx"], metadata={"attempt": 1},
    )
    store.create(record)
    updated = store.update("job-1", status=JobStatus.extracting, progress=10)
    assert updated.status == JobStatus.extracting
    assert store.get("job-1").input_files == ["input.docx"]
    assert len(store.events("job-1")) == 2
