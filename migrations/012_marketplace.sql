-- Migration 012: Class Marketplace
-- Adds fork tracking to period table, marketplace_listing table,
-- and an atomic fork RPC.

-- 1. Fork tracking on period
ALTER TABLE period
  ADD COLUMN IF NOT EXISTS forked_from_period_id TEXT REFERENCES period(period_id);

CREATE INDEX IF NOT EXISTS idx_period_forked_from ON period(forked_from_period_id);

-- 2. Marketplace listing table
CREATE TABLE IF NOT EXISTS marketplace_listing (
  listing_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  period_id      TEXT NOT NULL REFERENCES period(period_id),
  published_by   TEXT NOT NULL REFERENCES "user"(user_id),
  tags           TEXT[] DEFAULT '{}',
  fork_count     INT NOT NULL DEFAULT 0,
  is_published   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  delete_after   TIMESTAMPTZ
);

-- One listing per period (unique index allows upsert on republish)
CREATE UNIQUE INDEX IF NOT EXISTS idx_marketplace_listing_period
  ON marketplace_listing(period_id);

CREATE INDEX IF NOT EXISTS idx_marketplace_listing_published
  ON marketplace_listing(is_published, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_marketplace_listing_tags
  ON marketplace_listing USING GIN(tags);

-- updated_at trigger using inline function (moddatetime extension not required)
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER set_marketplace_listing_updated_at
  BEFORE UPDATE ON marketplace_listing
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 3. Atomic fork RPC
-- Clones a period + its full curriculum into a new period owned by new_owner_id.
-- Increments fork_count on the listing.
-- Called by the backend service; never called by the client directly.
CREATE OR REPLACE FUNCTION fork_marketplace_listing(
  p_listing_id    UUID,
  p_new_owner_id  TEXT,
  p_new_period_id TEXT
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
  v_orig_period_id TEXT;
BEGIN
  -- Resolve original period from listing
  SELECT period_id INTO v_orig_period_id
    FROM marketplace_listing
   WHERE listing_id = p_listing_id AND is_published = TRUE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'listing_not_found';
  END IF;

  -- Clone period row (shares vector_store_id and file_urls with original)
  INSERT INTO period (
    period_id, owner_id, name, vector_store_id, file_urls,
    start_date, end_date, grade_level, mastery_threshold, course_description,
    course_metadata, file_vector_store_ids, processing_status, status,
    is_summer_quest, forked_from_period_id, created_at
  )
  SELECT
    p_new_period_id, p_new_owner_id, name, vector_store_id, file_urls,
    start_date, end_date, grade_level, mastery_threshold, course_description,
    course_metadata, file_vector_store_ids, processing_status, status,
    is_summer_quest, v_orig_period_id, now()
  FROM period
  WHERE period_id = v_orig_period_id;

  -- Clone weeks
  INSERT INTO week (period_id, week_number, week_start, week_end)
  SELECT p_new_period_id, week_number, week_start, week_end
    FROM week WHERE period_id = v_orig_period_id;

  -- Clone lessons (DB auto-generates new lesson_ids) and remap into concepts
  WITH new_lessons AS (
    INSERT INTO lesson (period_id, lesson_name, week_number)
    SELECT p_new_period_id, lesson_name, week_number
      FROM lesson WHERE period_id = v_orig_period_id
    RETURNING lesson_id, lesson_name
  ),
  old_lessons AS (
    SELECT lesson_id, lesson_name FROM lesson WHERE period_id = v_orig_period_id
  ),
  lesson_map AS (
    SELECT o.lesson_id AS old_id, n.lesson_id AS new_id
      FROM old_lessons o
      JOIN new_lessons n ON o.lesson_name = n.lesson_name
  )
  INSERT INTO concept (
    period_id, concept_name, lesson_name, lesson_id,
    description, prerequisites, common_misconceptions, key_takeaways, metadata
  )
  SELECT
    p_new_period_id, c.concept_name, c.lesson_name, lm.new_id,
    c.description, c.prerequisites, c.common_misconceptions, c.key_takeaways, c.metadata
  FROM concept c
  JOIN lesson_map lm ON c.lesson_id = lm.old_id
  WHERE c.period_id = v_orig_period_id;

  -- Clone skills
  INSERT INTO skill (period_id, skill_name, description, week_number, lesson_name)
  SELECT p_new_period_id, skill_name, description, week_number, lesson_name
    FROM skill WHERE period_id = v_orig_period_id;

  -- Clone concept_skill mappings
  INSERT INTO concept_skill (period_id, concept_name, skill_name)
  SELECT p_new_period_id, concept_name, skill_name
    FROM concept_skill WHERE period_id = v_orig_period_id;

  -- Atomic fork_count increment
  UPDATE marketplace_listing
     SET fork_count = fork_count + 1
   WHERE listing_id = p_listing_id;
END;
$$;
