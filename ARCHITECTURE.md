# EduQuest Backend Architecture

## Architecture Decisions

### Routers are HTTP-boundary-only — no business logic lives there

Route handlers in `routers` are responsible for parsing requests, enforcing auth via `Depends()`, and returning responses. All business logic belongs in the service layer. A router handler should do nothing more than call a service method and return its result (plus any private `_helper()` functions scoped to that file for multi-step request wiring, capped at 20 lines each).

### All S3 access goes through `integrations/s3_service.py`

AWS credentials, bucket config, and error handling live in one place. Services must never
instantiate `boto3.client` directly — import helpers from `integrations/s3_service.py` instead.

### Frontend role and ownership checks are UX only — the backend is the enforcement boundary

The frontend may hide buttons, redirect routes, or skip rendering components based on role or ownership. These checks exist to avoid confusing users with options that would fail, not to enforce access control. Every protected action must be independently enforced at the API layer via `require_roles` or an explicit ownership check. Removing a frontend gate should never expose a security gap.

### Auth & Role-Based Access Control

Role enforcement lives exclusively at the **router layer** via FastAPI `Depends()`. Service methods never raise errors for role checks — they assume the caller is already authorized. Service-layer `PermissionError` is reserved for **ownership checks** only (e.g. a teacher editing another teacher's period).

Three roles: `Role.STUDENT`, `Role.TEACHER`, `Role.PARENT` — defined as a `str, Enum` in `api/deps.py` alongside `AuthPayload` and `get_auth()`.

Canonical dependencies (all in `api/deps.py`):

- `get_auth()` — validates JWT, returns `AuthPayload`; use when any authenticated user is allowed.
- `require_roles(Role.X, ...)` — restricts to one or more roles; declare in the route's `Depends()`.
- `require_student_viewer("param_name")` — use when a parent or teacher may optionally pass a student `user_id` to view that student's data.

Supabase RLS is the secondary enforcement layer. Do not duplicate RLS logic in Python.

Audit: `pytest tests/unit/routes/test_rbac_audit.py` verifies every route either has an auth dependency or is listed in `EXPLICITLY_PUBLIC_ROUTES`.

### The frontend never calls Supabase for data reads or writes — all domain data goes through FastAPI

The frontend uses the Supabase client SDK for auth only (sign-up, sign-in, session management).
All domain data reads and writes must go through the FastAPI backend. This keeps business logic
and RLS policy in one place and prevents clients from bypassing server-side validation.

---

## Layers at a Glance

### Architecture Overview

```mermaid
graph TB
    Client["Client<br/>(Browser / Mobile)"]

    subgraph FastAPI["FastAPI Application — Port 8000"]
        MW["CORS + JWT Middleware"]
        BP["Route Handlers<br/>/auth  /user  /conversation  /period<br/>/teacher  /enrollment  /quest  /parent  /pilot-waitlist"]
        Svc["Feature Services<br/>(one or more per Router)"]
    end

    AI["AI Layer (OpenAI Agents SDK)<br/>Profile · LTG · HW · Grading · Schedule · Teacher Feedback"]
    DB["Supabase / PostgreSQL"]
    Ext["External<br/>S3 · SES · Canvas LMS · OpenAI Files API"]

    Client -->|HTTPS JSON| MW
    MW --> BP
    BP --> Svc
    Svc --> AI & DB & Ext
    AI --> DB
```

### Service → Dependency Map

```mermaid
graph LR
    subgraph Svc["Services"]
        AuthSvc["auth_service<br/>password_reset_service"]
        UserSvc["user_service"]
        ConvSvc["conversation · grading<br/>profile · ltg · teacher_feedback"]
        PeriodSvc["period_management · ltg<br/>quest · schedule · enrollment"]
        EnrollSvc["enrollment_service"]
        QuestSvc["quest_creation<br/>quest_retrieval · quest_grading"]
        ParentSvc["parent_service"]
        WaitSvc["WaitlistService"]
    end

    subgraph AI["AI Agents (bots/)"]
        ProfBot["Profile Agent<br/>(gpt-4.1-mini)"]
        LTGBot["LTG Agent<br/>(gpt-5)"]
        HWBot["HW Agent<br/>(gpt-5)"]
        GradeBot["Grading Orchestrator<br/>4 sub-agents (gpt-5)"]
        SchedBot["Schedule Agent<br/>(gpt-5)"]
        TFBot["Teacher Feedback Agent"]
    end

    subgraph Ext["External Services"]
        S3["AWS S3"]
        SES["AWS SES"]
        Canvas["Canvas LMS"]
        OAI["OpenAI Files API"]
    end

    subgraph DB["Database (Supabase)"]
        Auth_t["session<br/>password_reset_token<br/>password_reset_rate_limit"]
        Identity_t["user · student<br/>teacher · parent"]
        Course_t["period · period_schedule<br/>enrollment"]
        AI_t["conversation · ltg_conversation<br/>quest · student_skill_mastery · aggregated_metrics"]
        Onboard_t["parent_invite · waitlist"]
    end

    AuthSvc --> Auth_t & SES
    UserSvc --> Identity_t & Canvas
    ConvSvc --> ProfBot & GradeBot & TFBot
    ConvSvc --> AI_t & Identity_t
    PeriodSvc --> LTGBot & HWBot & SchedBot
    PeriodSvc --> Course_t & OAI & S3
    EnrollSvc --> Course_t
    QuestSvc --> AI_t
    ParentSvc --> Identity_t & Onboard_t
    WaitSvc --> Onboard_t
    ProfBot --> Identity_t
    LTGBot & HWBot & GradeBot --> AI_t
```

---

## Auth Flows

### Sign Up

```mermaid
sequenceDiagram
    actor C as Client
    participant R as POST /auth/signup
    participant S as auth_service
    participant DB as Supabase

    C->>R: {email, password, first_name, last_name, role}
    R->>S: register_user()
    S->>DB: UserDAO.get_by_id()  — check duplicate
    DB-->>S: null (no duplicate)
    S->>DB: UserDAO.add_user()  — insert user row
    S->>DB: StudentDAO / TeacherDAO / ParentDAO.add_*()  — insert role row
    S->>DB: SessionDAO.add_session()  — create session
    S-->>R: {auth_token, user_id, role}
    R-->>C: 201  {auth_token, user_id, role}
    Note over R,C: Token also set as HTTP-only cookie via set_auth_cookie()
```

### Login

```mermaid
sequenceDiagram
    actor C as Client
    participant R as POST /auth/login
    participant S as auth_service
    participant DB as Supabase

    C->>R: {email, password, role}
    R->>S: login_user()
    S->>DB: UserDAO.get_by_id()
    DB-->>S: user row
    S->>S: bcrypt verify password
    S->>DB: SessionDAO.add_session()  — store token with 1 h expiry
    S-->>R: JWT auth_token
    R-->>C: 200  {auth_token, user_id, role}
    Note over C,R: All subsequent requests send Authorization: Bearer {auth_token}
```

### Password Reset

```mermaid
sequenceDiagram
    actor C as Client
    participant R1 as POST /auth/password-reset/request
    participant R2 as POST /auth/password-reset/confirm
    participant S as password_reset_service
    participant DB as Supabase
    participant Email as AWS SES

    C->>R1: {email}
    R1->>S: request_reset()
    S->>DB: PasswordResetRateLimitDAO  — enforce rate limit
    S->>DB: PasswordResetTokenDAO.create()  — store one-time token
    S->>Email: send_password_reset_email()
    R1-->>C: 200  (always, to avoid email enumeration)

    C->>R2: {token, new_password}
    R2->>S: confirm_reset()
    S->>DB: PasswordResetTokenDAO.get_valid()  — validate & check expiry
    S->>S: password_policy.validate()
    S->>DB: UserDAO.update()  — bcrypt hash + store
    S->>DB: PasswordResetTokenDAO.burn()  — mark token used
    R2-->>C: 200
```

---

## User / Profile Flows

### Get Profile

```mermaid
sequenceDiagram
    actor C as Client
    participant MW as get_auth() dependency
    participant R as GET /user/profile
    participant S as user_service
    participant DB as Supabase

    C->>MW: Authorization: Bearer {token}  (or auth_token cookie)
    MW->>DB: SessionDAO.get_by_token()  — validate session
    MW-->>R: AuthPayload(sub, role, token)
    R->>S: get_profile(user_id, role)
    S->>DB: StudentDAO / TeacherDAO / ParentDAO.get_by_id()
    DB-->>S: full profile row (joins user + role table)
    S-->>R: profile object
    R-->>C: 200  {profile}
```

### Connect / Disconnect Canvas

```mermaid
sequenceDiagram
    actor C as Client
    participant R as POST /user/canvas/connect
    participant S as user_service
    participant Canvas as Canvas LMS API
    participant DB as Supabase

    C->>R: {canvas_api_url, canvas_api_key}
    R->>S: connect_canvas(user_id, url, key)
    S->>Canvas: Verify credentials (fetch /api/v1/users/self)
    Canvas-->>S: 200 OK
    S->>DB: UserDAO.update()  — store url + key
    R-->>C: 200

    Note over C,R: GET /user/canvas/courses
    C->>R: GET /user/canvas/courses
    R->>S: get_canvas_courses(user_id)
    S->>DB: UserDAO.get_by_id()  — fetch stored credentials
    S->>Canvas: CanvasService.list_courses()
    Canvas-->>S: [{course_id, name, ...}]
    R-->>C: 200  [{course_id, name}]
```

---

## Conversation Flows

All conversation routes require a valid JWT. Conversation state is tracked in the `conversation` table using OpenAI's `last_response_id` from the Responses API — the previous response ID is passed to `Runner.run()` to continue a thread without re-sending history.

### Profile Gathering (New Student Onboarding)

```mermaid
sequenceDiagram
    actor C as Client (Student)
    participant R1 as POST /conversation/initiate-profile-assistant
    participant R2 as POST /conversation/continue-profile-assistant
    participant S as conversation_service / profile_service
    participant AI as Profile Agent (gpt-4.1-mini)
    participant DB as Supabase

    C->>R1: {} (no body needed)
    R1->>S: initiate_profile(user_id)
    S->>AI: create_profile_agent() — first message
    Note over S,AI: Guardrails applied via check_student_output_safety()
    AI-->>S: {response_text, response_id}
    S->>DB: ConversationDAO.add_conversation()  — store response_id
    R1-->>C: 200  {conversation_id, message}

    loop Until profile_complete
        C->>R2: {conversation_id, message}
        R2->>S: continue_profile(conversation_id, message)
        S->>DB: ConversationDAO.get_by_id()  — fetch last_response_id
        S->>AI: Runner.run() with previous_response_id
        AI-->>S: {response_text, response_id, profile_complete?, profile_data?}
        S->>DB: ConversationDAO.update()  — new response_id
        alt Profile complete
            S->>DB: StudentDAO.update_student()  — persist strengths/weaknesses/interests/learning_style
        end
        R2-->>C: 200  {message, profile_complete}
    end
```

### Grading / Update Assistant

This flow handles student work submissions. The update assistant grades the work via a multi-agent orchestrator then may continue as a follow-up conversation.

```mermaid
sequenceDiagram
    actor C as Client (Student)
    participant R1 as POST /conversation/initiate-update-assistant
    participant R2 as POST /conversation/continue-update-assistant
    participant S as conversation_service / grading_service
    participant AI as Grading Orchestrator (gpt-5)
    participant DB as Supabase
    participant S3 as AWS S3

    C->>R1: {quest_id, file OR json_submission}
    R1->>S: initiate_update(user_id, quest_id, submission)
    S->>S3: upload submission file (if file upload)
    S->>DB: QuestDAO.get_quest_by_id()  — load rubric & instructions
    S->>DB: StudentDAO.get_student_by_id()  — load student profile
    S->>AI: GradingOrchestrator.grade()
    Note over AI: 1. Numerical Grade Agent  → score per rubric criterion
    Note over AI: 2. Feedback Agent         → written feedback
    Note over AI: 3. Skill Mastery Agent    → updates skill mastery levels (0.0–1.0)
    Note over AI: 4. HW Recommendation Agent → next quest suggestions
    AI-->>S: {grade, feedback, skill_updates, next_quests}
    S->>DB: QuestDAO.update_quest()  — persist grade + feedback
    S->>DB: StudentSkillMasteryDAO.upsert()  — persist skill levels
    S->>DB: ConversationDAO.add_conversation()  — store response_id
    R1-->>C: 200  {conversation_id, message, grade, feedback}

    loop Optional follow-up turns
        C->>R2: {conversation_id, message}
        R2->>S: continue_update(conversation_id, message)
        S->>DB: ConversationDAO.get_by_id()
        S->>AI: continue thread
        AI-->>S: {response_text, response_id}
        S->>DB: ConversationDAO.update()
        R2-->>C: 200  {message}
    end
```

---

## Period Flows

### Create a Period

```mermaid
sequenceDiagram
    actor T as Client (Teacher / Parent)
    participant R as POST /period/create-period
    participant S as period_management_service
    participant S3 as AWS S3
    participant OAI as OpenAI Files API
    participant DB as Supabase

    T->>R: {name, files[], canvas_course_id?}  multipart
    R->>S: create_period(owner_id, name, files, canvas_course_id)
    S->>S3: S3Service.upload_to_s3() — store each file, get URLs
    S->>OAI: Create vector store, upload files for AI retrieval
    OAI-->>S: vector_store_id
    S->>DB: PeriodDAO.add_period()  — {name, owner_id, file_urls, vector_store_id}
    S-->>R: period object
    R-->>T: 201  {period_id, name, file_urls}
```

### Add Files to Existing Period

```mermaid
sequenceDiagram
    actor T as Client (Teacher / Parent)
    participant R as POST /period/add-files-to-period
    participant S as period_management_service
    participant S3 as AWS S3
    participant OAI as OpenAI Files API
    participant DB as Supabase

    T->>R: {period_id, files[]}  multipart
    R->>S: add_files(period_id, files)
    S->>S3: upload each new file
    S->>OAI: Add files to existing vector store
    S->>DB: PeriodDAO.update_file_urls()  — append new URLs
    R-->>T: 200  {file_urls}
```

### Get a File (Presigned URL)

```mermaid
sequenceDiagram
    actor C as Client
    participant R as GET /period/get-file/{key}
    participant S as period_file_helpers
    participant S3 as AWS S3

    C->>R: key (S3 object key)
    R->>S: get_presigned_url(key)
    S->>S3: generate_presigned_url()  — 1-hour expiry
    S3-->>S: presigned URL
    R-->>C: 200  {url}
    Note over C,S3: Client fetches file directly from S3 using the URL
```

### Generate Quests for a Period

```mermaid
sequenceDiagram
    actor T as Client (Teacher / Parent)
    participant R as POST /period/initiate-homework-agent
    participant S as period_quest_service
    participant AI as HW Agent (gpt-5)
    participant OAI as OpenAI Files API (vector store)
    participant DB as Supabase

    T->>R: {period_id, week_number}
    R->>S: generate_quests(period_id, week_number)
    S->>DB: PeriodDAO.get_period_by_id()  — fetch vector_store_id
    S->>DB: EnrollmentDAO.get_enrollments_by_period()  — list students
    loop For each enrolled student
        S->>DB: StudentDAO.get_student_by_id()  — fetch profile
        S->>AI: HWAgent.generate_title() → generate_instructions() → generate_rubric()
        Note over AI,OAI: Agent searches vector store for course-relevant content
        AI-->>S: {title, instructions, rubric}
        S->>DB: QuestDAO.add_quest()
    end
    R-->>T: 200  {quests_created: N}
```

### AI-Generated Period Schedule

```mermaid
sequenceDiagram
    actor T as Client (Teacher / Parent)
    participant R1 as POST /period/period-schedule/generate
    participant R2 as GET  /period/period-schedule
    participant R3 as PUT  /period/period-schedule
    participant R4 as PUT  /period/period-schedule/quest-weeks
    participant S as period_schedule_service
    participant AI as Schedule Agent (gpt-5)
    participant DB as Supabase

    T->>R1: {period_id}
    R1->>S: generate_schedule(period_id)
    S->>DB: PeriodDAO.get_period_by_id()  — fetch vector_store_id
    S->>AI: ScheduleAgent with course documents
    AI-->>S: schedule JSON
    S->>DB: PeriodScheduleDAO.upsert()  — store schedule
    R1-->>T: 200  {schedule}

    T->>R2: GET ?period_id=...
    R2->>S: get_schedule(period_id)
    S->>DB: PeriodScheduleDAO.get_by_period_id()
    R2-->>T: 200  {schedule}

    T->>R3: {period_id, schedule_json}
    R3->>S: update_schedule(period_id, schedule_json)
    S->>DB: PeriodScheduleDAO.update()
    R3-->>T: 200

    T->>R4: {period_id, quest_enabled_weeks[]}
    R4->>S: set_quest_weeks(period_id, weeks)
    S->>DB: PeriodScheduleDAO.update_quest_weeks()
    R4-->>T: 200
```

---

## LTG (Long-Term Goal) Flow

```mermaid
sequenceDiagram
    actor C as Client (Student)
    participant R1 as POST /period/initiate-ltg-conversation
    participant R2 as POST /period/continue-ltg-conversation
    participant S as ltg_service
    participant AI as LTG Agent (gpt-5)
    participant OAI as OpenAI Files API (vector store)
    participant DB as Supabase

    C->>R1: {period_id}
    R1->>S: initiate_ltg(user_id, period_id)
    S->>DB: StudentDAO.get_student_by_id()  — load profile
    S->>DB: PeriodDAO.get_period_by_id()  — load vector_store_id
    S->>AI: create_ltg_agent(vector_store_id) — first message
    Note over AI,OAI: Agent searches course docs to align goals with curriculum
    AI-->>S: {response_text, response_id, goal_suggestions?}
    S->>DB: LTGConversationDAO.upsert()  — store response_id
    R1-->>C: 200  {conversation_id, message}

    loop Until goal confirmed
        C->>R2: {period_id, message}
        R2->>S: continue_ltg(user_id, period_id, message)
        S->>DB: LTGConversationDAO.get()  — fetch last_response_id
        S->>AI: Runner.run() continue thread
        AI-->>S: {response_text, response_id, goal_confirmed?, goal_text?}
        S->>DB: LTGConversationDAO.update()
        alt Goal confirmed
            S->>DB: StudentLongTermGoalDAO.upsert()  — one row per (user_id, period_id)
        end
        R2-->>C: 200  {message, goal_confirmed}
    end
```

---

## Enrollment Flows

```mermaid
sequenceDiagram
    actor C as Client
    participant R as POST /period/verify-period
    participant S as period_enrollment_service
    participant DB as Supabase

    Note over C,DB: Student joins a period by period_id
    C->>R: {period_id}  (student)
    R->>S: verify_and_enroll(user_id, period_id)
    S->>DB: PeriodDAO.get_period_by_id()  — verify period exists
    S->>DB: EnrollmentDAO.add_enrollment()
    R-->>C: 200  {period}

    Note over C,DB: Teacher views enrolled students
    C->>R: GET /enrollment/enrollments/{period_id}
    R->>S: get_enrollments(period_id)
    S->>DB: EnrollmentDAO.get_enrollments_by_period()
    S->>DB: StudentDAO.get_student_by_id() for each enrollment
    R-->>C: 200  [{student_profile}]

    Note over C,DB: Unenroll
    C->>R: POST /period/unenroll  {period_id}
    R->>S: unenroll(user_id, period_id)
    S->>DB: EnrollmentDAO.delete_enrollment()
    R-->>C: 200
```

---

## Quest Flows

### Retrieve Quests

```mermaid
sequenceDiagram
    actor C as Client
    participant R as GET /quest/quests
    participant S as quest_retrieval_service
    participant DB as Supabase

    C->>R: ?period_id=...  (optional filter)
    R->>S: get_quests(user_id, period_id)
    alt Student
        S->>DB: QuestDAO.get_quests_by_student() or get_quests_by_student_and_period()
    else Teacher / Parent viewing student
        Note over R: GET /quest/quests/{user_id}
        S->>DB: QuestDAO.get_quests_by_student()
    end
    DB-->>S: [quest rows]
    R-->>C: 200  [{quest_id, title, instructions, rubric, status, grade, feedback, ...}]
```

### Update Quest Status

```mermaid
sequenceDiagram
    actor C as Client (Student)
    participant R as PUT /quest/quests/{quest_id}/status
    participant S as quest_service
    participant DB as Supabase

    C->>R: {status}  e.g. "in_progress" | "submitted" | "complete"
    R->>S: update_status(quest_id, status, user_id)
    S->>DB: QuestDAO.get_quest_by_id()  — verify ownership
    S->>DB: QuestDAO.update_quest_status()
    R-->>C: 200
```

### Grade a Quest (Teacher Override)

```mermaid
sequenceDiagram
    actor T as Client (Teacher)
    participant R as PUT /quest/quests/{quest_id}/grade
    participant S as quest_grading_service
    participant DB as Supabase

    T->>R: {grade, feedback}
    R->>S: grade_quest(quest_id, grade, feedback, teacher_id)
    S->>DB: QuestDAO.get_quest_by_id()  — verify period ownership
    S->>DB: QuestDAO.update_quest()  — persist manual grade
    R-->>T: 200
```

---

## Parent Flows

### Accept Parent Invite (Student Side)

```mermaid
sequenceDiagram
    actor C as Client (Student)
    participant R as POST /period/accept-parent-invite
    participant S as period_enrollment_service
    participant DB as Supabase

    C->>R: {invite_code}
    R->>S: accept_invite(student_id, invite_code)
    S->>DB: ParentInviteDAO.get_invite_by_code()  — validate & check expiry/used
    S->>DB: ParentDAO.update_parent()  — link student_id to parent
    S->>DB: ParentInviteDAO.mark_used()
    R-->>C: 200
```

### Generate Invite Code (Parent Side)

```mermaid
sequenceDiagram
    actor P as Client (Parent)
    participant R as POST /parent/generate-invite
    participant S as parent_service
    participant DB as Supabase

    P->>R: {}
    R->>S: generate_invite(parent_id)
    S->>S: uuid / random code, set expiry = now + INVITE_EXPIRY_HOURS (24 h)
    S->>DB: ParentInviteDAO.insert()
    R-->>P: 200  {invite_code, expires_at}
```

---

## Pilot Waitlist Flow

```mermaid
sequenceDiagram
    actor T as Client (Teacher)
    participant R1 as POST /pilot-waitlist/join
    participant R2 as GET  /pilot-waitlist/status
    participant R3 as POST /pilot-waitlist/approve/{user_id}
    participant S as WaitlistService
    participant DB as Supabase

    T->>R1: {referral_code?}
    R1->>S: join(user_id, referral_code)
    S->>DB: WaitlistDAO.insert()  — record position
    R1-->>T: 200  {position}

    T->>R2: GET /pilot-waitlist/status
    R2->>S: get_status(user_id)
    S->>DB: WaitlistDAO.get_by_user_id()
    R2-->>T: 200  {position, approved}

    Note over R3: Admin only
    T->>R3: POST /pilot-waitlist/approve/{user_id}
    R3->>S: approve(user_id)
    S->>DB: TeacherDAO.update_teacher()  — set pilot_approved = true
    S->>DB: WaitlistDAO.update()  — mark approved
    R3-->>T: 200
```

---

## AI Agent Details

All agents live in `bots/` and use the OpenAI Agents SDK (`from agents import Agent, Runner`). Structured outputs use Pydantic schemas in `bots/schemas/`.

| Agent                  | File                                    | Model        | Purpose                                                                                                    |
| ---------------------- | --------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------- |
| Profile Agent          | `profile_agent.py`                      | gpt-4.1-mini | Gathers student strengths, weaknesses, interests, learning style via multi-turn chat                       |
| LTG Agent              | `ltg_agent.py`                          | gpt-5        | Suggests 3 long-term goals aligned with course content (uses vector store file search)                     |
| HW Agent               | `agent.py::HWAgent`                     | gpt-5        | Generates personalised quest title, instructions, and rubric per student (async)                           |
| Grading Orchestrator   | `grading_agent.py::GradingOrchestrator` | gpt-5        | 4 sequential sub-agents: numerical grade, written feedback, skill mastery scores, homework recommendations |
| Schedule Agent         | `schedule_agent.py::ScheduleAgent`      | gpt-5        | Generates a weekly schedule from course documents                                                          |
| Teacher Feedback Agent | `teacher_feedback_agent.py`             | gpt-5        | Turns teacher notes into structured feedback for students                                                  |

Content safety is applied via `bots/guardrails.py::check_student_output_safety()` before returning agent responses to the client.

**All agent instantiation goes through `bots/provider.py::get_bot_provider()`** — services never import agent classes directly. This is what makes `MOCK_AI=true` (env) and `set_bot_provider(MockBotProvider())` (tests) work: swapping the provider swaps every agent at once without touching service code.

---

## Data Tables Reference

See [data_access/DATA_TABLES.md](data_access/DATA_TABLES.md).
