ALTER TABLE period
  DROP COLUMN IF EXISTS canvas_api_url,
  DROP COLUMN IF EXISTS canvas_api_key,
  DROP COLUMN IF EXISTS owner_type;
