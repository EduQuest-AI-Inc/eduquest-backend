-- ============================================================
-- Migration: 010_rls_policies.sql
-- Enable Row Level Security on all sensitive tables.
-- Identity expression: (auth.jwt() ->> 'sub') reads the JWT
-- 'sub' claim as text, directly matching user_id values.
-- Do NOT use auth.uid() — it casts to UUID and returns null
-- for username-format user IDs.
--
-- FastAPI backend uses SUPABASE_SERVICE_ROLE_KEY and bypasses
-- all RLS policies by design. These policies only fire for
-- direct frontend Supabase queries using the anon key + user JWT.
-- ============================================================

-- ============================================================
-- TABLES EXPLICITLY EXCLUDED FROM RLS
-- ============================================================
-- waitlist          — public signup, no per-user scoping
-- password_reset_token      — FastAPI service role only
-- password_reset_rate_limit — FastAPI service role only
-- aggregated_metrics        — FastAPI service role only
-- ============================================================


-- ============================================================
-- TABLE: user
-- ============================================================
alter table "user" enable row level security;

create policy "user: self select"
  on "user"
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "user: self update"
  on "user"
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: student
-- ============================================================
alter table student enable row level security;

create policy "student: self select"
  on student
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "student: parent select"
  on student
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and student.user_id = any(parent.linked_student_ids)
    )
  );

create policy "student: period owner select"
  on student
  for select
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = student.user_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "student: self update"
  on student
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: teacher
-- ============================================================
alter table teacher enable row level security;

create policy "teacher: self select"
  on teacher
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "teacher: self update"
  on teacher
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: parent
-- ============================================================
alter table parent enable row level security;

create policy "parent: self select"
  on parent
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "parent: self update"
  on parent
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: period
-- ============================================================
alter table period enable row level security;

create policy "period: owner select"
  on period
  for select
  using (owner_id = (auth.jwt() ->> 'sub'));

create policy "period: enrolled student select"
  on period
  for select
  using (
    exists (
      select 1 from enrollment e
      where e.period_id = period.period_id
        and e.user_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "period: owner update"
  on period
  for update
  using (owner_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: period_schedule
-- ============================================================
alter table period_schedule enable row level security;

create policy "period_schedule: owner select"
  on period_schedule
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "period_schedule: owner insert"
  on period_schedule
  for insert
  with check (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "period_schedule: owner update"
  on period_schedule
  for update
  using (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );


-- ============================================================
-- TABLE: enrollment
-- ============================================================
alter table enrollment enable row level security;

create policy "enrollment: period owner select"
  on enrollment
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = enrollment.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "enrollment: enrolled student select"
  on enrollment
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

-- Student self-enrollment only — user_id must match the caller's sub.
create policy "enrollment: self insert"
  on enrollment
  for insert
  with check (user_id = (auth.jwt() ->> 'sub'));

create policy "enrollment: student delete"
  on enrollment
  for delete
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: quest  (formerly individual_quest, renamed migration 004)
-- Column-level restriction (student → status only, teacher →
-- grade/feedback only) is enforced at the FastAPI layer, not here.
-- ============================================================
alter table quest enable row level security;

create policy "quest: student select"
  on quest
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "quest: period owner select"
  on quest
  for select
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = quest.user_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "quest: parent select"
  on quest
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and quest.user_id = any(parent.linked_student_ids)
    )
  );

create policy "quest: student update"
  on quest
  for update
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "quest: period owner update"
  on quest
  for update
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = quest.user_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );


-- ============================================================
-- TABLE: student_skill_mastery
-- PK column is student_id (not user_id) — identity expression
-- compares against student_id.
-- ============================================================
alter table student_skill_mastery enable row level security;

create policy "student_skill_mastery: student select"
  on student_skill_mastery
  for select
  using (student_id = (auth.jwt() ->> 'sub'));

create policy "student_skill_mastery: period owner select"
  on student_skill_mastery
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = student_skill_mastery.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "student_skill_mastery: parent select"
  on student_skill_mastery
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and student_skill_mastery.student_id = any(parent.linked_student_ids)
    )
  );


-- ============================================================
-- TABLE: conversation
-- ============================================================
alter table conversation enable row level security;

create policy "conversation: self select"
  on conversation
  for select
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: student_long_term_goal
-- ============================================================
alter table student_long_term_goal enable row level security;

create policy "student_long_term_goal: student select"
  on student_long_term_goal
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "student_long_term_goal: period owner select"
  on student_long_term_goal
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = student_long_term_goal.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "student_long_term_goal: parent select"
  on student_long_term_goal
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and student_long_term_goal.user_id = any(parent.linked_student_ids)
    )
  );


-- ============================================================
-- TABLE: ltg_conversation
-- ============================================================
alter table ltg_conversation enable row level security;

create policy "ltg_conversation: student select"
  on ltg_conversation
  for select
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: parent_invite
-- user_id = the parent who created the invite (NOT the student).
-- Invite creation and redemption go through FastAPI service role.
-- Students never query this table directly.
-- ============================================================
alter table parent_invite enable row level security;

create policy "parent_invite: parent select"
  on parent_invite
  for select
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: session
-- INSERT omitted: JWT does not exist yet at login time;
-- session creation goes through FastAPI service role.
-- ============================================================
alter table session enable row level security;

create policy "session: self select"
  on session
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "session: self delete"
  on session
  for delete
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- INDEXES (add any missing; idx_enrollment_user_id,
-- idx_period_owner_id, idx_quest_user_period, and
-- idx_conversation_user_id already exist from migration 004)
-- ============================================================
create index if not exists idx_quest_user_id
  on quest(user_id);

create index if not exists idx_quest_period_id
  on quest(period_id);

-- GIN index for parent.linked_student_ids array lookups.
-- At current scale (1-5 children per parent) this is optional,
-- but add it now to avoid a future hot migration.
create index if not exists idx_parent_linked_student_ids
  on parent using gin(linked_student_ids);


-- ============================================================
-- VERIFICATION QUERIES (run in Supabase SQL editor to test)
-- ============================================================

-- Verify actual FK constraint names before running 011:
-- SELECT conname, conrelid::regclass, confrelid::regclass
-- FROM pg_constraint
-- WHERE contype = 'f'
--   AND conrelid::regclass::text IN (
--     'quest', 'enrollment', 'ltg_conversation',
--     'student_long_term_goal', 'parent_invite'
--   );

-- Impersonate a student:
-- select set_config(
--   'request.jwt.claims',
--   '{"sub": "johnsmith123", "role": "authenticated", "app_role": "student"}',
--   true
-- );
-- select * from quest;
-- Must return only rows where user_id = 'johnsmith123'

-- Impersonate a teacher:
-- select set_config(
--   'request.jwt.claims',
--   '{"sub": "msteacher456", "role": "authenticated", "app_role": "teacher"}',
--   true
-- );
-- select * from quest;
-- Must return only quests for students enrolled in msteacher456's periods

-- Impersonate a parent:
-- select set_config(
--   'request.jwt.claims',
--   '{"sub": "parentuser789", "role": "authenticated", "app_role": "parent"}',
--   true
-- );
-- select * from student;
-- Must return only students whose user_id is in parent.linked_student_ids
-- where parent.user_id = 'parentuser789'

-- Confirm service role still bypasses RLS (run as service role connection):
-- select * from quest;
-- Must return all rows
