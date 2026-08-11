from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import JobRecord, JobStatus, utcnow


class JobStore:
    def __init__(self, database: Path):
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    project_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    current_step TEXT NOT NULL DEFAULT '',
                    error TEXT,
                    workspace TEXT NOT NULL,
                    input_files TEXT NOT NULL DEFAULT '[]',
                    artifacts TEXT NOT NULL DEFAULT '{}',
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> JobRecord:
        data = dict(row)
        for key in ("input_files", "artifacts", "metadata"):
            data[key] = json.loads(data[key])
        return JobRecord.model_validate(data)

    def create(self, record: JobRecord) -> JobRecord:
        data = record.model_dump(mode="json")
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO jobs
                (id,status,project_name,created_at,updated_at,progress,current_step,error,workspace,input_files,artifacts,metadata)
                VALUES (:id,:status,:project_name,:created_at,:updated_at,:progress,:current_step,:error,:workspace,:input_files,:artifacts,:metadata)""",
                {**data,
                 "input_files": json.dumps(data["input_files"], ensure_ascii=False),
                 "artifacts": json.dumps(data["artifacts"], ensure_ascii=False),
                 "metadata": json.dumps(data["metadata"], ensure_ascii=False)},
            )
            self._event(conn, record.id, "created", {"status": record.status})
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._decode(row) if row else None

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        current = self.get(job_id)
        if not current:
            raise KeyError(job_id)
        data = current.model_dump(mode="json")
        data.update(changes)
        data["updated_at"] = utcnow()
        updated = JobRecord.model_validate(data)
        encoded = updated.model_dump(mode="json")
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE jobs SET status=:status,project_name=:project_name,updated_at=:updated_at,
                progress=:progress,current_step=:current_step,error=:error,workspace=:workspace,
                input_files=:input_files,artifacts=:artifacts,metadata=:metadata WHERE id=:id""",
                {**encoded,
                 "input_files": json.dumps(encoded["input_files"], ensure_ascii=False),
                 "artifacts": json.dumps(encoded["artifacts"], ensure_ascii=False),
                 "metadata": json.dumps(encoded["metadata"], ensure_ascii=False)},
            )
            self._event(conn, job_id, "updated", changes)
        return updated

    def list_by_status(self, statuses: list[JobStatus]) -> list[JobRecord]:
        if not statuses:
            return []
        marks = ",".join("?" for _ in statuses)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs WHERE status IN ({marks}) ORDER BY created_at",
                [s.value for s in statuses],
            ).fetchall()
        return [self._decode(r) for r in rows]

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT seq,created_at,kind,payload FROM events WHERE job_id=? ORDER BY seq", (job_id,)
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    @staticmethod
    def _event(conn: sqlite3.Connection, job_id: str, kind: str, payload: Any) -> None:
        conn.execute(
            "INSERT INTO events(job_id,created_at,kind,payload) VALUES (?,?,?,?)",
            (job_id, utcnow(), kind, json.dumps(payload, ensure_ascii=False, default=str)),
        )
