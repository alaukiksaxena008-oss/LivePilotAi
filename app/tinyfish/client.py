"""Thin async wrapper around the TinyFish APIs.

Agent endpoints and fields follow https://docs.tinyfish.ai/agent-api/reference.md.
Search and Fetch response shapes are returned raw: check their docs and tighten later.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

import httpx

AGENT_BASE = "https://agent.tinyfish.ai"
SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


class TinyFishError(Exception):
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


class TinyFishClient:
    def __init__(self, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 60.0):
        if not api_key:
            raise ValueError("TINYFISH_API_KEY is missing")
        self._http = httpx.AsyncClient(headers={"X-API-Key": api_key}, transport=transport, timeout=timeout)

    async def __aenter__(self) -> "TinyFishClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------- helpers ----------
    @staticmethod
    def build_body(
        url: str,
        goal: str,
        *,
        output_schema: dict | None = None,
        use_vault: bool = False,
        credential_item_ids: list[str] | None = None,
        use_profile: bool = False,
        profile_id: str | None = None,
        browser_profile: str | None = None,
        country_code: str | None = None,
        max_duration_seconds: int | None = None,
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"url": url, "goal": goal}
        if output_schema:
            body["output_schema"] = output_schema
        if use_vault:
            body["use_vault"] = True
            if credential_item_ids:
                body["credential_item_ids"] = credential_item_ids
        if use_profile:
            body["use_profile"] = True
            if profile_id:
                body["profile_id"] = profile_id
        if browser_profile:
            body["browser_profile"] = browser_profile
        if country_code:
            body["proxy_config"] = {"enabled": True, "type": "tinyfish", "country_code": country_code}
        if max_duration_seconds:
            body["agent_config"] = {"max_duration_seconds": max_duration_seconds}
        if webhook_url:
            body["webhook_url"] = webhook_url
        return body

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        try:
            resp = await self._http.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            raise TinyFishError(f"Network error: {e!r}") from e
        if resp.status_code >= 400:
            code, message = None, resp.text[:300]
            try:
                data = resp.json()
                err = data.get("error", data) if isinstance(data, dict) else {}
                if isinstance(err, dict):
                    code = err.get("code")
                    message = err.get("message") or message
            except ValueError:
                pass
            raise TinyFishError(message, status=resp.status_code, code=code)
        return resp.json()

    # ---------- Agent API ----------
    async def run(self, url: str, goal: str, **opts) -> dict:
        """Blocking run: returns the final result. Cannot be cancelled."""
        return await self._request("POST", f"{AGENT_BASE}/v1/automation/run", json=self.build_body(url, goal, **opts), timeout=330.0)

    async def run_async(self, url: str, goal: str, **opts) -> str:
        """Starts a run and returns its run_id immediately."""
        data = await self._request("POST", f"{AGENT_BASE}/v1/automation/run-async", json=self.build_body(url, goal, **opts))
        if data.get("error") or not data.get("run_id"):
            raise TinyFishError(f"Could not create run: {data.get('error')}")
        return data["run_id"]

    async def get_run(self, run_id: str) -> dict:
        return await self._request("GET", f"{AGENT_BASE}/v1/runs/{run_id}")

    async def cancel(self, run_id: str) -> dict:
        return await self._request("POST", f"{AGENT_BASE}/v1/runs/{run_id}/cancel")

    async def wait_for_run(self, run_id: str, *, poll_interval: float = 3.0, timeout: float = 600.0) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            run = await self.get_run(run_id)
            if run.get("status") in TERMINAL_STATUSES:
                return run
            if time.monotonic() > deadline:
                await self.cancel(run_id)
                raise TinyFishError(f"Run {run_id} timed out after {timeout}s")
            await asyncio.sleep(poll_interval)

    async def stream(self, url: str, goal: str, **opts) -> AsyncIterator[dict]:
        """Server-sent events: STARTED, STREAMING_URL, PROGRESS, HEARTBEAT, COMPLETE."""
        body = self.build_body(url, goal, **opts)
        async with self._http.stream("POST", f"{AGENT_BASE}/v1/automation/run-sse", json=body, timeout=None) as resp:
            if resp.status_code >= 400:
                text = (await resp.aread()).decode()[:300]
                raise TinyFishError(text, status=resp.status_code)
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    # ---------- Search / Fetch ----------
    async def search(self, query: str, *, location: str | None = None, language: str | None = None) -> Any:
        params = {"query": query}
        if location:
            params["location"] = location
        if language:
            params["language"] = language
        return await self._request("GET", SEARCH_URL, params=params)

    async def fetch(self, urls: list[str]) -> Any:
        return await self._request("POST", FETCH_URL, json={"urls": urls})
