# FastAPI Response Models — Implementation Plan

## Why

Right now every router endpoint returns a raw `dict` from the service layer. FastAPI can't validate or document these. Adding `response_model=` to each decorator:

- Generates accurate OpenAPI schemas at `/docs`
- Strips unexpected fields from responses (security benefit)
- Catches service-layer bugs at the boundary (wrong field names, missing fields)

## When to do this

Add response models **during** each route migration from Flask → FastAPI, not before (Flask doesn't support `response_model=`) and not after (you'd have to re-read all the service code a second time). When you migrate a route, you're already reading what the service returns — define the model then.

## Where to put response models

No separate `api/schemas/` directory needed. Two rules:

1. **Reuse `models/` directly** when the endpoint returns a single DB record as-is (e.g. `GET /period-schedule` can use `response_model=PeriodSchedule` from `models/period_schedule.py`)
2. **Define inline in the router** for shapes that are endpoint-specific — this is already the pattern for request body models

Only create a shared file if the same response shape is needed across multiple routers (rare).

## How to apply

```python
# Reusing an existing model
from models.period_schedule import PeriodSchedule

@router.get("/period-schedule", response_model=PeriodSchedule)
def get_period_schedule(...):
    ...
    return period_schedule_service.get_schedule(...)  # FastAPI coerces dict → model

# Inline response model for a composite/AI shape
class LTGAgentResponse(BaseModel):
    message: str
    goal_1: Optional[str] = None
    goal_2: Optional[str] = None
    goal_3: Optional[str] = None

class LTGInitResponse(BaseModel):
    conversation_id: str
    response: LTGAgentResponse
    resumed: bool

@router.post("/initiate-ltg-conversation", response_model=LTGInitResponse)
def initiate_ltg_conversation(...):
    ...
    return period_service.initiate_ltg_conversation(...)
```

FastAPI coerces the returned dict into the response model automatically — no changes needed in the service layer.

## Endpoint-by-endpoint reference

### `api/routers/conversation.py`

| Endpoint | Strategy | Notes |
|---|---|---|
| `POST /initiate-profile-assistant` | inline | trace `conversation_service.start_profile_assistant()` return shape |
| `POST /continue-profile-assistant` | inline | likely `{message: str, conversation_id: str}` |
| `POST /initiate-update-assistant` | inline | dual-mode (multipart vs JSON) — check both branches return the same shape |
| `POST /continue-update-assistant` | inline | likely `{message: str}` |

### `api/routers/period.py`

| Endpoint | Strategy | Notes |
|---|---|---|
| `POST /initiate-ltg-conversation` | inline | `{conversation_id, response: {message, goal_1, goal_2, goal_3}, resumed}` |
| `POST /continue-ltg-conversation` | inline | `{response: str, goal_chosen: bool}` |
| `POST /initiate-homework-agent` | inline | trace `period_service.start_homework_agent()` |

### `api/routers/teacher.py`

| Endpoint | Strategy | Notes |
|---|---|---|
| `POST /create-period` | inline | `{message, period: {...}, schedule: Optional[...]}` — schedule can be None if generation fails |
| `GET /get-file/{key}` | **skip** | returns `StreamingResponse` — `response_model=` conflicts with streaming |
| `POST /canvas/courses` | inline | `{courses: [{id: int, name: str}]}` — simple, define inline |
| `POST /period-schedule/generate` | inline | trace `generate_and_save_schedule()` return |
| `GET /period-schedule` | reuse `PeriodSchedule` from `models/` | verify field names match exactly |
| `PUT /period-schedule` | reuse `PeriodSchedule` from `models/` | |
| `PUT /period-schedule/quest-weeks` | inline | trace `set_quest_weeks()` return |

### `api/routers/waitlist.py`

| Endpoint | Strategy | Notes |
|---|---|---|
| `GET /status` | inline | trace `WaitlistService.get_status()` |
| `POST /join` | inline | check both paths: already on waitlist vs newly added — must share same model |

## Tricky cases

**`initiate-update-assistant`** — multipart and JSON paths must return the same shape, or use `Optional` fields to cover both.

**`create-period`** — `schedule` is `Optional` because auto-generation is silently caught on failure.

**`GET /get-file/{key}`** — do not add `response_model=`. `StreamingResponse` bypasses FastAPI's response handling entirely.

**`GET /period-schedule`** — if reusing `PeriodSchedule` from `models/`, double-check that the service returns all non-optional fields. The model has `Optional` fields for `schedule_data` etc. — verify.

## Suggested migration order

1. `waitlist.py` — smallest, shapes are simple
2. `period.py` — LTG shapes are already known from `ltg_service.py`
3. `conversation.py` — requires tracing service return values carefully
4. `teacher.py` — most complex (multipart, StreamingResponse, nested schedule dict)
