from __future__ import annotations

from typing import Any

import httpx


class ResearchClient:
    def __init__(self, api_key: str | None, result_count: int = 5):
        self.api_key = api_key
        self.result_count = result_count

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, domains: list[str] | None = None) -> list[dict[str, Any]]:
        if not self.api_key:
            return []
        payload: dict[str, Any] = {
            "query": query,
            "numResults": self.result_count,
            "type": "auto",
            "contents": {"highlights": True, "summary": True},
        }
        if domains:
            payload["includeDomains"] = domains
        with httpx.Client(timeout=45) as client:
            response = client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
        output = []
        for row in response.json().get("results", []):
            output.append({
                "title": row.get("title") or "",
                "url": row.get("url") or "",
                "published": row.get("publishedDate") or "",
                "snippet": row.get("summary") or " ... ".join(row.get("highlights") or []),
            })
        return output


def build_queries(item: dict[str, Any]) -> list[str]:
    name = item.get("item_name", "")
    keywords = item.get("search_keywords") or []
    requirements = []
    for component in item.get("components", []):
        for req in component.get("requirements", []):
            if req.get("critical") or req.get("weight", 0) >= 8:
                requirements.append(req.get("raw_text") or req.get("field", ""))
    fingerprint = " ".join(str(x) for x in requirements[:4])[:500]
    queries = [f'"{name}" {fingerprint} datasheet model']
    queries.extend(f"{name} {keyword} datasheet" for keyword in keywords[:2])
    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))
