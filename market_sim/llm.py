"""Phase 12: thin clients for a language model (local Ollama or an OpenAI-compatible API such as SwissAI) and a fake model for tests."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


def api_key(name: str) -> str:
    """Read an API key from the environment or, on Windows, the user registry."""
    value = os.environ.get(name)
    if value:
        return value
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                return str(winreg.QueryValueEx(key, name)[0])
        except (OSError, ImportError):
            return ""
    return ""


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


class OpenAIClient:
    """Calls an OpenAI-compatible chat API (e.g. SwissAI/CSCS); the key comes from an environment variable."""

    def __init__(self, model: str, base_url: str, key_env: str, timeout: float = 120.0,
                 temperature: float = 0.3, max_tokens: int = 400,
                 requests_per_minute: float = 14.0, reasoning_effort: str = "") -> None:
        self.model, self.base_url, self.key_env = model, base_url.rstrip("/"), key_env
        self.timeout, self.temperature, self.max_tokens = timeout, temperature, max_tokens
        self.requests_per_minute, self.reasoning_effort = requests_per_minute, reasoning_effort
        self._last = 0.0

    def available(self) -> bool:
        key = api_key(self.key_env)
        if not key:
            return False
        request = urllib.request.Request(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.load(response).get("data", [])
            return isinstance(data, list) and any(
                isinstance(entry, dict) and entry.get("id") == self.model for entry in data
            )
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def _wait(self) -> None:
        interval = 60 / self.requests_per_minute
        remaining = interval - (time.monotonic() - self._last)
        if remaining > 0:
            time.sleep(remaining)
        self._last = time.monotonic()

    def generate(self, system: str, prompt: str) -> str:
        key = api_key(self.key_env)
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            # Reasoning models (GLM) otherwise spend the whole token budget on thinking.
            **({"reasoning_effort": self.reasoning_effort} if self.reasoning_effort else {}),
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        for attempt in range(1, 7):
            self._wait()
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    content = json.load(response)["choices"][0]["message"].get("content")
                return re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL).strip()
            except urllib.error.HTTPError as error:
                if (error.code == 429 or error.code >= 500) and attempt < 6:
                    # The API names its wait (up to a minute at 15 requests per minute).
                    retry = error.headers.get("Retry-After") if error.headers else None
                    time.sleep(float(retry) + 1 if retry and retry.isdigit() else 5 * attempt)
                    continue
                raise
        return ""


def make_client(cfg, chat: bool = False):
    if cfg.provider == "api":
        return OpenAIClient(
            cfg.api_chat_model if chat else cfg.api_story_model,
            cfg.api_base_url,
            cfg.api_key_env,
            cfg.timeout_seconds,
            cfg.temperature,
            cfg.max_tokens,
            cfg.requests_per_minute,
            cfg.api_reasoning_effort,
        )
    return OllamaClient(
        cfg.chat_model if chat else cfg.story_model,
        cfg.host,
        cfg.timeout_seconds,
        cfg.temperature,
        cfg.max_tokens,
    )


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
