from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any


SUPPORTED = {".docx", ".pdf"}


def _load_hsmt_parser(root: Path):
    path = root / "skills" / "hsmt-analyzer" / "scripts" / "hsmt_extract.py"
    spec = importlib.util.spec_from_file_location("hsmt_skill_extract", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load extractor: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_docx(path: Path, root: Path) -> dict[str, Any]:
    result = _load_hsmt_parser(root).parse(str(path))
    if not result.get("items"):
        raise ValueError(f"No HSMT item table found in {path.name}")
    return result


def read_pdf(path: Path) -> tuple[str, list[str]]:
    import fitz

    document = fitz.open(path)
    pages = [page.get_text("text") for page in document]
    warnings: list[str] = []
    if sum(len(page.strip()) for page in pages) < max(100, len(pages) * 40):
        warnings.append("PDF appears scanned; OCR or a vision-capable model is required.")
    suspect = [i + 1 for i, page in enumerate(pages) if re.search(r"[<>]\s*\d", page)]
    if suspect:
        warnings.append(
            "Visually verify >=/<= glyphs on pages: " + ", ".join(map(str, suspect[:30]))
        )
    return "\n\n".join(f"--- PAGE {i + 1} ---\n{page}" for i, page in enumerate(pages)), warnings


def merge_extractions(parts: list[dict[str, Any]], project_name: str = "") -> dict[str, Any]:
    if not parts:
        return {
            "schema_version": "7",
            "project_info": {"package_name": project_name},
            "general_requirements": [],
            "items": [],
            "quantity_table": [],
            "validation_warnings": [],
        }
    base = parts[0]
    if project_name:
        base.setdefault("project_info", {})["package_name"] = project_name
    for extra in parts[1:]:
        known = {str(item.get("item_no")) for item in base.get("items", [])}
        for item in extra.get("items", []):
            number = str(item.get("item_no"))
            if number in known:
                item["item_no"] = f"{number}.{len(base['items']) + 1}"
            base.setdefault("items", []).append(item)
        base.setdefault("general_requirements", []).extend(extra.get("general_requirements", []))
        base.setdefault("validation_warnings", []).extend(extra.get("validation_warnings", []))
    return base


def extract_inputs(files: list[Path], root: Path, project_name: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    docx_parts: list[dict[str, Any]] = []
    pdf_texts: list[dict[str, Any]] = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED:
            continue
        if suffix == ".docx":
            docx_parts.append(extract_docx(path, root))
        else:
            text, warnings = read_pdf(path)
            pdf_texts.append({"file": path.name, "text": text, "warnings": warnings})
    extraction = merge_extractions(docx_parts, project_name)
    for pdf in pdf_texts:
        extraction.setdefault("validation_warnings", []).extend(pdf["warnings"])
    return extraction, {"pdf_documents": pdf_texts}


PDF_SYSTEM = """You extract Vietnamese HSMT technical requirements from PDF text.
Return JSON only. Preserve exact operators, values, units, quantities, item boundaries,
and original requirement text. Never invent missing fields. Text extraction may map an
underlined >= or <= glyph to > or <, so add a validation warning for every suspicious
comparison instead of silently repairing it."""


def extract_pdf_with_llm(
    pdf_documents: list[dict[str, Any]], llm: Any, project_name: str = ""
) -> dict[str, Any]:
    if not llm.configured:
        raise ValueError(
            "PDF-only HSMT extraction requires LLM_API_KEY and LLM_MODEL; "
            "scanned PDFs additionally require OCR or a vision-capable model."
        )
    output = merge_extractions([], project_name)
    next_number = 1
    for document in pdf_documents:
        text = document.get("text", "")
        chunks = [text[i:i + 45000] for i in range(0, len(text), 43000)] or [""]
        for chunk_index, chunk in enumerate(chunks, 1):
            prompt = json.dumps({
                "file": document.get("file"),
                "chunk": chunk_index,
                "text": chunk,
                "output_schema": {
                    "project_info": {},
                    "general_requirements": ["verbatim requirement"],
                    "items": [{
                        "item_no": "number", "item_name": "exact name",
                        "quantity": "number or null", "unit": "string",
                        "category": "short category", "search_keywords": ["string"],
                        "match_priority": "high|medium|low",
                        "components": [{
                            "component_name": "string",
                            "requirements": [{
                                "raw_text": "verbatim", "field": "normalized field",
                                "operator": ">=|<=|=|range|supports|contains_all",
                                "value": "value or null", "unit": "string",
                                "critical": "boolean", "weight": "1-10",
                                "confidence": "high|medium|low",
                            }],
                        }],
                    }],
                    "validation_warnings": ["string"],
                },
            }, ensure_ascii=False)
            part = llm.json(PDF_SYSTEM, prompt, max_tokens=8000)
            output["project_info"].update({
                key: value for key, value in part.get("project_info", {}).items() if value
            })
            output["general_requirements"].extend(part.get("general_requirements", []))
            output["validation_warnings"].extend(part.get("validation_warnings", []))
            for item in part.get("items", []):
                item["item_no"] = next_number
                next_number += 1
                output["items"].append(item)
        output["validation_warnings"].extend(document.get("warnings", []))
    if not output["items"]:
        raise ValueError("The model found no HSMT line items in the supplied PDF")
    return output


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
