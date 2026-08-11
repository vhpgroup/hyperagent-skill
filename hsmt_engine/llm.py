from __future__ import annotations

import json
from typing import Any

import httpx


class LLMClient:
    def __init__(self, api_key: str | None, base_url: str, model: str | None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def json(self, system: str, prompt: str, max_tokens: int = 6000) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("LLM_API_KEY and LLM_MODEL are required")
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=180) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return json.loads(content)
