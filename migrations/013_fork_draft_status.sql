-- Migration 013: Forked periods start in 'draft' so parents can edit & approve curriculum.
-- Replaces fork_marketplace_listing() from 012_marketplace.sql; only change is
-- hardcoding status = 'draft' instead of copying it from the original period.

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

  -- Clone period row (shares vector_store_id and file_urls with original).
  -- Status is always 'draft' so the new owner can review and approve the curriculum.
  INSERT INTO period (
    period_id, owner_id, name, vector_store_id, file_urls,
    start_date, end_date, grade_level, mastery_threshold, course_description,
    course_metadata, file_vector_store_ids, processing_status, status,
    is_summer_quest, forked_from_period_id, created_at
  )
  SELECT
    p_new_period_id, p_new_owner_id, name, vector_store_id, file_urls,
    start_date, end_date, grade_level, mastery_threshold, course_description,
    course_metadata, file_vector_store_ids, processing_status, 'draft',
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
  INSERT INTO skill (period_id, skill_name, description, bloom_level, difficulty, mastery_threshold, mastery_criteria, metadata)
  SELECT p_new_period_id, skill_name, description, bloom_level, difficulty, mastery_threshold, mastery_criteria, metadata
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
