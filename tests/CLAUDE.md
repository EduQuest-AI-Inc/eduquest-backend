# CLAUDE.md — Tests

For rationale behind these testing decisions, see [ARCH_DECISIONS.md](../ARCH_DECISIONS.md) → Testing Decisions.

## Rules

- **Mock via constructor injection, not patching.** Pass `MockBotProvider()` directly to the service constructor — no `@patch`, no `sys.modules` stubbing, no `patch("services.X.get_bot_provider")`. Exception: `conftest.py` stubs individual bot modules (e.g. `bots.grading_agent`) with `MagicMock()` and marks them `# arch-ok` — these are import-guard stubs that prevent OpenAI SDK import-time failures, not behavior fakes. Do not add new `sys.modules['bots.*']` stubs without `# arch-ok` and a comment explaining why.
- **`MockBotProvider` must satisfy `BotProviderProtocol`.** Verified by `tests/unit/bots/test_provider_compliance.py`. Any new factory method added to `BotProvider` must be added to both `BotProviderProtocol` and `MockBotProvider` before merge.
- **Private methods are tested through public API only.** No direct calls to `_underscore` methods. If a private method is too complex to cover via the public path, extract it to a public function in a utility module.
- **Thin facade services have no unit tests.** `period_service.py` and `quest_service.py` are one-liner delegators — test the sub-services where logic lives (`period_quest_service.py`, `quest_creation_service.py`, etc.).
- **`services/tracking/` is intentionally untested.** PostHog calls are fire-and-forget; failures are swallowed. Schema verification belongs in the PostHog test environment, not unit tests.
- **Agent tests** live in `tests/unit/bots/` (provider compliance, tracing/model config, grading/provider behavior, slideshow agents) and `tests/unit/slides/` for rendering/generation service tests.
- **Slides agent tests** live in `tests/unit/bots/` (`test_content_writer_agent.py`, `test_orchestrator_agent.py`, `test_visual_review_agent.py`) and `tests/unit/slides/` for generation service tests.
- **No `PYTEST_CURRENT_TEST` guards in production code.** Test-mode detection in production code is banned.
- **Response model field types must match DB column types.** Mismatches cause silent data corruption.

## Test Layout

```
tests/
├── unit/
│   ├── bots/           # Agent unit tests (provider compliance, tracing/model config, grading, slideshow agents)
│   ├── data_access/    # DAO unit tests
│   ├── integrations/   # Integration adapter unit tests
│   ├── routes/         # Router handler unit tests
│   ├── services/       # Service unit tests, organized by feature subdirectory
│   │   ├── auth/, billing/, conversation/, curriculum/,
│   │   ├── enrollment/, knowledge_graph/, period/, quest/, slides/
│   │   └── plus legacy top-level service tests for parent/user/waitlist
│   └── slides/         # Slides generation service tests
└── integration/        # Full-stack integration tests (requires live Supabase)
```

## Running Tests

```bash
# From the repo root (uses venv binary directly):
eduquest-backend/venv/bin/pytest eduquest-backend/tests/unit/
pytest -m unit
pytest -m integration
pytest -m auth
pytest tests/test_teacher_dao.py
pytest --cov=. --cov-report=html
```

Configuration in [pytest.ini](../pytest.ini). Markers: `unit`, `integration`, `auth`, `api`, `smoke`, `slow`.
