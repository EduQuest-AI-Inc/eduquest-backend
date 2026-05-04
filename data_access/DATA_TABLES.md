# Supabase Table Reference

Quick reference for all 18 tables in the EduQuest Supabase database, grouped by domain.

---

## Table of Contents

**Identity**

1. [user](#user) — shared account record for all roles
2. [student](#student) — student-specific profile fields
3. [teacher](#teacher) — teacher-specific profile fields
4. [parent](#parent) — parent-specific profile fields

**Courses & Enrollment**

5. [period](#period) — a class period owned by a teacher or parent
6. [period_schedule](#period_schedule) — AI-generated weekly schedule for a period
7. [enrollment](#enrollment) — student ↔ period membership
8. [parent_invite](#parent_invite) — invite codes for parents to link to a student and view their progress

**File Deduplication**

19. [material_files](#material_files) — dedup registry: SHA-256 hash → OpenAI file + vector store

**AI Conversations**

9. [conversation](#conversation) — general AI chat session metadata
10. [ltg_conversation](#ltg_conversation) — long-term goal chat session per student/period

**Quests & Skill Tracking**

11. [quest](#quest) — individual student quest assignment
12. [student_skill_mastery](#student_skill_mastery) — per-skill mastery record per student/period
13. [aggregated_metrics](#aggregated_metrics) — weekly class-wide skill percentage rollups

**Student Goals**

14. [student_long_term_goal](#student_long_term_goal) — student's long-term learning goal per period

**Auth & Sessions**

15. [session](#session) — active JWT sessions
16. [password_reset_token](#password_reset_token) — single-use tokens for password reset
17. [password_reset_rate_limit](#password_reset_rate_limit) — rate-limit counters for reset requests

**Onboarding**

18. [waitlist](#waitlist) — teacher pilot study waitlist

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
| `last_login` | timestamptz | nullable |                                          |
| `role`       | text        | NOT NULL | `"student"` \| `"teacher"` \| `"parent"` |
| `created_at` | timestamptz | NOT NULL | Account creation time (DEFAULT now())    |

---

### `student`

> Role-specific fields for student accounts. One row per student, FK to `user`.

| Field                | Type      | Constraints | Notes                                   |
| -------------------- | --------- | ----------- | --------------------------------------- |
| `user_id`            | text      | PK → `user` |                                         |
| `grade`              | integer   | NOT NULL    | Grade level (e.g. `9`)                  |
| `strength`           | text[]  | nullable    | Self-reported strengths                 |
| `weakness`           | text[]  | nullable    | Self-reported weaknesses                |
| `interest`           | text[]  | nullable    | Self-reported interests                 |
| `learning_style`     | text      | nullable    |                                         |
| `completed_tutorial` | boolean   | NOT NULL    | Whether the onboarding tutorial is done |
| `school_name`        | text      | nullable    |                                         |

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

---

### `parent`

> Role-specific fields for parent accounts. One row per parent, FK to `user`.

| Field                | Type      | Constraints | Notes                                                            |
| -------------------- | --------- | ----------- | ---------------------------------------------------------------- |
| `user_id`            | text      | PK → `user` |                                                                  |
| `linked_student_ids` | text[]  | nullable    | `user_id`s of linked student accounts                            |
| `vpc_verified_at`    | timestamptz | nullable    | COPPA 2025 compliance — set when parent accepts a student invite |

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
| `file_url`                | text[]  | nullable    | S3 URLs of uploaded course files          |
| `canvas_course_id`        | integer | nullable    | Canvas course ID for LMS sync             |
| `canvas_course_name` | text      | nullable    |                                           |
| `start_date`         | text      | nullable    |                                           |
| `end_date`           | text      | nullable    |                                           |
| `course_description` | text      | nullable    | Teacher-provided description used when no files are uploaded |
| `processing_status`  | text      | NOT NULL DEFAULT 'ready' | `pending` while files process; `ready` on success; `failed` on error |
| `created_at`         | timestamptz | NOT NULL    |                                           |

---

### `period_schedule`

> AI-generated weekly schedule for a period. Tracks which weeks have quests enabled and the associated OpenAI file.

| Field                     | Type      | Constraints   | Notes                                           |
| ------------------------- | --------- | ------------- | ----------------------------------------------- |
| `period_id`               | text      | PK → `period` |                                                 |
| `schedule_json`           | json      | NOT NULL      | Full AI-generated schedule payload              |
| `schedule_openai_file_id` | text      | nullable      | OpenAI Files API ID used to create the schedule |
| `quest_enabled_weeks`     | integer[] | nullable      | List of week numbers that have quests enabled   |
| `created_at`              | timestamptz | NOT NULL      |                                                 |
| `last_updated_at`         | timestamptz | NOT NULL      | Auto-updated on every write                     |

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

### `parent_invite`

> Single-use invite codes that let a parent link to a student account. Once redeemed, the parent gains read access to that student's grades, skill mastery, and quest progress — the same view a teacher has for an enrolled student.

| Field        | Type      | Constraints | Notes                               |
| ------------ | --------- | ----------- | ----------------------------------- |
| `code`       | text      | PK          | 8-char random token sent to parent  |
| `user_id`    | text      | NOT NULL    | FK → `user.user_id` (the student)   |
| `expires_at` | timestamptz | NOT NULL    | Default: 24 hours from creation     |
| `used`       | boolean     | NOT NULL    | Flipped to `true` on redemption     |
| `created_at` | timestamptz | NOT NULL    |                                     |

---

## AI Conversations

### `conversation`

> Metadata for a general AI chat session (profile, update, etc.) between a student/teacher and an agent.

| Field               | Type      | Constraints | Notes                                               |
| ------------------- | --------- | ----------- | --------------------------------------------------- |
| `conversation_id`   | text      | PK          |                                                     |
| `user_id`           | text      | NOT NULL    | FK → `user.user_id`                                 |
| `conversation_type` | text      | NOT NULL    | e.g. `"profile"`, `"update"`, `"quest_grading"`     |
| `period_id`         | text      | nullable    |                                                     |
| `created_at`        | timestamptz | NOT NULL    |                                                     |
| `last_response_id`  | text        | nullable    | Last OpenAI response ID — used for message chaining |

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

---

### `student_skill_mastery`

> Tracks whether a student has mastered each skill in a period. Updated by the grading pipeline after each quest.

| Field        | Type      | Constraints               | Notes                               |
| ------------ | --------- | ------------------------- | ----------------------------------- |
| `student_id` | text      | PK (composite) → `user`   |                                     |
| `period_id`  | text      | PK (composite) → `period` |                                     |
| `skill_name` | text      | PK (composite)            |                                     |
| `mastered`   | boolean   | NOT NULL                  |                                     |
| `score`      | numeric     | NOT NULL                  | Latest aggregated score (0.0 – 1.0) |
| `updated_at` | timestamptz | NOT NULL                  |                                     |

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
| `request_ip` | text      | nullable    |                                                |
| `user_agent` | text      | nullable    |                                                |

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

---

## Quick Reference

| Table                       | PK                                    | Purpose                                   |
| --------------------------- | ------------------------------------- | ----------------------------------------- |
| `user`                      | `user_id`                             | Shared identity for all account types     |
| `student`                   | `user_id`                             | Student profile fields                    |
| `teacher`                   | `user_id`                             | Teacher profile fields                    |
| `parent`                    | `user_id`                             | Parent profile + linked student IDs       |
| `period`                    | `period_id`                           | Class period owned by a teacher or parent |
| `period_schedule`           | `period_id`                           | AI-generated weekly schedule for a period |
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
| `material_files`            | `file_hash`                           | SHA-256 dedup registry for uploaded course files |

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
