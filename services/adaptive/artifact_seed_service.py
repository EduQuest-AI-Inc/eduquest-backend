"""Artifact seeding pipeline — extracts skills from learner artifacts and seeds knowledge state."""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from bots.protocol import BotProviderProtocol
from data_access.canonical_skill_dao import CanonicalSkillDAO
from data_access.learner_artifact_dao import LearnerArtifactDAO
from data_access.parent_dao import ParentDAO
from data_access.skill_dao import SkillDAO
from exceptions.permission_error import PermissionError
from models.adaptive.learner_artifact import LearnerArtifact
from services.adaptive.learning_event_service import LearningEventService

logger = logging.getLogger(__name__)

# Maximum confidence level that artifact seeding can establish, by artifact type.
# Active assessment (pretest / teaching loop) is required to reach "known" (>= 0.65).
_CONFIDENCE_CAP: dict[str, float] = {
    "transcript": 0.65,
    "resume":     0.65,
    "file":       0.65,
    "free_text":  0.35,
}


class ArtifactSeedService:
    def __init__(
        self,
        *,
        bot_provider: BotProviderProtocol,
        skill_dao=None,
        canonical_skill_dao=None,
        artifact_dao=None,
        parent_dao=None,
        event_service=None,
    ) -> None:
        self._bot_provider = bot_provider
        self._skill_dao = skill_dao or SkillDAO()
        self._canonical_dao = canonical_skill_dao or CanonicalSkillDAO()
        self._artifact_dao = artifact_dao or LearnerArtifactDAO()
        self._parent_dao = parent_dao or ParentDAO()
        self._event_service = event_service or LearningEventService()

    async def seed(
        self,
        *,
        learner_id: str,
        period_id: str,
        artifact_type: str,
        text_content: str,
    ) -> dict[str, Any]:
        """Extract skills from learner text, match to period curriculum, seed knowledge state.

        Raises PermissionError if the student is under 13 and lacks parental VPC verification.
        Returns {seeded_skill_count, artifact_id}.
        """
        self._check_parental_consent(learner_id)

        if not text_content.strip():
            return {"seeded_skill_count": 0, "artifact_id": None}

        pii_redactor = self._bot_provider.create_pii_redactor()
        redacted = pii_redactor.redact(text_content)

        extractor = self._bot_provider.create_artifact_extractor()
        try:
            extraction = await extractor.extract(redacted)
        except Exception:
            logger.warning(
                "artifact extraction failed for learner=%s period=%s (returning 0 seeds)",
                learner_id, period_id,
            )
            extraction_skills = []
        else:
            extraction_skills = extraction.skills

        confidence_cap = _CONFIDENCE_CAP.get(artifact_type, 0.35)
        period_canonical = self._get_period_canonical_skills(period_id)
        seed_list = self._match_to_canonical(extraction_skills, period_canonical, confidence_cap)

        summary = (
            f"{len(extraction_skills)} skill(s) extracted; "
            f"{len(seed_list)} matched period curriculum"
        )
        artifact_row = self._artifact_dao.insert(LearnerArtifact(
            learner_id=learner_id,
            period_id=period_id,
            artifact_type=artifact_type,
            extracted_summary=summary,
            delete_after=(datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
        ))
        artifact_id = artifact_row.get("artifact_id") if artifact_row else None

        if seed_list:
            self._event_service.seed_from_artifact(learner_id, period_id, seed_list)

        logger.info(
            "artifact seeded: learner=%s period=%s extracted=%d seeded=%d",
            learner_id, period_id, len(extraction_skills), len(seed_list),
        )
        return {"seeded_skill_count": len(seed_list), "artifact_id": artifact_id}

    # ── private helpers ───────────────────────────────────────────────────────

    def _check_parental_consent(self, learner_id: str) -> None:
        """Block under-13 learners whose parent hasn't completed VPC verification.

        vpc_verified_at is a column on the parent table set when a parent completes
        verified parental consent via the VPC flow.
        """
        try:
            parents = self._parent_dao.get_parents_by_student_id(learner_id)
        except Exception:
            logger.warning("under-13 check: parent lookup failed; allowing (non-fatal)")
            return
        if parents and not any(p.get("vpc_verified_at") for p in parents):
            raise PermissionError(
                "Parental verification required before using AI learning features"
            )

    def _get_period_canonical_skills(self, period_id: str) -> list[dict]:
        """Return [{canonical_skill_id, name}] for all resolved skills in the period."""
        skills = self._skill_dao.get_skills_by_period(period_id)
        canonical_ids = [s["canonical_skill_id"] for s in skills if s.get("canonical_skill_id")]
        if not canonical_ids:
            return []
        canonical_rows = self._canonical_dao.get_by_ids(canonical_ids)
        return [
            {"canonical_skill_id": r["canonical_skill_id"], "name": r["name"]}
            for r in canonical_rows
        ]

    @staticmethod
    def _match_to_canonical(
        extracted_skills: list,
        canonical_skills: list[dict],
        confidence_cap: float,
    ) -> list[dict]:
        """Match extracted skill names to period canonical skills by normalized name overlap.

        Returns [{canonical_skill_id, confidence_cap}] for matched skills only.
        Uses conservative substring containment — both strings must be at least 4 chars.
        """
        seed_list: list[dict] = []
        seen: set[str] = set()

        for ext in extracted_skills:
            ext_norm = re.sub(r"[^a-z0-9 ]", "", ext.canonical_name.lower()).strip()
            if len(ext_norm) < 4:
                continue
            for csk in canonical_skills:
                cid = csk["canonical_skill_id"]
                if cid in seen:
                    continue
                canon_norm = re.sub(r"[^a-z0-9 ]", "", csk["name"].lower()).strip()
                if ext_norm == canon_norm or ext_norm in canon_norm or canon_norm in ext_norm:
                    seed_list.append({
                        "canonical_skill_id": cid,
                        "confidence_cap": round(ext.confidence * confidence_cap, 4),
                    })
                    seen.add(cid)
                    break

        return seed_list
