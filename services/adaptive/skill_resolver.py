"""
Canonical Skill Resolver — 4-tier deduplication for canonical_skill table.

Tier 1: exact normalized-title match    → return existing canonical_skill_id
Tier 2: embedding cosine >= 0.88        → return existing
Tier 3: LLM judge for 0.78–0.88 band   → return existing or fall through
Tier 4: below threshold                 → mint new canonical_skill row

Every call writes a row to skill_resolution_decision for auditing.
Cold-start (empty table): everything mints — correct behaviour.
"""
from __future__ import annotations

import logging
import re

import openai
from pydantic import BaseModel

from bots.model_config import RESOLVER_JUDGE_MODEL, SKILL_EMBEDDING_MODEL
from data_access.canonical_skill_dao import CanonicalSkillDAO
from data_access.skill_resolution_decision_dao import SkillResolutionDecisionDAO
from models.adaptive.canonical_skill import CanonicalSkill
from models.adaptive.skill_resolution_decision import SkillResolutionDecision

logger = logging.getLogger(__name__)

_EMBEDDING_THRESHOLD = 0.88
_LLM_JUDGE_LOW = 0.78


class _JudgeResult(BaseModel):
    is_equivalent: bool
    rationale: str


class SkillResolver:
    """
    Synchronous canonical skill resolver. Safe to call from synchronous service
    methods. Uses the admin Supabase client (reads across all periods).
    """

    def __init__(self) -> None:
        self._oai = openai.OpenAI()
        self._canonical_dao = CanonicalSkillDAO()  # admin client
        self._resolution_dao = SkillResolutionDecisionDAO()  # admin client

    # -- public API -----------------------------------------------------------

    def resolve(self, period_id: str, skill_name: str, description: str = "") -> str:
        """
        Returns a canonical_skill_id (existing or newly minted).
        Never raises — on any unexpected error mints a new node and logs.
        """
        try:
            return self._resolve(period_id, skill_name, description)
        except Exception:
            logger.exception(
                "SkillResolver._resolve raised unexpectedly for %s/%s; minting fallback",
                period_id, skill_name,
            )
            return self._mint(period_id, skill_name, description, embedding=None)

    # -- private helpers ------------------------------------------------------

    def _resolve(self, period_id: str, skill_name: str, description: str) -> str:
        # Tier 1: exact normalized name match (no API call)
        normalized = re.sub(r"[^a-zA-Z0-9 ]", "", skill_name.lower()).strip()
        existing = self._canonical_dao.find_by_normalized_name(normalized)
        if existing:
            self._log("exact", period_id, skill_name, existing["canonical_skill_id"])
            return existing["canonical_skill_id"]

        # Compute embedding once; used for Tier 2 and also stored on mint
        text = f"{skill_name}: {description}"[:512] if description else skill_name[:512]
        embedding = self._get_embedding(text)

        # Tier 2 + 3: similarity search
        candidates = self._canonical_dao.find_by_embedding_similarity(
            embedding, _LLM_JUDGE_LOW, match_count=5
        )
        if candidates:
            best = candidates[0]
            similarity = float(best.get("similarity", 0))

            if similarity >= _EMBEDDING_THRESHOLD:
                # Tier 2: direct cosine match
                self._log("embedding", period_id, skill_name, best["canonical_skill_id"], similarity)
                return best["canonical_skill_id"]

            if similarity >= _LLM_JUDGE_LOW:
                # Tier 3: LLM judge
                is_same, rationale = self._llm_judge(skill_name, best["name"], description)
                if is_same:
                    self._log("llm_judge", period_id, skill_name, best["canonical_skill_id"], similarity, rationale)
                    return best["canonical_skill_id"]

        # Tier 4: mint a new canonical node
        return self._mint(period_id, skill_name, description, embedding)

    def _mint(
        self,
        period_id: str,
        skill_name: str,
        description: str,
        embedding: list[float] | None,
    ) -> str:
        row = self._canonical_dao.insert(
            CanonicalSkill(name=skill_name, description=description or None)
        )
        new_id = row["canonical_skill_id"]
        if embedding:
            try:
                self._canonical_dao.update_embedding(new_id, embedding)
            except Exception:
                logger.warning("Could not store embedding for new canonical skill %s", new_id)
        self._log("minted", period_id, skill_name, new_id)
        return new_id

    def _get_embedding(self, text: str) -> list[float]:
        resp = self._oai.embeddings.create(model=SKILL_EMBEDDING_MODEL, input=text)
        return resp.data[0].embedding

    def _llm_judge(
        self, skill_name: str, candidate_name: str, description: str
    ) -> tuple[bool, str]:
        resp = self._oai.beta.chat.completions.parse(
            model=RESOLVER_JUDGE_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You determine whether two educational skill names refer to the same "
                        "underlying learning objective. Be conservative — only mark equivalent "
                        "if the skills are genuinely interchangeable for curriculum purposes."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Skill 1: {skill_name!r}\n"
                        f"Skill 2: {candidate_name!r}\n"
                        f"Context: {description[:200]}\n\n"
                        "Are these the same underlying skill?"
                    ),
                },
            ],
            response_format=_JudgeResult,
        )
        result = resp.choices[0].message.parsed
        return result.is_equivalent, result.rationale

    def _log(
        self,
        outcome: str,
        period_id: str,
        skill_name: str,
        canonical_skill_id: str,
        similarity: float | None = None,
        rationale: str | None = None,
    ) -> None:
        try:
            self._resolution_dao.insert(
                SkillResolutionDecision(
                    period_id=period_id,
                    skill_name=skill_name,
                    canonical_skill_id=canonical_skill_id,
                    outcome=outcome,
                    similarity_score=similarity,
                    judge_rationale=rationale,
                )
            )
        except Exception:
            logger.warning(
                "Could not log skill resolution decision for %s/%s", period_id, skill_name
            )
