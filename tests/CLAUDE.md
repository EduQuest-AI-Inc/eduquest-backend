# CLAUDE.md — Tests

For rationale behind these testing decisions, see [ARCH_DECISIONS.md](../ARCH_DECISIONS.md) → Testing Decisions.

## Rules

- **Mock via constructor injection, not patching.** Pass `MockBotProvider()` directly to the service constructor — no `@patch`, no `sys.modules` stubbing, no `patch("services.X.get_bot_provider")`.
- **`MockBotProvider` must satisfy `BotProviderProtocol`.** Verified by `tests/unit/bots/test_provider_compliance.py`. Any new factory method added to `BotProvider` must be added to both `BotProviderProtocol` and `MockBotProvider` before merge.
- **Private methods are tested through public API only.** No direct calls to `_underscore` methods. If a private method is too complex to cover via the public path, extract it to a public function in a utility module.
- **Thin facade services have no unit tests.** `period_service.py` and `quest_service.py` are one-liner delegators — test the sub-services where logic lives (`period_quest_service.py`, `quest_creation_service.py`, etc.).
- **`services/tracking/` is intentionally untested.** PostHog calls are fire-and-forget; failures are swallowed. Schema verification belongs in the PostHog test environment, not unit tests.

## Running Tests

```bash
# From eduquest-backend/ with venv active:
eduquest-backend/venv/bin/pytest eduquest-backend/tests/unit/
pytest -m unit
pytest -m integration
pytest -m auth
pytest tests/test_teacher_dao.py
pytest --cov=. --cov-report=html
```

Configuration in [pytest.ini](../pytest.ini). Markers: `unit`, `integration`, `auth`, `api`, `smoke`, `slow`.
