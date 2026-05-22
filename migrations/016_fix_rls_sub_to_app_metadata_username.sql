-- ============================================================
-- Migration: 016_fix_rls_sub_to_app_metadata_username.sql
-- Replace (auth.jwt() ->> 'sub') with
-- (auth.jwt() -> 'app_metadata' ->> 'username') in every RLS
-- policy.
--
-- Background: the backend now issues Supabase native ES256 JWTs
-- where sub is a UUID, not the EduQuest username.  The username
-- is carried in app_metadata.username.  All user_id / owner_id /
-- student_id columns store usernames, so the old sub-based
-- expression silently matched nothing.
--
-- Production DAOs use the service-role key and bypass RLS; this
-- fix is only required for direct frontend queries with the anon
-- key + user JWT.
-- ============================================================


-- ============================================================
-- TABLE: user
-- ============================================================
drop policy if exists "user: self select" on "user";
create policy "user: self select"
  on "user"
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "user: self update" on "user";
create policy "user: self update"
  on "user"
  for update
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: student
-- ============================================================
drop policy if exists "student: self select" on student;
create policy "student: self select"
  on student
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "student: parent select" on student;
create policy "student: parent select"
  on student
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() -> 'app_metadata' ->> 'username')
        and student.user_id = any(parent.linked_student_ids)
    )
  );

drop policy if exists "student: period owner select" on student;
create policy "student: period owner select"
  on student
  for select
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = student.user_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "student: self update" on student;
create policy "student: self update"
  on student
  for update
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: teacher
-- ============================================================
drop policy if exists "teacher: self select" on teacher;
create policy "teacher: self select"
  on teacher
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "teacher: self update" on teacher;
create policy "teacher: self update"
  on teacher
  for update
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: parent
-- ============================================================
drop policy if exists "parent: self select" on parent;
create policy "parent: self select"
  on parent
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "parent: self update" on parent;
create policy "parent: self update"
  on parent
  for update
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: period
-- ============================================================
drop policy if exists "period: owner select" on period;
create policy "period: owner select"
  on period
  for select
  using (owner_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "period: enrolled student select" on period;
create policy "period: enrolled student select"
  on period
  for select
  using (
    exists (
      select 1 from enrollment e
      where e.period_id = period.period_id
        and e.user_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "period: owner update" on period;
create policy "period: owner update"
  on period
  for update
  using (owner_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: period_schedule
-- ============================================================
drop policy if exists "period_schedule: owner select" on period_schedule;
create policy "period_schedule: owner select"
  on period_schedule
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "period_schedule: owner insert" on period_schedule;
create policy "period_schedule: owner insert"
  on period_schedule
  for insert
  with check (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "period_schedule: owner update" on period_schedule;
create policy "period_schedule: owner update"
  on period_schedule
  for update
  using (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );


-- ============================================================
-- TABLE: enrollment
-- ============================================================
drop policy if exists "enrollment: period owner select" on enrollment;
create policy "enrollment: period owner select"
  on enrollment
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = enrollment.period_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "enrollment: enrolled student select" on enrollment;
create policy "enrollment: enrolled student select"
  on enrollment
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "enrollment: self insert" on enrollment;
create policy "enrollment: self insert"
  on enrollment
  for insert
  with check (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "enrollment: student delete" on enrollment;
create policy "enrollment: student delete"
  on enrollment
  for delete
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: quest
-- ============================================================
drop policy if exists "quest: student select" on quest;
create policy "quest: student select"
  on quest
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "quest: period owner select" on quest;
create policy "quest: period owner select"
  on quest
  for select
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = quest.user_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "quest: parent select" on quest;
create policy "quest: parent select"
  on quest
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() -> 'app_metadata' ->> 'username')
        and quest.user_id = any(parent.linked_student_ids)
    )
  );

drop policy if exists "quest: student update" on quest;
create policy "quest: student update"
  on quest
  for update
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "quest: period owner update" on quest;
create policy "quest: period owner update"
  on quest
  for update
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = quest.user_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );


-- ============================================================
-- TABLE: student_skill_mastery
-- ============================================================
drop policy if exists "student_skill_mastery: student select" on student_skill_mastery;
create policy "student_skill_mastery: student select"
  on student_skill_mastery
  for select
  using (student_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "student_skill_mastery: period owner select" on student_skill_mastery;
create policy "student_skill_mastery: period owner select"
  on student_skill_mastery
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = student_skill_mastery.period_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "student_skill_mastery: parent select" on student_skill_mastery;
create policy "student_skill_mastery: parent select"
  on student_skill_mastery
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() -> 'app_metadata' ->> 'username')
        and student_skill_mastery.student_id = any(parent.linked_student_ids)
    )
  );


-- ============================================================
-- TABLE: conversation
-- ============================================================
drop policy if exists "conversation: self select" on conversation;
create policy "conversation: self select"
  on conversation
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: student_long_term_goal
-- ============================================================
drop policy if exists "student_long_term_goal: student select" on student_long_term_goal;
create policy "student_long_term_goal: student select"
  on student_long_term_goal
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "student_long_term_goal: period owner select" on student_long_term_goal;
create policy "student_long_term_goal: period owner select"
  on student_long_term_goal
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = student_long_term_goal.period_id
        and p.owner_id = (auth.jwt() -> 'app_metadata' ->> 'username')
    )
  );

drop policy if exists "student_long_term_goal: parent select" on student_long_term_goal;
create policy "student_long_term_goal: parent select"
  on student_long_term_goal
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() -> 'app_metadata' ->> 'username')
        and student_long_term_goal.user_id = any(parent.linked_student_ids)
    )
  );


-- ============================================================
-- TABLE: ltg_conversation
-- ============================================================
drop policy if exists "ltg_conversation: student select" on ltg_conversation;
create policy "ltg_conversation: student select"
  on ltg_conversation
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: parent_invite
-- ============================================================
drop policy if exists "parent_invite: parent select" on parent_invite;
create policy "parent_invite: parent select"
  on parent_invite
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));


-- ============================================================
-- TABLE: session
-- ============================================================
drop policy if exists "session: self select" on session;
create policy "session: self select"
  on session
  for select
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));

drop policy if exists "session: self delete" on session;
create policy "session: self delete"
  on session
  for delete
  using (user_id = (auth.jwt() -> 'app_metadata' ->> 'username'));
