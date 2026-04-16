from dotenv import load_dotenv

# Load environment variables BEFORE any other imports so feature flags
# (e.g. USE_SUPABASE) are available at module import time.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import conversation, period, teacher, waitlist

app = FastAPI(title="EduQuest Agent Service")

allowed_origins = [
    "https://eduquestai.org",
    "https://www.eduquestai.org",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

app.include_router(conversation.router, prefix="/conversation")
app.include_router(period.router, prefix="/period")
app.include_router(teacher.router, prefix="/teacher")
app.include_router(waitlist.router, prefix="/pilot-waitlist")


@app.get("/helloworld")
def hello():
    return "helloworld"
