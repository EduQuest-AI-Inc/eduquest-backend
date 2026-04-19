# DynamoDB Table Reference

Quick visual reference for all 14 tables in the EduQuest backend.

---

## Table of Contents

1. [student](#student)
2. [teacher](#teacher)
3. [parent](#parent)
4. [period](#period)
5. [period_schedule](#period_schedule)
6. [enrollment](#enrollment)
7. [session](#session)
8. [individual_quest](#individual_quest)
9. [weekly_quest](#weekly_quest)
10. [waitlist](#waitlist)
11. [parent_invite](#parent_invite)
12. [password_reset_token](#password_reset_token)
13. [password_reset_rate_limit](#password_reset_rate_limit)
14. [conversation](#conversation)

**Supabase-only tables** (no DynamoDB equivalent):

15. [school](#school)
16. [ltg_conversation](#ltg_conversation)
17. [parent_waitlist](#parent_waitlist)

---

### `student`

> Stores student accounts and their profile data (interests, learning style, long-term goals).

|               | Key          |
| ------------- | ------------ |
| Partition Key | `student_id` |
| Sort Key      | —            |

| Field                | Type           | Notes                                 |
| -------------------- | -------------- | ------------------------------------- |
| `student_id`         | string         | PK                                    |
| `first_name`         | string         |                                       |
| `last_name`          | string         |                                       |
| `email`              | string         |                                       |
| `email_lc`           | string         | Lowercase canonical email for lookups |
| `password`           | string         | Hashed                                |
| `grade`              | integer        |                                       |
| `enrollments`        | list\<string\> | List of `period_id`s                  |
| `strength`           | list           |                                       |
| `weakness`           | list           |                                       |
| `interest`           | list           |                                       |
| `learning_style`     | list           |                                       |
| `long_term_goal`     | map            | `{ subject: goal_string }`            |
| `quests`             | list\<map\>    | Embedded quest references             |
| `completed_tutorial` | boolean        | Default: `false`                      |
| `canvas_api_url`     | string         | Optional                              |
| `canvas_api_key`     | string         | Optional                              |

**Indexes:** none

---

### `teacher`

> Stores teacher accounts and pilot study approval status.

|               | Key          |
| ------------- | ------------ |
| Partition Key | `teacher_id` |
| Sort Key      | —            |

| Field            | Type    | Notes                                 |
| ---------------- | ------- | ------------------------------------- |
| `teacher_id`     | string  | PK                                    |
| `first_name`     | string  |                                       |
| `last_name`      | string  |                                       |
| `email`          | string  |                                       |
| `email_lc`       | string  | Lowercase canonical email for lookups |
| `password`       | string  | Hashed                                |
| `last_login`     | string  | ISO timestamp, optional               |
| `pilot_approved` | boolean | Default: `false`                      |

**Indexes:** none

---

### `parent`

> Stores parent accounts linked to one or more students (homeschool use case).

|               | Key         |
| ------------- | ----------- |
| Partition Key | `parent_id` |
| Sort Key      | —           |

| Field                | Type           | Notes                                 |
| -------------------- | -------------- | ------------------------------------- |
| `parent_id`          | string         | PK (username)                         |
| `first_name`         | string         |                                       |
| `last_name`          | string         |                                       |
| `email`              | string         |                                       |
| `email_lc`           | string         | Lowercase canonical email for lookups |
| `password`           | string         | Hashed                                |
| `linked_student_ids` | list\<string\> | Default: `[]`                         |
| `last_login`         | string         | ISO timestamp, optional               |

**Indexes:** none

---

### `period`

> Represents a class period owned by a teacher or parent. Holds course info and Canvas integration details.

|               | Key         |
| ------------- | ----------- |
| Partition Key | `period_id` |
| Sort Key      | —           |

| Field                | Type           | Notes                                           |
| -------------------- | -------------- | ----------------------------------------------- |
| `period_id`          | string         | PK                                              |
| `owner_id`           | string         | `teacher_id` or `parent_id`                     |
| `owner_type`         | string         | `"teacher"` or `"parent"`                       |
| `course`             | string         |                                                 |
| `vector_store_id`    | string         | OpenAI vector store ID                          |
| `file_urls`          | list\<string\> | Default: `[]`                                   |
| `canvas_api_url`     | string         | Optional                                        |
| `canvas_api_key`     | string         | Optional                                        |
| `canvas_course_id`   | integer        | Optional                                        |
| `canvas_course_name` | string         | Optional                                        |
| `teacher_id`         | string         | Optional — backward compat alias for `owner_id` |
| `parent_id`          | string         | Optional — backward compat alias for `owner_id` |

**Indexes:** none — queries by `owner_id` use a scan with filter

---

### `period_schedule`

> Stores the AI-generated class schedule for a period, including which weeks have quests enabled.

|               | Key         |
| ------------- | ----------- |
| Partition Key | `period_id` |
| Sort Key      | —           |

| Field                     | Type            | Notes                                                         |
| ------------------------- | --------------- | ------------------------------------------------------------- |
| `period_id`               | string          | PK                                                            |
| `teacher_id`              | string          |                                                               |
| `vector_store_id`         | string          |                                                               |
| `schedule_s3_key`         | string          | S3 key for `schedule.json`, optional                          |
| `schedule_json`           | map             | Full schedule payload (DynamoDB fallback when S3 unavailable) |
| `schedule_openai_file_id` | string          | OpenAI file ID for vector store, optional                     |
| `quest_enabled_weeks`     | list\<integer\> | Default: `[]`                                                 |
| `created_at`              | string          | ISO timestamp                                                 |
| `last_updated_at`         | string          | ISO timestamp — auto-updated on every write                   |

**Indexes:** none

---

### `enrollment`

> Maps students into class periods for a given semester.

|               | Key                           |
| ------------- | ----------------------------- |
| Partition Key | `period_id`                   |
| Sort Key      | `enrolled_at` (ISO timestamp) |

| Field         | Type   | Notes                              |
| ------------- | ------ | ---------------------------------- |
| `period_id`   | string | PK                                 |
| `enrolled_at` | string | SK — ISO timestamp, auto-generated |
| `student_id`  | string |                                    |
| `semester`    | string | e.g. `"Fall 2025"`                 |

**Indexes:** none — queries by `student_id` use a scan with filter

---

### `session`

> Active auth sessions. Tracks which user/role is associated with each JWT token.

|               | Key          |
| ------------- | ------------ |
| Partition Key | `auth_token` |
| Sort Key      | `user_id`    |

| Field        | Type    | Notes                                             |
| ------------ | ------- | ------------------------------------------------- |
| `auth_token` | string  | PK — JWT token                                    |
| `user_id`    | string  | SK                                                |
| `role`       | string  | `"student"` \| `"teacher"` \| `"parent"`          |
| `expires_at` | integer | Epoch timestamp — default: 12 hours from creation |

**Indexes:** none

---

### `individual_quest`

> Per-student instance of a quest assignment, including instructions, rubric, grade, and status.

|               | Key                   |
| ------------- | --------------------- |
| Partition Key | `individual_quest_id` |
| Sort Key      | —                     |

| Field                 | Type    | Notes                                                       |
| --------------------- | ------- | ----------------------------------------------------------- |
| `individual_quest_id` | string  | PK                                                          |
| `quest_id`            | string  | Parent weekly quest reference                               |
| `student_id`          | string  |                                                             |
| `period_id`           | string  |                                                             |
| `description`         | string  |                                                             |
| `skills`              | string  | Skills practiced                                            |
| `week`                | integer | Week number                                                 |
| `instructions`        | string  | Detailed completion instructions                            |
| `rubric`              | map     | Grading criteria                                            |
| `status`              | string  | `"not_started"` \| `"in_progress"` \| `"completed"`         |
| `grade`               | string  | Optional — JSON string: `{ detailed_grade, overall_score }` |
| `feedback`            | string  | Optional — grader feedback                                  |
| `due_date`            | string  | ISO timestamp                                               |
| `created_at`          | string  | ISO timestamp                                               |
| `last_updated_at`     | string  | ISO timestamp — auto-updated on write                       |

**Indexes:** none — filters by `student_id`, `period_id`, `week`, `status`, etc. all use scans

---

### `weekly_quest`

> Groups all individual quests for a student in a period across a semester. Contains embedded quest items in DynamoDB.

|               | Key        |
| ------------- | ---------- |
| Partition Key | `quest_id` |
| Sort Key      | —          |

| Field                | Type        | Notes                                              |
| -------------------- | ----------- | -------------------------------------------------- |
| `quest_id`           | string      | PK                                                 |
| `student_id`         | string      |                                                    |
| `period_id`          | string      |                                                    |
| `student_period_key` | string      | Composite GSI key: `"student_id#period_id"`        |
| `quests`             | list\<map\> | Embedded `WeeklyQuestItem` objects (DynamoDB only) |
| `year`               | integer     | Default: current year                              |
| `semester`           | string      | Default: `"Fall 2025"`                             |
| `created_at`         | string      | ISO timestamp                                      |
| `last_updated_at`    | string      | ISO timestamp — auto-updated on write              |

**WeeklyQuestItem fields** (embedded in `quests` list):

| Field                 | Type    |
| --------------------- | ------- |
| `individual_quest_id` | string  |
| `name`                | string  |
| `skills`              | string  |
| `week`                | integer |
| `status`              | string  |
| `description`         | string  |
| `instructions`        | string  |
| `rubric`              | map     |
| `grade`               | string  |
| `feedback`            | string  |
| `due_date`            | string  |
| `created_at`          | string  |
| `last_updated_at`     | string  |

**Indexes:** GSI `student_period_index` — PK: `student_period_key`

---

### `waitlist`

> Teacher pilot study waitlist with referral tracking.

|               | Key                                |
| ------------- | ---------------------------------- |
| Partition Key | `waitlistID` (stores `teacher_id`) |
| Sort Key      | `email`                            |

| Field          | Type    | Notes                               |
| -------------- | ------- | ----------------------------------- |
| `waitlistID`   | string  | PK — stores `teacher_id`            |
| `email`        | string  | SK — lowercase                      |
| `joinedAt`     | string  | ISO timestamp                       |
| `position`     | integer | Queue position                      |
| `referralCode` | string  | 8-char uppercase code               |
| `referredBy`   | string  | Optional — `teacher_id` of referrer |
| `status`       | string  | `"pending"` \| `"approved"`         |

**Indexes:** GSI `referralCode-index` — PK: `referralCode`

---

### `parent_invite`

> Single-use invite codes that allow a parent to be onboarded.

|               | Key    |
| ------------- | ------ |
| Partition Key | `code` |
| Sort Key      | —      |

| Field        | Type    | Notes                                                        |
| ------------ | ------- | ------------------------------------------------------------ |
| `code`       | string  | PK — 8-char random token                                     |
| `parent_id`  | string  |                                                              |
| `expires_at` | string  | ISO timestamp — default: `INVITE_EXPIRY_HOURS` from creation |
| `used`       | boolean | Default: `false`                                             |

**Indexes:** none

---

### `password_reset_token`

> Security tokens for password reset flow. Hashed at rest; supports attempt tracking and burning.

|               | Key          |
| ------------- | ------------ |
| Partition Key | `token_hash` |
| Sort Key      | —            |

| Field              | Type    | Notes                                        |
| ------------------ | ------- | -------------------------------------------- |
| `token_hash`       | string  | PK — SHA-256 hash of the actual token        |
| `user_id`          | string  | `student_id` or `teacher_id`                 |
| `role`             | string  | `"student"` \| `"teacher"`                   |
| `email_lc`         | string  | Lowercase canonical email                    |
| `created_at_iso`   | string  | ISO timestamp                                |
| `expires_at_epoch` | integer | Epoch timestamp — **TTL attribute** (45 min) |
| `attempts`         | integer | Confirmation attempts; max 5 before burning  |
| `used_at_iso`      | string  | Optional — set when token is consumed        |
| `burned_at_iso`    | string  | Optional — set when token is burned          |
| `request_ip`       | string  | Optional                                     |
| `user_agent`       | string  | Optional                                     |

**Indexes:** TTL on `expires_at_epoch` — auto-deletes after 45 minutes

---

### `password_reset_rate_limit`

> Three-tier rate limiting for password reset requests (IP+email, IP-only, email cooldown).

|               | Key   |
| ------------- | ----- |
| Partition Key | `key` |
| Sort Key      | —     |

| Field              | Type    | Notes                                                 |
| ------------------ | ------- | ----------------------------------------------------- |
| `key`              | string  | PK — composite key; format varies by tier (see below) |
| `count`            | integer | Request count within window                           |
| `expires_at_epoch` | integer | Epoch timestamp — **TTL attribute**                   |

**Key formats:**

| Tier           | Format                                     | Limit          |
| -------------- | ------------------------------------------ | -------------- |
| IP + email     | `ip:{ip}\|email:{email}\|w:{window_start}` | 5 per 15 min   |
| IP only        | `ip:{ip}\|w:{window_start}`                | 20 per 15 min  |
| Email cooldown | `cooldown:email:{email}`                   | 5 min cooldown |

**Indexes:** TTL on `expires_at_epoch` — auto-deletes after window + 1 minute

---

### `conversation`

> Stores conversation metadata for AI chat sessions between students/teachers and the agent.

|               | Key               |
| ------------- | ----------------- |
| Partition Key | `conversation_id` |
| Sort Key      | —                 |

| Field               | Type   | Notes                                            |
| ------------------- | ------ | ------------------------------------------------ |
| `conversation_id`   | string | PK                                               |
| `user_id`           | string |                                                  |
| `role`              | string | `"student"` \| `"teacher"`                       |
| `conversation_type` | string | e.g. `"profile"`                                 |
| `period_id`         | string | Optional                                         |
| `last_response_id`  | string | Optional — last OpenAI response ID for threading |
| `created_at`        | string | ISO timestamp (aliased as `createdAt` in model)  |

**Indexes:** none — filtering by `user_id` / `conversation_type` done in application code

---

## Supabase-Only Tables

---

### `school`

> Represents a school organization. Supabase-only — no DynamoDB counterpart.

|               | Key         |
| ------------- | ----------- |
| Partition Key | `school_id` |
| Sort Key      | —           |

| Field         | Type   | Notes |
| ------------- | ------ | ----- |
| `school_id`   | string | PK    |
| `school_name` | string |       |

**Indexes:** none

---

### `ltg_conversation`

> Maps each (student, period) pair to an OpenAI long-term goal conversation ID. Supabase-only.

|               | Key                                    |
| ------------- | -------------------------------------- |
| Partition Key | `student_id` + `period_id` (composite) |
| Sort Key      | —                                      |

| Field              | Type   | Notes                                            |
| ------------------ | ------ | ------------------------------------------------ |
| `student_id`       | string | Part of composite PK                             |
| `period_id`        | string | Part of composite PK                             |
| `conversation_id`  | string | OpenAI conversation ID                           |
| `last_response_id` | string | Optional — last OpenAI response ID for threading |
| `created_at`       | string | ISO timestamp                                    |

**Indexes:** unique index on `(student_id, period_id)`

---

### `parent_waitlist`

> Waitlist for parent onboarding. Supabase-only by design — new feature with no DynamoDB legacy path.

|               | Key                        |
| ------------- | -------------------------- |
| Partition Key | `email` (via unique index) |
| Sort Key      | —                          |

| Field                 | Type   | Notes                                                                 |
| --------------------- | ------ | --------------------------------------------------------------------- |
| `email`               | string | Unique — case-insensitive via `idx_parent_waitlist_email_lower` index |
| _(additional fields)_ |        | Set by caller via `create()` — no fixed schema enforced in DAO        |

**Indexes:** unique index `idx_parent_waitlist_email_lower` on lowercase `email`

---

## Quick Reference

| Table                                | PK                       | SK            | GSI                              | TTL                |
| ------------------------------------ | ------------------------ | ------------- | -------------------------------- | ------------------ |
| `student`                            | `student_id`             | —             | —                                | —                  |
| `teacher`                            | `teacher_id`             | —             | —                                | —                  |
| `parent`                             | `parent_id`              | —             | —                                | —                  |
| `period`                             | `period_id`              | —             | —                                | —                  |
| `period_schedule`                    | `period_id`              | —             | —                                | —                  |
| `enrollment`                         | `period_id`              | `enrolled_at` | —                                | —                  |
| `session`                            | `auth_token`             | `user_id`     | —                                | —                  |
| `individual_quest`                   | `individual_quest_id`    | —             | —                                | —                  |
| `weekly_quest`                       | `quest_id`               | —             | `student_period_index`           | —                  |
| `waitlist`                           | `waitlistID`             | `email`       | `referralCode-index`             | —                  |
| `parent_invite`                      | `code`                   | —             | —                                | —                  |
| `password_reset_token`               | `token_hash`             | —             | —                                | `expires_at_epoch` |
| `password_reset_rate_limit`          | `key`                    | —             | —                                | `expires_at_epoch` |
| `conversation`                       | `conversation_id`        | —             | —                                | —                  |
| `school` _(Supabase only)_           | `school_id`              | —             | —                                | —                  |
| `ltg_conversation` _(Supabase only)_ | `student_id + period_id` | —             | unique `(student_id, period_id)` | —                  |
| `parent_waitlist` _(Supabase only)_  | `email`                  | —             | unique `email_lower`             | —                  |
