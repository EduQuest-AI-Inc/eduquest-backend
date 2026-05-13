# CLAUDE.md — Bots

For rationale behind bot provider selection and `@function_tool` boundary rules, see [ARCH_DECISIONS.md](../ARCH_DECISIONS.md).

## Rules

- **All type annotations use `BotProviderProtocol`** from `bots/protocol.py`, never concrete classes.
- **Individual bot classes are never imported or instantiated outside `bots/provider.py`.** Direct imports bypass the abstraction and silently run wrong config on provider swap.
- **`@function_tool` bodies do nothing except call one named public function and return its result.** All logic lives in the extracted function (in `utils/` if pure with injected deps, in a dedicated service if it needs DAO/provider wiring).
- **No `os.getenv("MOCK_AI")` after startup.** Provider is selected once in `main.py` lifespan and stored in `app.state.bot_provider`. Use `get_bot_provider()` from `api/deps.py` to read it.
- **No module-level instantiation in `bots/tools/`.** Use lazy initialization for singletons.
- **Services never call `get_bot_provider()` directly.** The router injects `bot_provider` via `Depends()` and passes it to the service constructor as `bot_provider: BotProviderProtocol`.

## Agents

All agent code uses OpenAI Agents SDK (`from agents import Agent, Runner`).

- `grading_agent.py` (`GradingOrchestrator`) — produces per-skill float scores (0.0–1.0); results written to `aggregated_metrics` via `AggregatedMetricsDAO`
- `schedule_agent.py` (`PeriodScheduleAgent`) — generates Week→Lesson→Concept→Skill hierarchy; accepts `research_context` (from Perplexity) to fill gaps when no files are uploaded
- `coverage_evaluator.py` (`CoverageEvaluator`) — single structured call; returns `sufficient`, `gaps`, `research_queries`; used before schedule generation to decide whether to call Perplexity
- `ltg_agent.py` — long-term goal agent
- `profile_agent.py` — student profile agent
- `teacher_feedback_agent.py` — teacher feedback agent
- `guardrails.py` — content safety guardrails
- `provider.py` — `BotProvider` factory; `_mocks.py` — `MockBotProvider` and mock agents for tests

## Perplexity Integration

`integrations/perplexity_service.py` (`PerplexityService`) calls `POST https://api.perplexity.ai/v1/agent` with `{"preset": "deep-research", "input": ...}` via `httpx`. Response text is at `output[-1]["content"][0]["text"]` (last item of type "message" in `output` array). This is **not** the OpenAI-compatible `/chat/completions` endpoint.

## Slideshow / PPTX Pipeline

Each generation is a stateless fresh `Runner.run()` call with `max_turns=80` (unlike conversation agents which use a stateful `OpenAIConversationsSession`).

**Agent chain:** `PptxAgent → OrchestratorAgent → ContentWriterAgent / VisualReviewAgent / SLIDE_TOOLS`

- `slideshow/pptx_agent.py` (`PptxAgent`) — entry point; calls `OrchestratorAgent().run_async()`, renders `CompleteSlideDeck` to `.pptx` (`utils/rendering/pptx_renderer.py`) and HTML (`utils/rendering/html_renderer.py`); returns `{"pptx_bytes": bytes, "html_str": str}`
- `slideshow/orchestrator_agent.py` (`OrchestratorAgent`) — designs deck, calls specialists via `SLIDE_TOOLS`
- `slideshow/content_writer_agent.py` (`ContentWriterAgent`) — writes `title`, `bullets`, `speaker_notes` per slide
- `slideshow/visual_review_agent.py` (`VisualReviewAgent`) — reviews images; returns `approved`, `regenerate`, or `flag`
- `bots/tools/` — `SLIDE_TOOLS` are `@function_tool` wrappers: `content_tool`, `image_tool`, `chart_tool`, `review_tool`, `html_tool`

**Status lifecycle:** `LessonPptx` rows transition `pending → generating → done | failed`. Managed by `services/slides/pptx_generation_service.py`.

**Mock:** `MockPptxAgent` in `bots/_mocks.py` generates a minimal real `.pptx` and non-empty `html_str`. `MockBotProvider.create_pptx_agent()` returns it.
