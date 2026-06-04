-- Migration 020: COPPA student intake containment and authorization primitives.
-- Apply before deploying the matching FastAPI and Next.js changes.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE student
  ADD COLUMN IF NOT EXISTS age_band text,
  ADD COLUMN IF NOT EXISTS age_signal_source text,
  ADD COLUMN IF NOT EXISTS compliance_status text NOT NULL DEFAULT 'blocked',
  ADD COLUMN IF NOT EXISTS compliance_review_due_at timestamptz,
  ADD COLUMN IF NOT EXISTS compliance_outreach_stage integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS compliance_outreach_sent_at timestamptz;

ALTER TABLE student
  DROP CONSTRAINT IF EXISTS student_age_band_check,
  ADD CONSTRAINT student_age_band_check
    CHECK (age_band IS NULL OR age_band IN ('under_13', '13_to_17', '18_plus')),
  DROP CONSTRAINT IF EXISTS student_compliance_status_check,
  ADD CONSTRAINT student_compliance_status_check
    CHECK (compliance_status IN (
      'active', 'legacy_review_due', 'quarantined_age_review', 'provisioning', 'blocked'
    ));

-- Fail closed for the highest-risk legacy cohort. Grade 8-12 records get a
-- short remediation window before the request-time authorization gate blocks them.
UPDATE student
SET compliance_status = CASE
      WHEN grade IS NULL OR grade <= 7 THEN 'quarantined_age_review'
      ELSE 'legacy_review_due'
    END,
    compliance_review_due_at = CASE
      WHEN grade IS NULL OR grade <= 7 THEN now()
      ELSE now() + interval '21 days'
    END
WHERE age_band IS NULL;

UPDATE "user" u
SET login_disabled = true
FROM student s
WHERE s.user_id = u.user_id
  AND s.compliance_status = 'quarantined_age_review';

-- Historic invite redemption was a relationship link, not VPC.
UPDATE parent SET vpc_verified_at = NULL WHERE vpc_verified_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS age_screen_session (
  token_hash text PRIMARY KEY,
  age_band text NOT NULL CHECK (age_band IN ('under_13', '13_to_17', '18_plus')),
  signal_source text NOT NULL CHECK (signal_source IN (
    'self_screen', 'parent_screen', 'legacy_self_screen', 'legacy_parent_review',
    'operations_review', 'school_registry'
  )),
  authenticated_parent_id text REFERENCES "user"(user_id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_age_screen_session_delete_after
  ON age_screen_session(delete_after);

CREATE TABLE IF NOT EXISTS student_email_verification (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email_hmac text NOT NULL,
  code_hash text NOT NULL,
  verified_token_hash text,
  attempt_count integer NOT NULL DEFAULT 0,
  expires_at timestamptz NOT NULL,
  verified_at timestamptz,
  consumed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_email_verification_email_hmac
  ON student_email_verification(email_hmac);
CREATE INDEX IF NOT EXISTS idx_student_email_verification_delete_after
  ON student_email_verification(delete_after);

CREATE TABLE IF NOT EXISTS auth_rate_limit (
  scope text NOT NULL,
  key_hash text NOT NULL,
  count integer NOT NULL DEFAULT 0,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL,
  PRIMARY KEY (scope, key_hash)
);
CREATE INDEX IF NOT EXISTS idx_auth_rate_limit_delete_after
  ON auth_rate_limit(delete_after);

CREATE TABLE IF NOT EXISTS parent_assurance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_user_id text NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
  method text NOT NULL CHECK (method IN ('stripe_refunded_charge')),
  status text NOT NULL CHECK (status IN ('pending', 'verified', 'refund_failed', 'revoked')),
  stripe_payment_intent_id text,
  stripe_refund_id text,
  verified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parent_assurance_delete_after
  ON parent_assurance(delete_after);

CREATE TABLE IF NOT EXISTS vpc_request (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_user_id text NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
  status text NOT NULL CHECK (status IN (
    'pending_email_confirmation', 'ready_for_checkout', 'checkout_open',
    'payment_processing', 'refund_requested', 'verified', 'refund_failed',
    'cancelled', 'expired', 'consumed'
  )),
  notice_version text NOT NULL,
  notice_accepted_at timestamptz,
  stripe_checkout_session_id text,
  stripe_checkout_expires_at timestamptz,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vpc_request_checkout_session
  ON vpc_request(stripe_checkout_session_id);
CREATE INDEX IF NOT EXISTS idx_vpc_request_delete_after
  ON vpc_request(delete_after);

CREATE TABLE IF NOT EXISTS student_authorization (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_user_id text REFERENCES "user"(user_id) ON DELETE SET NULL,
  authorizer_parent_id text NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
  authorization_type text NOT NULL CHECK (authorization_type IN ('parent_direct', 'teacher_enrollment')),
  evidence_type text NOT NULL CHECK (evidence_type IN ('parent_attestation', 'stripe_refunded_charge')),
  vpc_request_id uuid REFERENCES vpc_request(id) ON DELETE SET NULL,
  parent_assurance_id uuid REFERENCES parent_assurance(id) ON DELETE SET NULL,
  notice_version text NOT NULL,
  authorized_at timestamptz NOT NULL,
  consumed_at timestamptz,
  revoked_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_authorization_delete_after
  ON student_authorization(delete_after);

CREATE TABLE IF NOT EXISTS student_age_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_user_id text REFERENCES "user"(user_id) ON DELETE CASCADE,
  age_band text NOT NULL CHECK (age_band IN ('under_13', '13_to_17', '18_plus')),
  signal_source text NOT NULL CHECK (signal_source IN (
    'self_screen', 'parent_screen', 'legacy_self_screen', 'legacy_parent_review',
    'operations_review', 'school_registry'
  )),
  authority_user_id text REFERENCES "user"(user_id) ON DELETE SET NULL,
  assessed_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_age_evidence_delete_after
  ON student_age_evidence(delete_after);

CREATE TABLE IF NOT EXISTS student_claim_token (
  token_hash text PRIMARY KEY,
  authorization_id uuid NOT NULL REFERENCES student_authorization(id) ON DELETE CASCADE,
  reservation_nonce text,
  reservation_expires_at timestamptz,
  attempt_count integer NOT NULL DEFAULT 0,
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_claim_token_delete_after
  ON student_claim_token(delete_after);

CREATE TABLE IF NOT EXISTS stripe_webhook_event (
  event_id text PRIMARY KEY,
  event_type text NOT NULL,
  processing_status text NOT NULL CHECK (processing_status IN ('received', 'processed', 'failed')),
  processed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  delete_after timestamptz NOT NULL
);

CREATE OR REPLACE FUNCTION consume_age_screen_session(p_token_hash text)
RETURNS SETOF age_screen_session
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  UPDATE age_screen_session
  SET consumed_at = now()
  WHERE token_hash = p_token_hash
    AND consumed_at IS NULL
    AND expires_at > now()
  RETURNING *;
END;
$$;

CREATE OR REPLACE FUNCTION confirm_student_email_verification(
  p_email_hmac text,
  p_code_hash text,
  p_verified_token_hash text
)
RETURNS SETOF student_email_verification
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_id uuid;
BEGIN
  SELECT id INTO v_id
  FROM student_email_verification
  WHERE email_hmac = p_email_hmac
    AND consumed_at IS NULL
    AND verified_at IS NULL
    AND expires_at > now()
    AND attempt_count < 5
  ORDER BY created_at DESC
  LIMIT 1
  FOR UPDATE;

  IF v_id IS NULL THEN
    RETURN;
  END IF;

  UPDATE student_email_verification
  SET attempt_count = attempt_count + 1
  WHERE id = v_id;

  RETURN QUERY
  UPDATE student_email_verification
  SET verified_at = now(),
      verified_token_hash = p_verified_token_hash
  WHERE id = v_id
    AND code_hash = p_code_hash
  RETURNING *;
END;
$$;

CREATE OR REPLACE FUNCTION consume_student_email_verification(
  p_email_hmac text,
  p_verified_token_hash text
)
RETURNS SETOF student_email_verification
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  UPDATE student_email_verification
  SET consumed_at = now()
  WHERE email_hmac = p_email_hmac
    AND verified_token_hash = p_verified_token_hash
    AND verified_at IS NOT NULL
    AND consumed_at IS NULL
    AND expires_at > now()
  RETURNING *;
END;
$$;

CREATE OR REPLACE FUNCTION increment_auth_rate_limit(
  p_scope text,
  p_key_hash text,
  p_window_seconds integer
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_count integer;
BEGIN
  INSERT INTO auth_rate_limit(scope, key_hash, count, expires_at, delete_after)
  VALUES (
    p_scope, p_key_hash, 1,
    now() + (p_window_seconds || ' seconds')::interval,
    now() + (p_window_seconds || ' seconds')::interval + interval '24 hours'
  )
  ON CONFLICT (scope, key_hash) DO UPDATE
  SET count = CASE WHEN auth_rate_limit.expires_at > now()
                   THEN auth_rate_limit.count + 1 ELSE 1 END,
      expires_at = CASE WHEN auth_rate_limit.expires_at > now()
                        THEN auth_rate_limit.expires_at
                        ELSE now() + (p_window_seconds || ' seconds')::interval END,
      delete_after = CASE WHEN auth_rate_limit.expires_at > now()
                          THEN auth_rate_limit.delete_after
                          ELSE now() + (p_window_seconds || ' seconds')::interval + interval '24 hours' END
  RETURNING count INTO v_count;
  RETURN v_count;
END;
$$;

CREATE OR REPLACE FUNCTION cleanup_coppa_intake_records()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE student_claim_token
  SET reservation_nonce = NULL,
      reservation_expires_at = NULL
  WHERE consumed_at IS NULL
    AND reservation_expires_at < now();

  UPDATE vpc_request
  SET status = 'expired'
  WHERE status = 'checkout_open'
    AND stripe_checkout_expires_at < now();

  DELETE FROM age_screen_session WHERE delete_after < now();
  DELETE FROM student_email_verification WHERE delete_after < now();
  DELETE FROM auth_rate_limit WHERE delete_after < now();
  DELETE FROM stripe_webhook_event WHERE delete_after < now();
  DELETE FROM student_claim_token WHERE delete_after < now();
  DELETE FROM student_age_evidence WHERE delete_after < now();
  DELETE FROM student_authorization WHERE delete_after < now();
  DELETE FROM vpc_request WHERE delete_after < now();
  DELETE FROM parent_assurance WHERE delete_after < now();
END;
$$;

ALTER TABLE age_screen_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_email_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_rate_limit ENABLE ROW LEVEL SECURITY;
ALTER TABLE parent_assurance ENABLE ROW LEVEL SECURITY;
ALTER TABLE vpc_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_authorization ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_age_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_claim_token ENABLE ROW LEVEL SECURITY;
ALTER TABLE stripe_webhook_event ENABLE ROW LEVEL SECURITY;
