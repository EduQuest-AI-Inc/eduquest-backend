-- Migration 017: Add owner INSERT/UPDATE/DELETE policies for curriculum tables.
-- Phase 2 of the Supabase auth migration only added SELECT policies for week,
-- lesson, concept, skill, and concept_skill. These write policies allow teachers
-- (period owners) to manage curriculum via their own Supabase JWT instead of
-- the service-role key.

-- week: owner write policies
CREATE POLICY "week: owner insert" ON week FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = week.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "week: owner update" ON week FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = week.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = week.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "week: owner delete" ON week FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = week.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

-- lesson: owner write policies
CREATE POLICY "lesson: owner insert" ON lesson FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = lesson.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "lesson: owner update" ON lesson FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = lesson.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = lesson.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "lesson: owner delete" ON lesson FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = lesson.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

-- concept: owner write policies
CREATE POLICY "concept: owner insert" ON concept FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "concept: owner update" ON concept FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "concept: owner delete" ON concept FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

-- skill: owner write policies
CREATE POLICY "skill: owner insert" ON skill FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = skill.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "skill: owner update" ON skill FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = skill.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = skill.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "skill: owner delete" ON skill FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = skill.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

-- concept_skill: owner write policies (junction table — insert + delete only)
CREATE POLICY "concept_skill: owner insert" ON concept_skill FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept_skill.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

CREATE POLICY "concept_skill: owner delete" ON concept_skill FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM period p
      WHERE p.period_id = concept_skill.period_id
        AND p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );
