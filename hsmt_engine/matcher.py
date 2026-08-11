from __future__ import annotations

import json
from datetime import date
from typing import Any

from .llm import LLMClient


SYSTEM = """You are an HSMT product compliance analyst. Return JSON only. Never invent a model,
specification, quote, URL, certificate, or compliance status. Official manufacturer datasheets have
priority. A requirement is compliant only when the supplied evidence directly supports it. Use
'Cần xác minh' when evidence is missing or ambiguous."""


def _requirements(item: dict[str, Any]) -> list[str]:
    rows = []
    for component in item.get("components", []):
        for requirement in component.get("requirements", []):
            rows.append(requirement.get("raw_text") or "")
    return [row for row in rows if row]


def provisional_item(item: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = sources[0]["title"] if sources else ""
    return {
        "candidate": candidate,
        "dat": 0,
        "khong_dat": 0,
        "xac_minh": len(_requirements(item)),
        "status": "Cần xác minh",
        "note": "Chưa cấu hình model đối chiếu; các nguồn tìm được chỉ là ứng viên.",
        "spec_rows": [
            [str(item.get("item_no", "")), req, candidate, "", "Cần xác minh", "", ""]
            for req in _requirements(item)
        ],
    }


def match_item(item: dict[str, Any], sources: list[dict[str, Any]], llm: LLMClient) -> dict[str, Any]:
    if not llm.configured:
        return provisional_item(item, sources)
    prompt = json.dumps(
        {"item": item, "candidate_sources": sources, "required_output": {
            "candidate": "exact manufacturer + model or empty",
            "dat": "integer", "khong_dat": "integer", "xac_minh": "integer",
            "status": "Đạt|Không đạt|Cần xác minh",
            "note": "short Vietnamese explanation",
            "spec_rows": [["item", "requirement", "model", "actual", "status", "verbatim evidence", "source URL"]],
            "alternatives": [["item", "option", "model", "technical note", "URL", "reference price"]],
        }}, ensure_ascii=False
    )
    result = llm.json(SYSTEM, prompt)
    for row in result.get("spec_rows", []):
        if len(row) >= 7 and row[4] == "Đạt" and not row[6]:
            row[4] = "Cần xác minh"
    return result


def compile_results(extraction: dict[str, Any], matches: dict[str, dict[str, Any]], sources: dict[str, Any]) -> dict[str, Any]:
    spec_rows, alternatives, traced = [], [], []
    for item in extraction.get("items", []):
        number = str(item.get("item_no"))
        result = matches[number]
        spec_rows.extend(result.get("spec_rows", []))
        alternatives.extend(result.get("alternatives", []))
        traced.append([number, result.get("candidate", ""), " / ".join(build_fingerprint(item)), result.get("status", "")])
    needs_review = sum(1 for row in matches.values() if row.get("status") != "Đạt")
    return {
        "meta": {
            "analysis_date": date.today().isoformat(),
            "coverage_note": f"{len(matches)} hạng mục; {needs_review} hạng mục cần xem lại.",
            "human_review_required": True,
        },
        "items": matches,
        "spec_rows": spec_rows,
        "alternatives": alternatives,
        "traced_models": traced,
        "analysis_sections": [["Kiểm soát chất lượng", [
            "Mọi kết luận Đạt phải có URL và bằng chứng trích dẫn.",
            "Các dòng Cần xác minh phải được duyệt trước khi xuất bản chính thức.",
        ]]],
        "summary": [["Phạm vi", f"Đã xử lý {len(matches)} hạng mục"], ["Cần duyệt", str(needs_review)]],
        "source_index": sources,
    }


def build_fingerprint(item: dict[str, Any]) -> list[str]:
    rows = _requirements(item)
    return rows[:3]
