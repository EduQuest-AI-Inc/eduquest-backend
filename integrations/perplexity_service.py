"""
Perplexity Agent API service — uses the deep-research preset for comprehensive,
multi-step curriculum research.

Calls the Perplexity Agent REST endpoint directly via httpx (already a declared
dependency). No Perplexity SDK required.

The deep-research preset runs up to 10 research steps with web_search and
fetch_url tools, returning a long-form synthesis suitable for injecting into
the schedule agent prompt.

Required env var: PERPLEXITY_API_KEY

Docs: https://docs.perplexity.ai/docs/agent-api/presets#deep-research

Response shape (output array):
  [
    {"type": "web_search",  "queries": [...], "results": [...]},
    {"type": "fetch_url",   "contents": [...]},
    {"type": "message",     "role": "assistant",
     "content": [{"text": "<final answer>", ...}], "status": "completed"}
  ]
The assistant text is extracted from the last "message" item in output[].
"""
import asyncio
import os
from typing import List

import httpx

_AGENT_URL = "https://api.perplexity.ai/v1/agent"
_DEFAULT_PRESET = "deep-research"
_REQUEST_TIMEOUT = 300  # deep-research can take several minutes


class PerplexityService:
    """
    Calls Perplexity's Agent API with the deep-research preset for each query
    concurrently and returns a single markdown string aggregating all results.

    Deep-research does multi-step reasoning (up to 10 steps) with web_search
    and fetch_url tools — significantly richer than a single Sonar search pass.
    """

    def __init__(self) -> None:
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "PERPLEXITY_API_KEY environment variable is not set. "
                "Set it to your Perplexity API key to enable web research."
            )
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def research(
        self,
        queries: List[str],
        preset: str = _DEFAULT_PRESET,
        max_steps: int = 10,
    ) -> str:
        """
        Fire all queries concurrently against the Perplexity Agent API and
        return a single markdown string with one section per query.

        Args:
            queries: List of research query strings.
            preset: Perplexity preset name (default: "deep-research").
            max_steps: Max agent steps per query (1-10).

        Returns:
            Markdown-formatted string: "## <query>\\n<answer>\\n\\n..."
        """
        if not queries:
            return ""

        results = await asyncio.gather(
            *[self._query(q, preset, max_steps) for q in queries],
            return_exceptions=True,
        )

        sections = []
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                sections.append(f"## {query}\n*(Research unavailable: {result})*")
            else:
                sections.append(f"## {query}\n{result}")

        return "\n\n".join(sections)

    async def _query(self, query: str, preset: str, max_steps: int) -> str:
        """Single Agent API call; returns the assistant's response text."""
        payload = {
            "preset": preset,
            "input": query,
            "max_steps": max_steps,
        }
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                _AGENT_URL,
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            return self._extract_text(response.json())

    @staticmethod
    def _extract_text(data: dict) -> str:
        """
        Extract the assistant's response text from the Agent API response.

        The response `output` array ends with a message item of the form:
          {"type": "message", "role": "assistant",
           "content": [{"text": "...", ...}], "status": "completed"}
        """
        output = data.get("output") or []
        for item in reversed(output):
            if isinstance(item, dict) and item.get("type") == "message":
                for block in item.get("content") or []:
                    text = block.get("text", "")
                    if text:
                        return text
        return ""
