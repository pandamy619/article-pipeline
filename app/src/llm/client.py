"""Клиент к локальной Ollama (HTTP API)."""

from __future__ import annotations

import re

import httpx

from src.config import settings


class OllamaClient:
    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        think: bool = False,
        num_predict: int = 400,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.host = (host or settings.ollama_host).rstrip("/")
        self.model = model or settings.llm_model
        self.think = think
        self.num_predict = num_predict
        self._client = httpx.Client(
            base_url=self.host, timeout=timeout, transport=transport
        )

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        format: str | None = None,
        options: dict | None = None,
    ) -> str:
        opts: dict = {"num_predict": self.num_predict}
        if options:
            opts.update(options)
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": self.think,
            "options": opts,
        }
        if system:
            payload["system"] = system
        if format:
            payload["format"] = format
        resp = self._client.post("/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")

    def chat(self, messages: list[dict], *, format: str | None = None) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "options": {"num_predict": self.num_predict},
        }
        if format:
            payload["format"] = format
        resp = self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "")
        return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        resp = self._client.post(
            "/api/embeddings",
            json={"model": model or settings.embed_model, "prompt": text},
        )
        resp.raise_for_status()
        return resp.json().get("embedding", [])
