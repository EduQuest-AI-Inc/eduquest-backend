# Supabase Table Reference

Quick reference for all 28 tables in the EduQuest Supabase database, grouped by domain.

See [RPC_FUNCTIONS.md](RPC_FUNCTIONS.md) for stored procedures called via PostgREST `rpc/`.

**RLS identity expression:** All policies use `(auth.jwt() ->> 'sub')` — reads the JWT `sub` claim as text, directly matching `user_id` values. Do **not** use `auth.uid()` — it casts to UUID and silently returns null for username-format IDs.

---

## Table of Contents

**Identity**

1. [user](#user) — shared account record for all roles
2. [student](#student) — student-specific profile fields
3. [teacher](#teacher) — teacher-specific profile fields
4. [parent](#parent) — parent-specific profile fields

**Courses & Enrollment**

5. [period](#period) — a class period owned by a teacher or parent
6. [enrollment](#enrollment) — student ↔ period membership
7. [parent_invite](#parent_invite) — invite codes for parents to link to a student and view their progress
8. [period_schedule](#period_schedule) — per-period schedule JSON, quest-enabled weeks, OpenAI file reference

**Curriculum**

9. [week](#week) — week rows within a period (start/end dates)
10. [lesson](#lesson) — a lesson belonging to a week within a period
11. [lesson_pptx](#lesson_pptx) — per-lesson PowerPoint generation state + S3 reference
12. [concept](#concept) — a concept taught in a lesson, with rich metadata
13. [skill](#skill) — a measurable skill for a period with mastery config
14. [concept_skill](#concept_skill) — junction: which concepts develop which skills

**File Deduplication**

15. [material_files](#material_files) — dedup registry: SHA-256 hash → OpenAI file + vector store

**AI Conversations**

16. [conversation](#conversation) — general AI chat session metadata
17. [ltg_conversation](#ltg_conversation) — long-term goal chat session per student/period

**Quests & Skill Tracking**

18. [quest](#quest) — individual student quest assignment
19. [student_skill_mastery](#student_skill_mastery) — per-skill mastery record per student/period
20. [aggregated_metrics](#aggregated_metrics) — weekly class-wide skill percentage rollups

**Student Goals**

21. [student_long_term_goal](#student_long_term_goal) — student's long-term learning goal per period

**Auth & Sessions**

22. [session](#session) — active JWT sessions
23. [password_reset_token](#password_reset_token) — single-use tokens for password reset
24. [password_reset_rate_limit](#password_reset_rate_limit) — rate-limit counters for reset requests

**Onboarding**

25. [waitlist](#waitlist) — teacher pilot study waitlist

**Billing**

26. [membership](#membership) — trial + Stripe subscription record per teacher/parent

**Marketplace**

27. [marketplace_listing](#marketplace_listing) — published period listings in the resource marketplace

**Feedback**

28. [user_feedback](#user_feedback) — in-app feedback messages submitted by users

---

## Identity

### `user`

> Shared identity record for every account. The `student`, `teacher`, and `parent` tables hold only role-specific fields and FK to this table.

| Field            | Type | Constraints | Notes                                    |
| ---------------- | ---- | ----------- | ---------------------------------------- |
| `user_id`    | text | PK       |                                          |
| `first_name` | text | NOT NULL |                                          |
| `last_name`  | text | NOT NULL |                                          |
| `email`      | text | NOT NULL |                                          |
| `password`   | text        | NOT NULL | Hashed (bcrypt)                        |
| `phone_number` | text      | nullable |                                          |
| `last_login` | timestamptz | nullable |                                          |
| `role`       | text        | NOT NULL | `"student"` \| `"teacher"` \| `"parent"` |
| `created_at` | timestamptz | NOT NULL | Account creation time (DEFAULT now())    |
| `login_disabled` | boolean | NOT NULL DEFAULT false | Set true to block login without deleting account |
| `supabase_auth_id` | uuid | nullable, UNIQUE | Supabase Auth UUID; null until backfilled on first login after Phase 1 deploy |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

---

### `student`

> Role-specific fields for student accounts. One row per student, FK to `user`.

| Field                | Type      | Constraints | Notes                                   |
| -------------------- | --------- | ----------- | --------------------------------------- |
| `user_id`            | text      | PK → `user` |                                         |
| `grade`              | integer   | nullable    | Grade level (e.g. `9`)                  |
| `strength`           | text[]  | nullable    | Self-reported strengths                 |
| `weakness`           | text[]  | nullable    | Self-reported weaknesses                |
| `interest`           | text[]  | nullable    | Self-reported interests                 |
| `learning_style`     | text[]  | nullable    | Self-reported learning styles (array)   |
| `completed_tutorial` | boolean   | NOT NULL DEFAULT false | Whether the onboarding tutorial is done |
| `school_name`        | text      | nullable    |                                         |
| `account_status`     | text      | NOT NULL DEFAULT 'active' | `"active"` \| `"unclaimed"` — unclaimed accounts are created by a parent |
| `created_by_parent_id` | text    | nullable    | FK → `user.user_id`; set when a parent creates the student account |
| `claimed_at`         | timestamptz | nullable  | Timestamp when an unclaimed student account is claimed by the student |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| SELECT        | Parent of student (EXISTS parent where sub ∈ `linked_student_ids`) |
| SELECT        | Period owner (EXISTS enrollment JOIN period where `owner_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

---

### `teacher`

> Role-specific fields for teacher accounts. One row per teacher, FK to `user`.

| Field            | Type      | Constraints | Notes                           |
| ---------------- | --------- | ----------- | ------------------------------- |
| `user_id`        | text      | PK → `user` |                                 |
| `pilot_approved` | boolean   | NOT NULL    | Whether teacher is in the pilot |
| `school_name`    | text      | nullable    |                                 |
| `canvas_api_url` | text      | nullable    | Canvas LMS base URL             |
| `canvas_api_key` | text      | nullable    | Canvas personal access token    |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

---

### `parent`

> Role-specific fields for parent accounts. One row per parent, FK to `user`.

| Field                | Type      | Constraints | Notes                                                            |
| -------------------- | --------- | ----------- | ---------------------------------------------------------------- |
| `user_id`            | text      | PK → `user` |                                                                  |
| `linked_student_ids` | text[]  | nullable    | `user_id`s of linked student accounts                            |
| `vpc_verified_at`    | timestamptz | nullable    | COPPA 2025 compliance — set when parent accepts a student invite |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

---

## Courses & Enrollment

### `period`

> A class period created by a teacher or parent. Holds course metadata and Canvas/OpenAI integration references.

| Field                | Type      | Constraints | Notes                                     |
| -------------------- | --------- | ----------- | ----------------------------------------- |
| `period_id`          | text      | PK          |                                           |
| `name`               | text      | NOT NULL    | Display name for the period               |
| `owner_id`           | text      | NOT NULL    | FK → `user.user_id` (teacher or parent)   |
| `vector_store_id`         | text    | nullable    | OpenAI vector store ID for period-specific content (Canvas JSON, schedule JSON) |
| `file_vector_store_ids`   | text[]  | NOT NULL DEFAULT '{}' | Per-file vector store IDs for uploaded course materials (deduped across periods) |
| `file_urls`               | text[]  | NOT NULL DEFAULT '{}' | S3 URLs of uploaded course files          |
| `canvas_course_id`        | integer | nullable    | Canvas course ID for LMS sync             |
| `canvas_course_name` | text      | nullable    |                                           |
| `start_date`         | date      | nullable    |                                           |
| `end_date`           | date      | nullable    |                                           |
| `grade_level`        | text      | nullable    | Grade level of the course, e.g. "9", "AP", "College" |
| `mastery_threshold`  | float4    | nullable, default 0.8 | Score (0.0–1.0) required to flip mastered = true; applies to all weeks in the period |
| `course_description` | text      | nullable    | Teacher-provided description used when no files are uploaded |
| `course_metadata`    | jsonb     | nullable    | Structured class metadata: learning_objectives, primary_standard, additional_standards, specific_standard_codes |
| `processing_status`  | text      | NOT NULL DEFAULT 'ready' | `pending` while files process; `ready` on success; `failed` on error |
| `status`             | text      | NOT NULL DEFAULT 'pending' | Curriculum lifecycle: `"pending"` → `"draft"` (bot wrote rows) → `"approved"` (teacher confirmed) |
| `is_summer_quest`    | boolean   | NOT NULL DEFAULT false | `true` if this period is a summer quest; `false` for a normal class |
| `forked_from_period_id` | text   | nullable    | FK → `period.period_id`; set when this period was forked from a marketplace listing |
| `created_at`         | timestamptz | NOT NULL    |                                           |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Owner (`owner_id = sub`) |
| SELECT        | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| UPDATE        | Owner (`owner_id = sub`) |
| INSERT/DELETE | FastAPI only |

---

### `enrollment`

> Maps a student into a class period for a given semester. Composite PK on `(user_id, period_id)`.

| Field           | Type      | Constraints               | Notes              |
| --------------- | --------- | ------------------------- | ------------------ |
| `user_id`       | text      | PK (composite) → `user`   |                    |
| `period_id`     | text      | PK (composite) → `period` |                    |
| `semester`      | text      | NOT NULL                  | e.g. `"Fall 2025"` |
| `enrolled_at`   | timestamptz | NOT NULL                  | Auto-set on insert |
| `enrollment_id` | uuid      | UNIQUE                    | Surrogate ID       |

**RLS:** Enabled

| Operation | Who  |
| --------- | ---- |
| SELECT    | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT    | Enrolled student (self — `user_id = sub`) |
| INSERT    | Self only (`user_id = sub` WITH CHECK) |
| DELETE    | Self only (`user_id = sub`) |

### `period_schedule`

> Per-period schedule configuration. Stores the raw schedule JSON (uploaded or Canvas-synced), the OpenAI file ID for that JSON (used in the vector store), and which week numbers have quests enabled.

| Field                    | Type        | Constraints                      | Notes                                               |
| ------------------------ | ----------- | -------------------------------- | --------------------------------------------------- |
| `period_id`              | text        | PK → `period`                    |                                                     |
| `schedule_json`          | jsonb       | nullable                         | Raw schedule data (Canvas or teacher-uploaded)      |
| `schedule_openai_file_id` | text       | nullable                         | OpenAI Files API ID for the schedule JSON           |
| `quest_enabled_weeks`    | integer[]   | NOT NULL DEFAULT '{}'            | Week numbers for which quests are generated         |
| `created_at`             | timestamptz | NOT NULL DEFAULT now()           |                                                     |
| `last_updated_at`        | timestamptz | NOT NULL DEFAULT now()           | Updated on every write                              |

**RLS:** Enabled

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

### `parent_invite`

> Single-use invite codes that let a parent link to a student account. Once redeemed, the parent gains read access to that student's grades, skill mastery, and quest progress — the same view a teacher has for an enrolled student.

| Field        | Type      | Constraints | Notes                               |
| ------------ | --------- | ----------- | ----------------------------------- |
| `code`       | text      | PK          | 8-char random token sent to parent  |
| `user_id`    | text      | NOT NULL    | FK → `user.user_id` (the student)   |
| `expires_at` | timestamptz | NOT NULL    | Default: 24 hours from creation     |
| `used`       | boolean     | NOT NULL    | Flipped to `true` on redemption     |
| `created_at` | timestamptz | NOT NULL    |                                     |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Parent creator (`user_id = sub`) — note: `user_id` here is the **parent**, not the student |
| INSERT/UPDATE/DELETE | FastAPI only — invite creation and redemption always go through the service role |

---

## Curriculum

### `week`

> One row per week within a period. Written by the curriculum bot; referenced by `lesson`.

| Field         | Type    | Constraints               | Notes                        |
| ------------- | ------- | ------------------------- | ---------------------------- |
| `period_id`   | text    | PK (composite) → `period` |                              |
| `week_number` | integer | PK (composite)            | 1-based week index           |
| `week_start`  | date    | nullable                  | First day of the week        |
| `week_end`    | date    | nullable                  | Last day of the week         |

**RLS:** Enabled

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| SELECT               | Parent (EXISTS parent where sub ∈ `linked_student_ids` AND student enrolled in period) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

### `lesson`

> A named lesson belonging to a specific week in a period.

| Field         | Type    | Constraints                                  | Notes                      |
| ------------- | ------- | -------------------------------------------- | -------------------------- |
| `lesson_id`   | uuid    | PK DEFAULT gen_random_uuid()                 | Stable surrogate reference |
| `period_id`   | text    | NOT NULL → `period`                          |                            |
| `lesson_name` | text    | NOT NULL                                     |                            |
| `week_number` | integer | NOT NULL → FK `week(period_id, week_number)` |                            |

**RLS:** Enabled

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

### `lesson_pptx`

> Per-lesson PowerPoint generation job state and S3 reference. One row per lesson, written when a curriculum is approved.

| Field        | Type        | Constraints                      | Notes                                           |
| ------------ | ----------- | -------------------------------- | ----------------------------------------------- |
| `pptx_id`    | uuid        | PK DEFAULT gen_random_uuid()     |                                                 |
| `lesson_id`  | uuid        | NOT NULL FK → `lesson.lesson_id` |                                                 |
| `period_id`  | text        | NOT NULL FK → `period`           | Denormalized for RLS                            |
| `status`     | text        | NOT NULL DEFAULT 'pending'       | `pending` \| `generating` \| `done` \| `failed` |
| `s3_key`       | text        | nullable                         | Null until PPTX generation succeeds             |
| `html_key`     | text        | nullable                         | S3 key for the HTML version of the lesson slides |
| `attempt_count`| integer     | NOT NULL DEFAULT 0               | Incremented on each generation attempt; capped at 3 |
| `created_at`   | timestamptz | NOT NULL DEFAULT now()           |                                                 |
| `updated_at`   | timestamptz | NOT NULL DEFAULT now()           | Updated on every status change                  |

**RLS:** Enabled

| Operation     | Who                                                        |
| ------------- | ---------------------------------------------------------- |
| SELECT        | Period owner (EXISTS period where `owner_id = sub`)        |
| SELECT        | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| SELECT        | Parent of enrolled student (EXISTS parent → enrollment)    |
| INSERT/UPDATE | FastAPI only                                               |

---

### `concept`

> A concept taught within a lesson. Rich metadata fields populated by the curriculum bot; editable by the teacher before approval.

| Field                  | Type        | Constraints                               | Notes                                     |
| ---------------------- | ----------- | ----------------------------------------- | ----------------------------------------- |
| `period_id`            | text        | PK (composite) → `period`                 |                                           |
| `concept_name`         | text        | PK (composite)                            |                                           |
| `lesson_id`            | uuid        | NOT NULL → FK `lesson.lesson_id`          | Direct FK to the lesson (preferred over lesson_name join) |
| `lesson_name`          | text        | NOT NULL → FK `lesson(period_id, lesson_name)` |                                      |
| `description`          | text        | nullable                                  | Plain-text summary of the concept         |
| `prerequisites`        | jsonb       | nullable                                  | List of prerequisite concepts/skills      |
| `common_misconceptions`| jsonb       | nullable                                  | Common student errors                     |
| `key_takeaways`        | jsonb       | nullable                                  | Core points to remember                   |
| `metadata`             | jsonb       | nullable                                  | Arbitrary extra data from the bot         |
| `created_at`           | timestamptz | NOT NULL DEFAULT now()                    |                                           |
| `last_updated_at`      | timestamptz | NOT NULL DEFAULT now()                    | Set on every write                        |

**RLS:** Enabled

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

### `skill`

> A measurable skill scoped to a period. Defines mastery config and optional taxonomy metadata.

| Field               | Type    | Constraints               | Notes                                          |
| ------------------- | ------- | ------------------------- | ---------------------------------------------- |
| `period_id`         | text    | PK (composite) → `period` |                                                |
| `skill_name`        | text    | PK (composite)            |                                                |
| `description`       | text    | nullable                  |                                                |
| `bloom_level`       | text    | nullable                  | Bloom's taxonomy level (e.g. `"Apply"`)        |
| `difficulty`        | text    | nullable                  | e.g. `"beginner"`, `"intermediate"`, `"advanced"` |
| `mastery_threshold` | float   | NOT NULL DEFAULT 0.8      | Score (0.0–1.0) required to mark mastered      |
| `mastery_criteria`  | jsonb   | nullable                  | Detailed rubric criteria for mastery           |
| `metadata`          | jsonb   | nullable                  | Arbitrary extra data from the bot              |

**RLS:** Enabled

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

### `concept_skill`

> Junction table mapping concepts to the skills they develop. One row per (period, concept, skill) triple.

| Field          | Type | Constraints                                          | Notes |
| -------------- | ---- | ---------------------------------------------------- | ----- |
| `period_id`    | text | PK (composite)                                       |       |
| `concept_name` | text | PK (composite) → FK `concept(period_id, concept_name)` ON DELETE CASCADE |       |
| `skill_name`   | text | PK (composite) → FK `skill(period_id, skill_name)` ON DELETE CASCADE |       |

**RLS:** Enabled

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

## AI Conversations

### `conversation`

> Metadata for a general AI chat session (profile, update, etc.) between a student/teacher and an agent.

| Field               | Type      | Constraints | Notes                                               |
| ------------------- | --------- | ----------- | --------------------------------------------------- |
| `conversation_id`   | text      | PK          |                                                     |
| `user_id`           | text      | NOT NULL    | FK → `user.user_id`                                 |
| `conversation_type` | text      | NOT NULL    | e.g. `"profile"`, `"update"`                        |
| `period_id`         | text      | nullable    |                                                     |
| `created_at`        | timestamptz | NOT NULL    |                                                     |
| `last_response_id`  | text        | nullable    | Last OpenAI response ID — used for message chaining |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

### `ltg_conversation`

> Tracks the long-term goal AI conversation for each (student, period) pair. One row per student per period.

| Field              | Type        | Constraints               | Notes                                               |
| ------------------ | ----------- | ------------------------- | --------------------------------------------------- |
| `user_id`          | text        | PK (composite) → `user`   |                                                     |
| `period_id`        | text        | PK (composite) → `period` |                                                     |
| `conversation_id`  | text        | NOT NULL                  | OpenAI conversation ID                              |
| `created_at`       | timestamptz | NOT NULL                  |                                                     |
| `last_response_id` | text      | nullable                  | Last OpenAI response ID — used for message chaining |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | The student (self — `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

## Quests & Skill Tracking

### `quest`

> A single quest assignment for one student in one period for a given week. Includes AI-generated instructions, rubric, and grading output.

| Field             | Type         | Constraints | Notes                                                     |
| ----------------- | ------------ | ----------- | --------------------------------------------------------- |
| `quest_id`        | uuid         | PK          |                                                           |
| `user_id`         | text         | NOT NULL    | FK → `user.user_id` (the student)                         |
| `period_id`       | text         | NOT NULL    | FK → `period.period_id`                                   |
| `description`     | text         | NOT NULL    | Short summary of the quest                                |
| `skills`          | text         | NOT NULL    | Skills this quest targets                                 |
| `week`            | integer      | NOT NULL    | Week number within the period                             |
| `instructions`    | jsonb        | NOT NULL    | Step-by-step completion instructions                      |
| `rubric`          | json         | NOT NULL    | Grading criteria keyed by skill                           |
| `status`          | quest_status | NOT NULL    | Enum: `"not_started"` \| `"in_progress"` \| `"completed"` |
| `grade`           | jsonb        | nullable    | Grading output — see shape below                          |
| `feedback`        | text         | nullable    | AI or teacher feedback                                    |
| `due_date`        | timestamptz  | nullable    |                                                           |
| `completed_steps` | jsonb        | nullable DEFAULT '[]' | Array tracking which steps the student has completed |
| `created_at`      | timestamptz  | NOT NULL    |                                                           |
| `last_updated_at` | timestamptz  | NOT NULL    | Auto-updated on every write                               |

**`grade` JSONB shape:**

```json
{
  "detailed_grade": { "<criterion>": <int>, ... },
  "overall_score": <int>
}
```

- `detailed_grade` — per-criterion scores produced by the grading agent (e.g. `{"Clarity": 18, "Analysis": 22}`)
- `overall_score` — total points rolled up from all criteria

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | The student (`user_id = sub`) |
| SELECT        | Period owner (EXISTS enrollment JOIN period where `owner_id = sub`) |
| SELECT        | Parent (EXISTS parent where sub ∈ `linked_student_ids`) |
| UPDATE        | Student — `status` column only (enforced at FastAPI layer, not RLS) |
| UPDATE        | Period owner — `grade`/`feedback` columns only (enforced at FastAPI layer, not RLS) |
| INSERT/DELETE | FastAPI only |

---

### `student_skill_mastery`

> Tracks whether a student has mastered each skill in a period. Written through `KnowledgeGraphService.update_mastery` (one row per (student, period, skill)). Read by `KnowledgeGraphService.get_graph` and the agent function tools in `bots/tools/knowledge_graph_tools.py`. Wiring from the grading pipeline is a follow-up.

| Field        | Type      | Constraints               | Notes                               |
| ------------ | --------- | ------------------------- | ----------------------------------- |
| `student_id` | text      | PK (composite) → `user`   |                                     |
| `period_id`  | text      | PK (composite) → `period` |                                     |
| `skill_name` | text      | PK (composite)            |                                     |
| `mastered`   | boolean   | NOT NULL DEFAULT false    |                                     |
| `score`      | numeric     | nullable                  | Latest aggregated score (0.0 – 1.0) |
| `updated_at` | timestamptz | NOT NULL                  |                                     |

**RLS:** Enabled — note: PK column is `student_id`, not `user_id`

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | The student (`student_id = sub`) |
| SELECT        | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT        | Parent (EXISTS parent where sub ∈ `linked_student_ids` and `student_id` matches) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

### `aggregated_metrics`

> Weekly class-wide skill percentage rollups. Used by the teacher dashboard to track class progress over time.

| Field        | Type        | Constraints             | Notes                                        |
| ------------ | ----------- | ----------------------- | -------------------------------------------- |
| `period_id`  | text        | PRIMARY KEY, NOT NULL   | FK → `period.period_id`                      |
| `week`       | integer     | PRIMARY KEY, NOT NULL   | Week number                                  |
| `skill_name` | text        | PRIMARY KEY, NOT NULL   | The skill being tracked                      |
| `percentage` | numeric     | NOT NULL                | Fraction of students who mastered this skill |
| `updated_at` | timestamptz | NOT NULL                |                                              |

**RLS:** Disabled — FastAPI service role only

---

## Student Goals

### `student_long_term_goal`

> Stores one free-text long-term goal per student per period. Upserted whenever the student updates their goal in the LTG conversation.

| Field        | Type      | Constraints               | Notes                           |
| ------------ | --------- | ------------------------- | ------------------------------- |
| `user_id`    | text      | PK (composite) → `user`   |                                 |
| `period_id`  | text      | PK (composite) → `period` |                                 |
| `goal_text`  | text      | NOT NULL                  | Student's stated long-term goal |
| `updated_at` | timestamptz | NOT NULL                  | Set on every upsert             |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | The student (`user_id = sub`) |
| SELECT        | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT        | Parent (EXISTS parent where sub ∈ `linked_student_ids` and `user_id` matches) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

## Auth & Sessions

### `session`

> Active auth sessions. Each JWT token is a row; validated on every protected API call.

| Field        | Type      | Constraints | Notes                                          |
| ------------ | --------- | ----------- | ---------------------------------------------- |
| `auth_token` | text      | PK          | JWT token value                                |
| `user_id`    | text      | NOT NULL    | FK → `user.user_id`                            |
| `role`       | user_role | NOT NULL    | Enum: `"student"` \| `"teacher"` \| `"parent"` |
| `expires_at` | timestamptz | NOT NULL    | Token expiry (default: 1 hour from creation)   |

**RLS:** Enabled

| Operation | Who  |
| --------- | ---- |
| SELECT    | Self (`user_id = sub`) |
| DELETE    | Self (`user_id = sub`) |
| INSERT    | FastAPI only — JWT doesn't exist yet at login time |

---

### `password_reset_token`

> Single-use password reset tokens. Stored as SHA-256 hashes; support attempt counting and burning on abuse.

| Field        | Type      | Constraints | Notes                                          |
| ------------ | --------- | ----------- | ---------------------------------------------- |
| `token_hash` | text      | PK          | SHA-256 hash of the raw token sent to the user |
| `user_id`    | text      | NOT NULL    | FK → `user.user_id`                            |
| `email`      | text      | NOT NULL    | Email at time of request                       |
| `created_at` | timestamptz | NOT NULL    |                                                |
| `expires_at` | timestamptz | NOT NULL    | Auto-expires after 45 minutes                  |
| `used_at`    | timestamptz | nullable    | Set when the token is consumed                 |
| `burned_at`  | timestamptz | nullable    | Set when the token is invalidated due to abuse |
| `attempts`   | integer   | NOT NULL    | Confirmation attempts; token burns after 5     |
| `request_ip` | inet      | nullable    |                                                |
| `user_agent` | text      | nullable    |                                                |

**RLS:** Disabled — FastAPI service role only

---

### `password_reset_rate_limit`

> Request counters for three-tier rate limiting on the password reset endpoint (IP+email, IP-only, email cooldown).

| Field        | Type      | Constraints | Notes                                             |
| ------------ | --------- | ----------- | ------------------------------------------------- |
| `key`        | text      | PK          | Composite key — format varies by tier (see below) |
| `count`      | integer   | NOT NULL    | Number of requests in the current window          |
| `expires_at` | timestamptz | NOT NULL    | Window expiry; row is stale after this            |

**Key formats by tier:**

| Tier           | Format                                     | Limit          |
| -------------- | ------------------------------------------ | -------------- |
| IP + email     | `ip:{ip}\|email:{email}\|w:{window_start}` | 5 per 15 min   |
| IP only        | `ip:{ip}\|w:{window_start}`                | 20 per 15 min  |
| Email cooldown | `cooldown:email:{email}`                   | 5 min cooldown |

**RLS:** Disabled — FastAPI service role only

---

## Onboarding

### `waitlist`

> Teacher pilot study waitlist with referral tracking. Managed by the `/pilot-waitlist` API.

| Field           | Type      | Constraints | Notes                             |
| --------------- | --------- | ----------- | --------------------------------- |
| `waitlist_id`   | uuid      | PK          |                                   |
| `user_id`       | text      | nullable    | FK → `user.user_id` if registered |
| `email`         | text      | NOT NULL    |                                   |
| `joined_at`     | timestamptz | NOT NULL    |                                   |
| `position`      | integer   | NOT NULL    | Queue position                    |
| `referral_code` | text      | nullable    | Unique 8-char code for sharing    |
| `referred_by`   | text      | nullable    | `user_id` of the referrer         |
| `status`        | text      | NOT NULL    | `"pending"` \| `"approved"`       |

**RLS:** Disabled — public signup list, no per-user scoping needed

---

## Billing

### `membership`

> Trial and Stripe subscription record for teacher and parent accounts. One row per user; students never have a row. Managed exclusively by `MembershipService`.

| Field                     | Type              | Constraints              | Notes                                                            |
| ------------------------- | ----------------- | ------------------------ | ---------------------------------------------------------------- |
| `user_id`                 | text              | PK → `user`              |                                                                  |
| `role`                    | text              | NOT NULL                 | `"teacher"` \| `"parent"` only                                  |
| `status`                  | membership_status | NOT NULL DEFAULT 'none'  | Enum: `none` \| `trialing` \| `active` \| `past_due` \| `canceled` \| `expired` |
| `plan`                    | membership_plan   | nullable                 | Enum: `starter` \| `growth` \| `pro`                            |
| `class_limit`             | integer           | nullable                 | Max periods allowed under current plan                          |
| `students_per_class_limit` | integer          | nullable                 | Max students per period under current plan                      |
| `trial_started_at`        | timestamptz       | nullable                 |                                                                  |
| `trial_ends_at`           | timestamptz       | nullable                 |                                                                  |
| `reminder_sent_at`        | timestamptz       | nullable                 | When the trial-ending reminder email was sent                   |
| `stripe_customer_id`      | text              | nullable                 |                                                                  |
| `stripe_subscription_id`  | text              | nullable                 |                                                                  |
| `stripe_price_id`         | text              | nullable                 |                                                                  |
| `current_period_end`      | timestamptz       | nullable                 | Stripe billing period end                                        |
| `cancel_at_period_end`    | boolean           | NOT NULL DEFAULT false   | Stripe cancel-at-period-end flag                                |
| `created_at`              | timestamptz       | NOT NULL DEFAULT now()   |                                                                  |
| `updated_at`              | timestamptz       | NOT NULL DEFAULT now()   | Must be kept non-null; use `default_factory` in Pydantic model  |
| `delete_after`            | timestamptz       | nullable                 | Soft-delete timestamp; row is eligible for cleanup after this   |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

---

## Marketplace

### `marketplace_listing`

> Published period listings in the resource marketplace. Tracks publish state, fork count, and tags. Managed by `MarketplaceListingDAO`.

| Field          | Type        | Constraints              | Notes                                                  |
| -------------- | ----------- | ------------------------ | ------------------------------------------------------ |
| `listing_id`   | uuid        | PK DEFAULT gen_random_uuid() |                                                    |
| `period_id`    | text        | NOT NULL → `period`      |                                                        |
| `published_by` | text        | NOT NULL → `user`        | FK → `user.user_id` (the teacher who published)        |
| `tags`         | text[]      | nullable DEFAULT '{}'    | Subject or grade tags for filtering                    |
| `fork_count`   | integer     | NOT NULL DEFAULT 0       | Number of times this listing has been forked           |
| `is_published` | boolean     | NOT NULL DEFAULT true    | `false` to soft-hide from the marketplace              |
| `created_at`   | timestamptz | NOT NULL DEFAULT now()   |                                                        |
| `updated_at`   | timestamptz | NOT NULL DEFAULT now()   |                                                        |
| `delete_after` | timestamptz | nullable                 | Soft-delete timestamp                                  |

**RLS:** Disabled — FastAPI service role only

---

## Feedback

### `user_feedback`

> In-app feedback messages submitted by students or teachers. Read by the FastAPI feedback router.

| Field         | Type        | Constraints              | Notes                              |
| ------------- | ----------- | ------------------------ | ---------------------------------- |
| `feedback_id` | uuid        | PK DEFAULT gen_random_uuid() |                                |
| `user_id`     | text        | NOT NULL → `user`        |                                    |
| `message`     | text        | NOT NULL                 | Raw feedback text from the user    |
| `created_at`  | timestamptz | NOT NULL DEFAULT now()   |                                    |

**RLS:** Disabled — FastAPI service role only

---

## Quick Reference

| Table                       | PK                                    | Purpose                                   |
| --------------------------- | ------------------------------------- | ----------------------------------------- |
| `user`                      | `user_id`                             | Shared identity for all account types     |
| `student`                   | `user_id`                             | Student profile fields                    |
| `teacher`                   | `user_id`                             | Teacher profile fields                    |
| `parent`                    | `user_id`                             | Parent profile + linked student IDs       |
| `period`                    | `period_id`                           | Class period owned by a teacher or parent (`status`: pending→draft→approved) |
| `enrollment`                | `(user_id, period_id)`                | Student ↔ period membership               |
| `session`                   | `auth_token`                          | Active JWT sessions                       |
| `quest`                     | `quest_id`                            | Per-student weekly quest assignment       |
| `student_skill_mastery`     | `(student_id, period_id, skill_name)` | Per-skill mastery record                  |
| `aggregated_metrics`        | `(period_id, week, skill_name)`       | Weekly class-wide skill rollups           |
| `student_long_term_goal`    | `(user_id, period_id)`                | Student's long-term goal per period       |
| `conversation`              | `conversation_id`                     | General AI chat session metadata          |
| `ltg_conversation`          | `(user_id, period_id)`                | Long-term goal chat session per student   |
| `password_reset_token`      | `token_hash`                          | Single-use password reset tokens          |
| `password_reset_rate_limit` | `key`                                 | Rate-limit counters for reset requests    |
| `waitlist`                  | `waitlist_id`                         | Teacher pilot study waitlist              |
| `parent_invite`             | `code`                                | Invite codes for parents to link to a student and view their progress |
| `week`                      | `(period_id, week_number)`            | Week rows within a period (start/end dates)       |
| `lesson`                    | `lesson_id`                           | Lesson belonging to a week within a period        |
| `lesson_pptx`               | `pptx_id`                             | Per-lesson PowerPoint generation state + S3 ref   |
| `concept`                   | `(period_id, concept_name)`           | Concept taught in a lesson with rich metadata     |
| `skill`                     | `(period_id, skill_name)`             | Measurable skill with mastery config              |
| `concept_skill`             | `(period_id, concept_name, skill_name)` | Junction: concepts → skills they develop        |
| `material_files`            | `file_hash`                           | SHA-256 dedup registry for uploaded course files |
| `period_schedule`           | `period_id`                           | Schedule JSON, OpenAI file ID, quest-enabled weeks |
| `membership`                | `user_id`                             | Trial + Stripe subscription for teachers/parents  |
| `marketplace_listing`       | `listing_id`                          | Published period in the resource marketplace      |
| `user_feedback`             | `feedback_id`                         | In-app feedback messages from users               |

---

## File Deduplication

### `material_files`

> Deduplication registry for uploaded course files. Each unique file (by SHA-256 hash) is stored once with its own OpenAI vector store. Periods reference these shared vector stores via `period.file_vector_store_ids`.

| Field              | Type        | Constraints | Notes                                            |
| ------------------ | ----------- | ----------- | ------------------------------------------------ |
| `file_hash`        | text        | PK          | SHA-256 hex of the original file bytes           |
| `openai_file_id`   | text        | NOT NULL UNIQUE | OpenAI Files API ID                          |
| `vector_store_id`  | text        | NOT NULL UNIQUE | Per-file vector store; embeddings live here  |
| `created_at`       | timestamptz | NOT NULL    | Auto-set on first upload                         |

**RLS:** Enabled

| Operation     | Who  |
| ------------- | ---- |
| INSERT/UPDATE/DELETE | FastAPI only |
