from hsmt_engine.extractors import extract_inputs, extract_pdf_with_llm


def test_extract_docx_uses_hsmt_skill(settings, sample_docx):
    extraction, supplements = extract_inputs([sample_docx], settings.root, "Gói kiểm thử")
    assert extraction["items"]
    assert extraction["items"][0]["item_name"] == "Máy in laser"
    assert extraction["project_info"]["package_name"] == "Gói kiểm thử"
    assert supplements == {"pdf_documents": []}


def test_pdf_llm_extraction_has_stable_item_numbers():
    class FakeLLM:
        configured = True

        def json(self, system, prompt, max_tokens=0):
            return {
                "project_info": {"investor": "Test"},
                "general_requirements": [],
                "items": [{
                    "item_no": "9", "item_name": "Printer", "quantity": 1,
                    "unit": "piece", "category": "printer", "search_keywords": ["printer"],
                    "match_priority": "high", "components": [{
                        "component_name": "main", "requirements": [{
                            "raw_text": "Speed >= 30 ppm", "field": "speed", "operator": ">=",
                            "value": "30", "unit": "ppm", "critical": True,
                            "weight": 10, "confidence": "high",
                        }],
                    }],
                }],
                "validation_warnings": [],
            }

    result = extract_pdf_with_llm(
        [{"file": "input.pdf", "text": "item text", "warnings": ["check glyph"]}],
        FakeLLM(), "PDF package",
    )
    assert result["items"][0]["item_no"] == 1
    assert "check glyph" in result["validation_warnings"]
