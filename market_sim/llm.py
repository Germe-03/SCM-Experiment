"""Phase 12: a thin client for a local Ollama model and a fake model for tests."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


class OllamaClient:
    """Calls the local Ollama HTTP API; no data leaves the machine."""

    def __init__(self, model: str, host: str = "http://localhost:11434", timeout: float = 180.0,
                 temperature: float = 0.3, max_tokens: int = 400) -> None:
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout
        self.temperature, self.max_tokens = temperature, max_tokens

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5) as response:
                names = [m.get("name") for m in json.load(response).get("models", [])]
            return self.model in names
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def generate(self, system: str, prompt: str) -> str:
        body = json.dumps({
            "model": self.model, "system": system, "prompt": prompt, "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }).encode("utf-8")
        request = urllib.request.Request(f"{self.host}/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response).get("response", "").strip()


class FakeLLM:
    """Deterministic stand-in: repeats the facts it was given (used in tests)."""

    def available(self) -> bool:
        return True

    def generate(self, system: str, prompt: str) -> str:
        facts = prompt.split("FAKTEN:", 1)[-1].strip().splitlines()
        return " ".join(line.strip("- ").strip() for line in facts[:4] if line.strip())


_NUMBER = re.compile(r"(?<![\w.])-?\d[\d']*(?:[.,]\d+)?")


def numbers_in(text: str) -> list[float]:
    values = []
    for raw in _NUMBER.findall(text):
        cleaned = raw.replace("'", "").replace(",", ".")
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values


def unchecked_numbers(text: str, facts: str, tolerance: float = 0.02) -> list[float]:
    """Numbers in the text that do not appear in the facts (small integers like years 1-3 are allowed)."""
    known = numbers_in(facts)
    bad = []
    for value in numbers_in(text):
        if abs(value) <= 3 and float(value).is_integer():
            continue
        if not any(abs(value - k) <= max(tolerance * abs(k), 0.051) for k in known):
            bad.append(value)
    return bad
