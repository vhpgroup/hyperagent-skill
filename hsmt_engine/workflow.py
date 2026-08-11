from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .config import Settings
from .extractors import extract_inputs, extract_pdf_with_llm, write_json
from .llm import LLMClient
from .matcher import compile_results, match_item
from .models import JobStatus
from .research import ResearchClient, build_queries
from .storage import JobStore


class WorkflowState(TypedDict, total=False):
    job_id: str
    review_decision: str
    review_note: str


class HSMTWorkflow:
    def __init__(self, settings: Settings, store: JobStore):
        self.settings = settings
        self.store = store
        self.research = ResearchClient(settings.exa_api_key, settings.research_results)
        self.llm = LLMClient(settings.llm_api_key, settings.llm_base_url, settings.llm_model)
        checkpoint_db = settings.data_dir / "checkpoints.sqlite3"
        self._checkpoint_connection = sqlite3.connect(checkpoint_db, check_same_thread=False)
        self.checkpointer = SqliteSaver(self._checkpoint_connection)
        self.graph = self._build()

    def _build(self):
        builder = StateGraph(WorkflowState)
        builder.add_node("extract", self._extract)
        builder.add_node("research", self._research)
        builder.add_node("match", self._match)
        builder.add_node("verify", self._verify)
        builder.add_node("review", self._review)
        builder.add_node("export", self._export)
        builder.add_node("reject", self._reject)
        builder.add_edge(START, "extract")
        builder.add_edge("extract", "research")
        builder.add_edge("research", "match")
        builder.add_edge("match", "verify")
        builder.add_edge("verify", "review")
        builder.add_conditional_edges(
            "review", lambda state: state.get("review_decision", "reject"),
            {"approve": "export", "reject": "reject"},
        )
        builder.add_edge("export", END)
        builder.add_edge("reject", END)
        return builder.compile(checkpointer=self.checkpointer)

    def _job_paths(self, job_id: str) -> tuple[Any, Path]:
        job = self.store.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job, Path(job.workspace)

    def _extract(self, state: WorkflowState) -> WorkflowState:
        job, workspace = self._job_paths(state["job_id"])
        self.store.update(job.id, status=JobStatus.extracting, progress=10, current_step="extract")
        files = [workspace / name for name in job.input_files]
        extraction, supplements = extract_inputs(files, self.settings.root, job.project_name)
        if not extraction.get("items") and supplements.get("pdf_documents"):
            extraction = extract_pdf_with_llm(
                supplements["pdf_documents"], self.llm, job.project_name
            )
        extraction_path = workspace / "extraction.json"
        supplements_path = workspace / "supplements.json"
        write_json(extraction_path, extraction)
        write_json(supplements_path, supplements)
        self.store.update(job.id, artifacts={
            **job.artifacts, "extraction": extraction_path.name, "supplements": supplements_path.name,
        }, progress=25)
        return state

    def _research(self, state: WorkflowState) -> WorkflowState:
        job, workspace = self._job_paths(state["job_id"])
        self.store.update(job.id, status=JobStatus.researching, progress=30, current_step="research")
        extraction = json.loads((workspace / "extraction.json").read_text(encoding="utf-8"))
        source_index: dict[str, Any] = {}
        items = extraction.get("items", [])
        for position, item in enumerate(items, 1):
            number = str(item.get("item_no"))
            rows: list[dict[str, Any]] = []
            seen: set[str] = set()
            for query in build_queries(item):
                for result in self.research.search(query):
                    if result["url"] and result["url"] not in seen:
                        result["query"] = query
                        rows.append(result)
                        seen.add(result["url"])
            source_index[number] = rows
            progress = 30 + int(25 * position / max(1, len(items)))
            self.store.update(job.id, progress=progress, current_step=f"research:{number}")
        path = workspace / "sources.json"
        write_json(path, source_index)
        current = self.store.get(job.id)
        self.store.update(job.id, artifacts={**current.artifacts, "sources": path.name})
        return state

    def _match(self, state: WorkflowState) -> WorkflowState:
        job, workspace = self._job_paths(state["job_id"])
        self.store.update(job.id, status=JobStatus.matching, progress=58, current_step="match")
        extraction = json.loads((workspace / "extraction.json").read_text(encoding="utf-8"))
        sources = json.loads((workspace / "sources.json").read_text(encoding="utf-8"))
        matches: dict[str, Any] = {}
        items = extraction.get("items", [])
        for position, item in enumerate(items, 1):
            number = str(item.get("item_no"))
            matches[number] = match_item(item, sources.get(number, []), self.llm)
            progress = 58 + int(22 * position / max(1, len(items)))
            self.store.update(job.id, progress=progress, current_step=f"match:{number}")
        results = compile_results(extraction, matches, sources)
        path = workspace / "results.json"
        write_json(path, results)
        current = self.store.get(job.id)
        self.store.update(job.id, artifacts={**current.artifacts, "results": path.name})
        return state

    def _verify(self, state: WorkflowState) -> WorkflowState:
        job, workspace = self._job_paths(state["job_id"])
        self.store.update(job.id, status=JobStatus.verifying, progress=82, current_step="verify")
        path = workspace / "results.json"
        results = json.loads(path.read_text(encoding="utf-8"))
        downgraded = 0
        for row in results.get("spec_rows", []):
            if len(row) >= 7 and str(row[4]).lower() in {"đạt", "dat"} and not row[6]:
                row[4] = "Cần xác minh"
                downgraded += 1
        results.setdefault("meta", {})["verification_downgrades"] = downgraded
        write_json(path, results)
        self.store.update(
            job.id, status=JobStatus.awaiting_review, progress=90,
            current_step="human_review", error=None,
        )
        return state

    def _review(self, state: WorkflowState) -> WorkflowState:
        decision = interrupt({
            "job_id": state["job_id"],
            "message": "Review results.json, then approve or reject the job.",
        })
        return {
            **state,
            "review_decision": decision.get("decision", "reject"),
            "review_note": decision.get("note", ""),
        }

    def _export(self, state: WorkflowState) -> WorkflowState:
        job, workspace = self._job_paths(state["job_id"])
        self.store.update(job.id, status=JobStatus.exporting, progress=94, current_step="export")
        output = workspace / "HSMT_KetQua_PhanTich.xlsx"
        script = self.settings.root / "skills" / "hsmt-analyzer" / "scripts" / "hsmt_excel.py"
        subprocess.run(
            [sys.executable, str(script), str(workspace / "extraction.json"),
             "--results", str(workspace / "results.json"), "--output", str(output)],
            check=True, cwd=self.settings.root,
        )
        current = self.store.get(job.id)
        metadata = {**current.metadata, "review_note": state.get("review_note", "")}
        self.store.update(
            job.id, status=JobStatus.completed, progress=100, current_step="completed",
            artifacts={**current.artifacts, "excel": output.name}, metadata=metadata,
        )
        return state

    def _reject(self, state: WorkflowState) -> WorkflowState:
        job = self.store.get(state["job_id"])
        if job:
            self.store.update(
                job.id, status=JobStatus.rejected, current_step="rejected",
                metadata={**job.metadata, "review_note": state.get("review_note", "")},
            )
        return state

    def _config(self, job_id: str) -> dict[str, Any]:
        job = self.store.get(job_id)
        attempt = (job.metadata if job else {}).get("attempt", 1)
        return {"configurable": {"thread_id": f"{job_id}:{attempt}"}}

    def start(self, job_id: str) -> None:
        self.graph.invoke({"job_id": job_id}, config=self._config(job_id))

    def resume(self, job_id: str, decision: str, note: str = "") -> None:
        self.graph.invoke(
            Command(resume={"decision": decision, "note": note}),
            config=self._config(job_id),
        )
