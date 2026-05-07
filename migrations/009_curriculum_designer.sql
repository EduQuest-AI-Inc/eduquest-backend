-- Migration 009: Curriculum Designer tables
-- Adds status lifecycle to period and creates the curriculum object graph:
-- week → lesson → concept ← concept_skill → skill

-- ── period: curriculum lifecycle status ─────────────────────────────────────

ALTER TABLE period ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending';
-- Values: "pending" (no generation yet) | "draft" (bot wrote rows, awaiting review) | "approved" (teacher confirmed)

-- ── week ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS week (
  period_id   text    NOT NULL REFERENCES period(period_id) ON DELETE CASCADE,
  week_number integer NOT NULL,
  week_start  date,
  week_end    date,
  PRIMARY KEY (period_id, week_number)
);

ALTER TABLE week ENABLE ROW LEVEL SECURITY;

CREATE POLICY "week: owner select" ON week FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = week.period_id
        AND p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

CREATE POLICY "week: enrolled student select" ON week FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM enrollment e
      WHERE e.period_id = week.period_id
        AND e.user_id = (auth.jwt() ->> 'sub')
    )
  );

CREATE POLICY "week: parent of enrolled student select" ON week FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM parent p
      WHERE p.user_id = (auth.jwt() ->> 'sub')
        AND EXISTS (
          SELECT 1 FROM enrollment e
          WHERE e.period_id = week.period_id
            AND e.user_id = ANY(p.linked_student_ids)
        )
    )
  );

-- ── lesson ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lesson (
  period_id   text    NOT NULL REFERENCES period(period_id) ON DELETE CASCADE,
  lesson_name text    NOT NULL,
  week_number integer NOT NULL,
  FOREIGN KEY (period_id, week_number) REFERENCES week(period_id, week_number),
  PRIMARY KEY (period_id, lesson_name)
);

ALTER TABLE lesson ENABLE ROW LEVEL SECURITY;

CREATE POLICY "lesson: owner select" ON lesson FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = lesson.period_id
        AND p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

CREATE POLICY "lesson: enrolled student select" ON lesson FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM enrollment e
      WHERE e.period_id = lesson.period_id
        AND e.user_id = (auth.jwt() ->> 'sub')
    )
  );

-- ── concept ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS concept (
  period_id               text        NOT NULL REFERENCES period(period_id) ON DELETE CASCADE,
  concept_name            text        NOT NULL,
  lesson_name             text        NOT NULL,
  description             text,
  prerequisites           jsonb,
  common_misconceptions   jsonb,
  key_takeaways           jsonb,
  metadata                jsonb,
  created_at              timestamptz NOT NULL DEFAULT now(),
  last_updated_at         timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (period_id, lesson_name) REFERENCES lesson(period_id, lesson_name),
  PRIMARY KEY (period_id, concept_name)
);

ALTER TABLE concept ENABLE ROW LEVEL SECURITY;

CREATE POLICY "concept: owner select" ON concept FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept.period_id
        AND p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

CREATE POLICY "concept: enrolled student select" ON concept FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM enrollment e
      WHERE e.period_id = concept.period_id
        AND e.user_id = (auth.jwt() ->> 'sub')
    )
  );

-- ── skill ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS skill (
  period_id         text  NOT NULL REFERENCES period(period_id) ON DELETE CASCADE,
  skill_name        text  NOT NULL,
  description       text,
  bloom_level       text,
  difficulty        text,
  mastery_threshold float NOT NULL DEFAULT 0.8,
  mastery_criteria  jsonb,
  metadata          jsonb,
  PRIMARY KEY (period_id, skill_name)
);

ALTER TABLE skill ENABLE ROW LEVEL SECURITY;

CREATE POLICY "skill: owner select" ON skill FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = skill.period_id
        AND p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

CREATE POLICY "skill: enrolled student select" ON skill FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM enrollment e
      WHERE e.period_id = skill.period_id
        AND e.user_id = (auth.jwt() ->> 'sub')
    )
  );

-- ── concept_skill ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS concept_skill (
  period_id    text NOT NULL,
  concept_name text NOT NULL,
  skill_name   text NOT NULL,
  FOREIGN KEY (period_id, concept_name) REFERENCES concept(period_id, concept_name) ON DELETE CASCADE,
  FOREIGN KEY (period_id, skill_name)   REFERENCES skill(period_id, skill_name)     ON DELETE CASCADE,
  PRIMARY KEY (period_id, concept_name, skill_name)
);

ALTER TABLE concept_skill ENABLE ROW LEVEL SECURITY;

CREATE POLICY "concept_skill: owner select" ON concept_skill FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept_skill.period_id
        AND p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

CREATE POLICY "concept_skill: enrolled student select" ON concept_skill FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM enrollment e
      WHERE e.period_id = concept_skill.period_id
        AND e.user_id = (auth.jwt() ->> 'sub')
    )
  );

-- ── Deferred: quest → week FK ─────────────────────────────────────────────────
-- Run this AFTER all existing quest rows have matching (period_id, week) entries
-- in the new week table. Applying it now would fail on legacy data.
--
-- ALTER TABLE quest
--   ADD CONSTRAINT quest_week_fk
--   FOREIGN KEY (period_id, week) REFERENCES week(period_id, week_number);
