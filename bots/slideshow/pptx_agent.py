from typing import Any


class PptxAgent:
    async def run(
        self,
        lesson: dict[str, Any],
        concepts: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> bytes:
        raise NotImplementedError("PowerPoint agent not yet implemented")
