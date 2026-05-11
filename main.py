from dotenv import load_dotenv

load_dotenv()

import logging
import time

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

_req_log = logging.getLogger("eduquest.request")

from routers import conversation, period, ltg, teacher, waitlist
from routers import auth, user, enrollment, quest, parent
from routers import curriculum, billing
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError
from exceptions.auth_error import AuthError
from exceptions.permission_error import PermissionError


@asynccontextmanager
async def lifespan(app: FastAPI):
    from integrations.s3_service import s3, BUCKET_NAME
    _log = logging.getLogger(__name__)
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        _log.info("S3 OK — bucket=%s endpoint=%s", BUCKET_NAME, s3.meta.endpoint_url)
    except Exception as e:
        _log.error("S3 connectivity FAILED — bucket=%s error=%s", BUCKET_NAME, e)
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


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(status_code=401, content={"error": str(exc)})


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(status_code=403, content={"error": str(exc)})


_logger = logging.getLogger(__name__)


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
app.include_router(billing.router, prefix="/billing")


@app.get("/helloworld")
def hello() -> str:
    return "helloworld"
