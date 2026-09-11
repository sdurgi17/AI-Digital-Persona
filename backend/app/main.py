from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import agent, chat, documents, health, interview, llm_gateway, persona, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Digital Persona", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(interview.router, prefix="/api/interview", tags=["interview"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(persona.router, prefix="/api/persona", tags=["persona"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(llm_gateway.router, prefix="/v1", tags=["gateway"])
