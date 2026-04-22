# Supabase Table Reference

Quick visual reference for all 16 tables in the EduQuest backend.

---

## Table of Contents

1. [user](#user)
2. [student](#student)
3. [teacher](#teacher)
4. [parent](#parent)
5. [period](#period)
6. [period_schedule](#period_schedule)
7. [enrollment](#enrollment)
8. [session](#session)
9. [individual_quest](#individual_quest)
10. [weekly_quest](#weekly_quest)
11. [waitlist](#waitlist)
12. [parent_invite](#parent_invite)
13. [password_reset_token](#password_reset_token)
14. [password_reset_rate_limit](#password_reset_rate_limit)
15. [conversation](#conversation)
16. [student_long_term_goal](#student_long_term_goal)
17. [school](#school)
18. [ltg_conversation](#ltg_conversation)
19. [parent_waitlist](#parent_waitlist)

---

### `user`

> Shared identity table for all account types. Role tables (`student`, `teacher`, `parent`) hold only role-specific fields and FK to this table.

|               | Key       |
| ------------- | --------- |
| Partition Key | `user_id` |
| Sort Key      | —         |

| Field            | Type   | Notes                                          |
| ---------------- | ------ | ---------------------------------------------- |
| `user_id`        | string | PK                                             |
| `first_name`     | string |                                                |
| `last_name`      | string |                                                |
| `email`          | string |                                                |
| `email_lc`       | string | Unique — canonical lowercase email for lookups |
| `password`       | string | Hashed (werkzeug)                              |
| `last_login`     | string | ISO timestamp, optional                        |
| `role`           | string | `"student"` \| `"teacher"` \| `"parent"`       |
| `canvas_api_url` | string | Optional                                       |
| `canvas_api_key` | string | Optional                                       |

**Indexes:** unique index `idx_user_email_lc` on `email_lc`

---

### `student`

> Role-specific fields for student accounts. Shared identity fields live in `user`.

|               | Key       |
| ------------- | --------- |
| Partition Key | `user_id` |
| Sort Key      | —         |

| Field                | Type    | Notes                             |
| -------------------- | ------- | --------------------------------- |
| `user_id`            | string  | PK + FK → `user.user_id` CASCADE  |
| `grade`              | integer |                                   |
| `strength`           | list    |                                   |
| `weakness`           | list    |                                   |
| `interest`           | list    |                                   |
| `learning_style`     | list    |                                   |
| `completed_tutorial` | boolean | Default: `false`                  |
| `school_id`          | string  | Optional — FK → `school.school_id`|

**Indexes:** none

---

### `teacher`

> Role-specific fields for teacher accounts. Shared identity fields live in `user`.

|               | Key       |
| ------------- | --------- |
| Partition Key | `user_id` |
| Sort Key      | —         |

| Field            | Type    | Notes                              |
| ---------------- | ------- | ---------------------------------- |
| `user_id`        | string  | PK + FK → `user.user_id` CASCADE   |
| `pilot_approved` | boolean | Default: `false`                   |
| `school_id`      | string  | Optional — FK → `school.school_id` |

**Indexes:** none

---

### `parent`

> Role-specific fields for parent accounts. Shared identity fields live in `user`.

|               | Key       |
| ------------- | --------- |
| Partition Key | `user_id` |
| Sort Key      | —         |

| Field             | Type           | Notes                                                            |
| ----------------- | -------------- | ---------------------------------------------------------------- |
| `user_id`         | string         | PK + FK → `user.user_id` CASCADE                                 |
| `linked_user_ids` | list\<string\> | Default: `[]` — `user_id`s of linked students                    |
| `vpc_verified_at` | string         | Optional — COPPA 2025 compliance timestamp, set on invite accept |

**Indexes:** none

---

### `period`

> Represents a class period owned by a teacher or parent. Holds course info and Canvas integration details.

|               | Key         |
| ------------- | ----------- |
| Partition Key | `period_id` |
| Sort Key      | —           |

| Field                | Type           | Notes                              |
| -------------------- | -------------- | ---------------------------------- |
| `period_id`          | string         | PK                                 |
| `owner_id`           | string         | FK → `user.user_id`                |
| `owner_type`         | string         | `"teacher"` or `"parent"`          |
| `course`             | string         |                                    |
| `vector_store_id`    | string         | OpenAI vector store ID             |
| `file_urls`          | list\<string\> | Default: `[]`                      |
| `canvas_api_url`     | string         | Optional                           |
| `canvas_api_key`     | string         | Optional                           |
| `canvas_course_id`   | integer        | Optional                           |
| `canvas_course_name` | string         | Optional                           |

**Indexes:** none — queries by `owner_id` use a filter

---

### `period_schedule`

> AI-generated class schedule for a period, including which weeks have quests enabled.

|               | Key         |
| ------------- | ----------- |
| Partition Key | `period_id` |
| Sort Key      | —           |

| Field                     | Type            | Notes                                     |
| ------------------------- | --------------- | ----------------------------------------- |
| `period_id`               | string          | PK                                        |
| `user_id`                 | string          | FK → `user.user_id`                       |
| `vector_store_id`         | string          |                                           |
| `schedule_s3_key`         | string          | S3 key for `schedule.json`, optional      |
| `schedule_json`           | map             | Full schedule payload (S3 fallback)       |
| `schedule_openai_file_id` | string          | OpenAI file ID for vector store, optional |
| `quest_enabled_weeks`     | list\<integer\> | Default: `[]`                             |
| `created_at`              | string          | ISO timestamp                             |
| `last_updated_at`         | string          | ISO timestamp — auto-updated on write     |

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
| `user_id`     | string | FK → `user.user_id`                |
| `semester`    | string | e.g. `"Fall 2025"`                 |

**Indexes:** none — queries by `user_id` use a filter

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
| `user_id`    | string  | SK — FK → `user.user_id`                          |
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
| `user_id`             | string  | FK → `user.user_id`                                         |
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

**Indexes:** none — filters by `user_id`, `period_id`, `week`, `status` use filters

---

### `weekly_quest`

> Groups all individual quests for a student in a period across a semester.

|               | Key        |
| ------------- | ---------- |
| Partition Key | `quest_id` |
| Sort Key      | —          |

| Field                | Type        | Notes                                   |
| -------------------- | ----------- | --------------------------------------- |
| `quest_id`           | string      | PK                                      |
| `user_id`            | string      | FK → `user.user_id`                     |
| `period_id`          | string      |                                         |
| `student_period_key` | string      | Composite index key: `"user_id#period_id"` |
| `quests`             | list\<map\> | Embedded `WeeklyQuestItem` objects      |
| `year`               | integer     | Default: current year                   |
| `semester`           | string      | Default: `"Fall 2025"`                  |
| `created_at`         | string      | ISO timestamp                           |
| `last_updated_at`    | string      | ISO timestamp — auto-updated on write   |

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

**Indexes:** unique index on `student_period_key`

---

### `waitlist`

> Teacher pilot study waitlist with referral tracking.

|               | Key          |
| ------------- | ------------ |
| Partition Key | `waitlistID` |
| Sort Key      | `email`      |

| Field          | Type    | Notes                             |
| -------------- | ------- | --------------------------------- |
| `waitlistID`   | string  | PK — stores `user_id`             |
| `email`        | string  | SK — lowercase                    |
| `joinedAt`     | string  | ISO timestamp                     |
| `position`     | integer | Queue position                    |
| `referralCode` | string  | 8-char uppercase code             |
| `referredBy`   | string  | Optional — `user_id` of referrer  |
| `status`       | string  | `"pending"` \| `"approved"`       |

**Indexes:** unique index on `referralCode`

---

### `parent_invite`

> Single-use invite codes that allow a parent to link a student account.

|               | Key    |
| ------------- | ------ |
| Partition Key | `code` |
| Sort Key      | —      |

| Field        | Type    | Notes                                                        |
| ------------ | ------- | ------------------------------------------------------------ |
| `code`       | string  | PK — 8-char random token                                     |
| `user_id`    | string  | FK → `user.user_id` (parent)                                 |
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
| `token_hash`       | string  | PK — SHA-256 hash of the raw token           |
| `user_id`          | string  | FK → `user.user_id`                          |
| `role`             | string  | `"student"` \| `"teacher"` \| `"parent"`     |
| `email_lc`         | string  | Lowercase canonical email                    |
| `created_at_iso`   | string  | ISO timestamp                                |
| `expires_at_epoch` | integer | Epoch timestamp — TTL (45 min)               |
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
| `expires_at_epoch` | integer | Epoch timestamp — TTL                                 |

**Key formats:**

| Tier           | Format                                     | Limit          |
| -------------- | ------------------------------------------ | -------------- |
| IP + email     | `ip:{ip}\|email:{email}\|w:{window_start}` | 5 per 15 min   |
| IP only        | `ip:{ip}\|w:{window_start}`                | 20 per 15 min  |
| Email cooldown | `cooldown:email:{email}`                   | 5 min cooldown |

**Indexes:** TTL on `expires_at_epoch` — auto-deletes after window + 1 minute

---

### `conversation`

> Conversation metadata for AI chat sessions between students/teachers and the agent.

|               | Key               |
| ------------- | ----------------- |
| Partition Key | `conversation_id` |
| Sort Key      | —                 |

| Field               | Type   | Notes                                            |
| ------------------- | ------ | ------------------------------------------------ |
| `conversation_id`   | string | PK                                               |
| `user_id`           | string | FK → `user.user_id`                              |
| `role`              | string | `"student"` \| `"teacher"`                       |
| `conversation_type` | string | e.g. `"profile"`, `"update"`                     |
| `period_id`         | string | Optional                                         |
| `last_response_id`  | string | Optional — last OpenAI response ID for threading |
| `created_at`        | string | ISO timestamp                                    |

**Indexes:** none — filtering by `user_id` / `conversation_type` done in application code

---

### `student_long_term_goal`

> Per-student, per-period long-term goal text. Written by `StudentDAO.update_long_term_goal`.

|               | Key                           |
| ------------- | ----------------------------- |
| Partition Key | `user_id` + `period_id` (composite) |
| Sort Key      | —                             |

| Field        | Type   | Notes                                  |
| ------------ | ------ | -------------------------------------- |
| `user_id`    | string | Part of composite PK — FK → `user.user_id` |
| `period_id`  | string | Part of composite PK                   |
| `goal_text`  | string |                                        |
| `updated_at` | string | ISO timestamp — set on every upsert    |

**Indexes:** unique index on `(user_id, period_id)`

---

### `school`

> Represents a school organization.

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

> Maps each (student, period) pair to an OpenAI long-term goal conversation ID.

|               | Key                                  |
| ------------- | ------------------------------------ |
| Partition Key | `user_id` + `period_id` (composite)  |
| Sort Key      | —                                    |

| Field              | Type   | Notes                                            |
| ------------------ | ------ | ------------------------------------------------ |
| `user_id`          | string | Part of composite PK — FK → `user.user_id`       |
| `period_id`        | string | Part of composite PK                             |
| `conversation_id`  | string | OpenAI conversation ID                           |
| `last_response_id` | string | Optional — last OpenAI response ID for threading |
| `created_at`       | string | ISO timestamp                                    |

**Indexes:** unique index on `(user_id, period_id)`

---

### `parent_waitlist`

> Waitlist for parent onboarding.

|               | Key                       |
| ------------- | ------------------------- |
| Partition Key | `email` (via unique index) |
| Sort Key      | —                         |

| Field                 | Type   | Notes                                                                 |
| --------------------- | ------ | --------------------------------------------------------------------- |
| `email`               | string | Unique — case-insensitive via `idx_parent_waitlist_email_lower` index |
| _(additional fields)_ |        | Set by caller — no fixed schema enforced in DAO                       |

**Indexes:** unique index `idx_parent_waitlist_email_lower` on lowercase `email`

---

## Quick Reference

| Table                        | PK                          | SK            | Unique / Index                  | TTL                |
| ---------------------------- | --------------------------- | ------------- | ------------------------------- | ------------------ |
| `user`                       | `user_id`                   | —             | `email_lc`                      | —                  |
| `student`                    | `user_id`                   | —             | FK → `user`                     | —                  |
| `teacher`                    | `user_id`                   | —             | FK → `user`                     | —                  |
| `parent`                     | `user_id`                   | —             | FK → `user`                     | —                  |
| `period`                     | `period_id`                 | —             | —                                | —                  |
| `period_schedule`            | `period_id`                 | —             | —                                | —                  |
| `enrollment`                 | `period_id`                 | `enrolled_at` | —                                | —                  |
| `session`                    | `auth_token`                | `user_id`     | —                                | —                  |
| `individual_quest`           | `individual_quest_id`       | —             | —                                | —                  |
| `weekly_quest`               | `quest_id`                  | —             | `student_period_key`            | —                  |
| `waitlist`                   | `waitlistID`                | `email`       | `referralCode`                  | —                  |
| `parent_invite`              | `code`                      | —             | —                                | —                  |
| `password_reset_token`       | `token_hash`                | —             | —                                | `expires_at_epoch` |
| `password_reset_rate_limit`  | `key`                       | —             | —                                | `expires_at_epoch` |
| `conversation`               | `conversation_id`           | —             | —                                | —                  |
| `student_long_term_goal`     | `user_id + period_id`       | —             | unique `(user_id, period_id)`   | —                  |
| `school`                     | `school_id`                 | —             | —                                | —                  |
| `ltg_conversation`           | `user_id + period_id`       | —             | unique `(user_id, period_id)`   | —                  |
| `parent_waitlist`            | `email`                     | —             | `email_lower`                   | —                  |
