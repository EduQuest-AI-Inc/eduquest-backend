from dotenv import load_dotenv

load_dotenv()

import logging
import time
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s  %(name)s - %(message)s",
    force=True,
)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os


def _validate_env() -> None:
    """Fail fast at startup if required environment variables are missing."""
    _log = logging.getLogger(__name__)
    mock_ai = os.getenv("MOCK_AI", "").lower() in ("true", "1", "yes")

    required = [
        "JWT_SECRET_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_JWT_SECRET",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "S3_BUCKET_NAME",
        "STRIPE_SECRET_KEY",
        # STRIPE_WEBHOOK_SECRET is validated lazily in the webhook route handler,
        # so it is intentionally omitted here to allow local dev without it.
    ]

    # AI keys are only required when running live agents
    if not mock_ai:
        required += [
            "OPENAI_API_KEY",
            "PERPLEXITY_API_KEY",
            "GEMINI_API_KEY",
        ]

    missing = [var for var in required if not os.getenv(var)]

    # region agent log
    try:
        with open("/Users/goldenhuang/Desktop/EduQuest/.cursor/debug-1c3679.log", "a", encoding="utf-8") as _debug_file:
            _debug_file.write(json.dumps({
                "sessionId": "1c3679",
                "runId": "pre-fix",
                "hypothesisId": "backend-env-loading-or-required-key-drift",
                "location": "main.py:_validate_env",
                "message": "backend env validation snapshot",
                "data": {
                    "cwd": os.getcwd(),
                    "dotenv_exists_in_cwd": os.path.exists(os.path.join(os.getcwd(), ".env")),
                    "required_count": len(required),
                    "missing": missing,
                    "present": {var: bool(os.getenv(var)) for var in required},
                    "mock_ai": mock_ai,
                },
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # endregion

    if missing:
        _log.critical(
            "Missing required environment variables — server cannot start:\n  %s",
            "\n  ".join(missing),
        )
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    _log.info("Environment validation passed (%d required vars present)", len(required))


_req_log = logging.getLogger("eduquest.request")

from routers import conversation, period, ltg, teacher, waitlist
from routers import auth, user, enrollment, quest, parent
from routers import curriculum, billing, lessons, slides, feedback
from routers import marketplace
from routers import demo_quest
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError
from exceptions.auth_error import AuthError
from exceptions.permission_error import PermissionError


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log = logging.getLogger(__name__)

    _validate_env()

    if os.getenv("MOCK_AI", "").lower() in ("true", "1", "yes"):
        from bots.provider import MockBotProvider
        from bots.protocol import BotProviderProtocol
        provider: BotProviderProtocol = MockBotProvider()
        _log.info("Bot provider: MockBotProvider (MOCK_AI=true)")
    else:
        from bots.provider import BotProvider
        from bots.protocol import BotProviderProtocol
        provider: BotProviderProtocol = BotProvider()
        _log.info("Bot provider: BotProvider (live OpenAI)")
    app.state.bot_provider = provider

    from integrations.s3_service import s3, BUCKET_NAME
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        _log.info("S3 OK — bucket=%s endpoint=%s", BUCKET_NAME, s3.meta.endpoint_url)
    except Exception as e:
        _log.error("S3 connectivity FAILED — bucket=%s error=%s", BUCKET_NAME, e)

    from data_access.period_dao import PeriodDAO
    reset_count = PeriodDAO().reset_stale_generating()
    if reset_count:
        _log.warning("Reset %d stale 'generating' period(s) to 'failed' at startup", reset_count)
    else:
        _log.info("No stale 'generating' periods found at startup")

    yield


app = FastAPI(title="EduQuest Agent Service", lifespan=lifespan)

allowed_origins = [
    "https://eduquestai.org",
    "https://www.eduquestai.org",
    "http://eduquestai.org",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

api_gateway_url = os.getenv("API_GATEWAY_URL")
if api_gateway_url:
    allowed_origins.append(api_gateway_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    ms = (time.monotonic() - start) * 1000
    _req_log.info(
        "%s %s %s %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        ms,
    )
    return response


_logger = logging.getLogger(__name__)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    _logger.warning("ValidationError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError):
    _logger.info("NotFoundError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    _logger.warning("AuthError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=401, content={"error": str(exc)})


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    _logger.info("PermissionError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=403, content={"error": str(exc)})


try:
    import openai as _openai
    _openai_RateLimitError = _openai.RateLimitError
    _openai_AuthenticationError = _openai.AuthenticationError
    _openai_APIError = _openai.APIError
    _openai_handlers_available = all(
        isinstance(cls, type) and issubclass(cls, Exception)
        for cls in (_openai_RateLimitError, _openai_AuthenticationError, _openai_APIError)
    )
except (ImportError, AttributeError, TypeError):
    _openai_handlers_available = False


if _openai_handlers_available:
    @app.exception_handler(_openai_RateLimitError)
    async def openai_rate_limit_handler(request: Request, exc):
        _logger.error("OpenAI quota/rate-limit on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"error": "AI service quota exceeded or rate-limited. Please try again later or contact support."},
        )

    @app.exception_handler(_openai_AuthenticationError)
    async def openai_auth_error_handler(request: Request, exc):
        _logger.error("OpenAI authentication failure on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"error": "AI service authentication failed. Please contact support."},
        )

    @app.exception_handler(_openai_APIError)
    async def openai_api_error_handler(request: Request, exc):
        _logger.error("OpenAI API error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=502,
            content={"error": f"AI service error: {type(exc).__name__}"},
        )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    _logger.error("Unhandled exception: %s %s — %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})



app.include_router(auth.router, prefix="/auth")
app.include_router(conversation.router, prefix="/conversation")
app.include_router(enrollment.router, prefix="/enrollment")
app.include_router(parent.router, prefix="/parent")
app.include_router(period.router, prefix="/period")
app.include_router(ltg.router, prefix="/period")
app.include_router(quest.router, prefix="/quest")
app.include_router(teacher.router, prefix="/teacher")
app.include_router(user.router, prefix="/user")
app.include_router(waitlist.router, prefix="/pilot-waitlist")
app.include_router(curriculum.router, prefix="/curriculum")
app.include_router(lessons.router, prefix="/lessons")
app.include_router(slides.router, prefix="/slides")
app.include_router(billing.router, prefix="/billing")
app.include_router(feedback.router, prefix="/feedback")
app.include_router(marketplace.router, prefix="/marketplace")
app.include_router(demo_quest.router, prefix="/demo")


@app.get("/helloworld")
def hello() -> str:
    return "helloworld"
