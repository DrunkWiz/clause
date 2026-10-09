"""Model providers and the fallback chain. Stdlib only (urllib).

Chain: Gemini Flash -> Featherless -> recorded responses. Each rung returns
JSON text; the chain parses it, checks its shape with the task's validator,
and moves to the next rung on any failure. The recorded rung replays saved
responses for the bundled demo cases, so the live demo still works when a
quota runs out; results say which rung answered.

Keys are read from the environment (.env on the server). They never leave the
backend.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
RECORDED_DIR = ROOT / "data" / "recorded"


class ProviderError(Exception):
    pass


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=value lines into os.environ without overriding what is set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$", line)
        if m and not line.lstrip().startswith("#"):
            os.environ.setdefault(m.group(1), m.group(2).strip().strip("\"'"))


RETRY_STATUS = (429, 500, 502, 503, 504)
RETRY_WAITS = (2.0, 6.0)  # seconds before the 2nd and 3rd tries


def _post_json(url: str, body: dict, headers: dict, timeout: float, waits=RETRY_WAITS) -> dict:
    """POST with short retries on overload or rate-limit errors, then give
    up so the chain can move to the next provider."""
    for wait in (*waits, None):
        try:
            return _post_once(url, body, headers, timeout)
        except ProviderError as e:
            if wait is None or getattr(e, "status", None) not in RETRY_STATUS:
                raise
            time.sleep(wait)
    raise AssertionError("unreachable")


def _post_once(url: str, body: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        err = ProviderError(f"HTTP {e.code}: {detail}")
        err.status = e.code
        raise err from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise ProviderError(str(e)) from e


class Provider:
    name = "provider"

    def complete(self, task: str, system: str, user: str) -> str:
        raise NotImplementedError


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float = 90):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def complete(self, task: str, system: str, user: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        data = _post_json(url, body, {"x-goog-api-key": self.api_key}, self.timeout)
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected Gemini response: {str(data)[:200]}") from e
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))


class OpenAICompatibleProvider(Provider):
    """Featherless (and any other OpenAI-compatible endpoint)."""

    def __init__(self, name: str, base_url: str, api_key: str, model: str, timeout: float = 120):
        self.name, self.base_url, self.api_key, self.model, self.timeout = name, base_url.rstrip("/"), api_key, model, timeout

    def complete(self, task: str, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
        }
        data = _post_json(f"{self.base_url}/chat/completions", body, {"Authorization": f"Bearer {self.api_key}"}, self.timeout)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected response: {str(data)[:200]}") from e


def prompt_key(task: str, system: str, user: str) -> str:
    return hashlib.sha256(f"{task}\n{system}\n{user}".encode("utf-8")).hexdigest()[:24]


class RecordedProvider(Provider):
    """Replays responses saved from a live provider for exactly this prompt."""

    name = "recorded"

    def __init__(self, directory: Path = RECORDED_DIR):
        self.directory = directory

    def path(self, task: str, system: str, user: str) -> Path:
        return self.directory / f"{task}-{prompt_key(task, system, user)}.json"

    def complete(self, task: str, system: str, user: str) -> str:
        p = self.path(task, system, user)
        if not p.exists():
            raise ProviderError("no recording for this prompt")
        return json.loads(p.read_text(encoding="utf-8"))["response"]

    def save(self, task: str, system: str, user: str, response: str, provider: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {"task": task, "provider": provider, "response": response}
        self.path(task, system, user).write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")


class FakeProvider(Provider):
    """For tests: answers from a function of (task, user)."""

    name = "fake"

    def __init__(self, fn: Callable[[str, str], str | dict]):
        self.fn = fn

    def complete(self, task: str, system: str, user: str) -> str:
        out = self.fn(task, user)
        return out if isinstance(out, str) else json.dumps(out)


def parse_json(text: str):
    """JSON from a model reply, tolerating ```json fences and text around it."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start = min((i for i in (t.find("{"), t.find("[")) if i != -1), default=-1)
        if start == -1:
            raise
        end = max(t.rfind("}"), t.rfind("]"))
        return json.loads(t[start : end + 1])


@dataclass
class Attempt:
    provider: str
    ok: bool
    error: str = ""
    seconds: float = 0.0


@dataclass
class ChainResult:
    data: object
    provider: str
    attempts: list[Attempt] = field(default_factory=list)


class Chain:
    def __init__(self, providers: list[Provider], record_to: RecordedProvider | None = None):
        self.providers = providers
        self.record_to = record_to  # save live responses (for the demo cases)

    def run(self, task: str, system: str, user: str, validate: Callable[[object], None] = lambda d: None) -> ChainResult:
        attempts: list[Attempt] = []
        for p in self.providers:
            t0 = time.monotonic()
            try:
                text = p.complete(task, system, user)
                data = parse_json(text)
                validate(data)
            except Exception as e:  # any failure moves to the next rung
                attempts.append(Attempt(p.name, False, f"{type(e).__name__}: {e}"[:300], time.monotonic() - t0))
                continue
            attempts.append(Attempt(p.name, True, "", time.monotonic() - t0))
            if self.record_to and not isinstance(p, (RecordedProvider, FakeProvider)):
                self.record_to.save(task, system, user, text, p.name)
            return ChainResult(data, p.name, attempts)
        raise ProviderError("every provider failed: " + "; ".join(f"{a.provider}: {a.error}" for a in attempts))


def default_chain(record: bool = False) -> Chain:
    """Gemini -> Featherless -> recorded, using whatever keys are configured."""
    load_env()
    providers: list[Provider] = []
    if os.environ.get("GEMINI_API_KEY"):
        providers.append(GeminiProvider(os.environ["GEMINI_API_KEY"], os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")))
    if os.environ.get("FEATHERLESS_API_KEY"):
        providers.append(
            OpenAICompatibleProvider(
                "featherless",
                os.environ.get("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
                os.environ["FEATHERLESS_API_KEY"],
                os.environ.get("FEATHERLESS_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
            )
        )
    recorded = RecordedProvider()
    providers.append(recorded)
    return Chain(providers, record_to=recorded if record else None)
