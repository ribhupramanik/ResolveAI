from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.rate_limit import AIRateLimitMiddleware
from src.api.routes import (
    chat,
    conversations,
    demo_orders,
    health,
    orders,
)
from src.rag.pipeline import ResolveAIPipeline
from src.rag.providers.groq_provider import GroqGenerator


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    app.state.pipeline = ResolveAIPipeline(generator=GroqGenerator())

    yield


app = FastAPI(
    title="ResolveAI API",
    description=("API for the ResolveAI customer-support intelligence platform."),
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    AIRateLimitMiddleware,
    max_requests=10,
    window_seconds=60,
    max_daily_requests=30,
    daily_window_seconds=86400,
    max_concurrent_requests=1,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://resolve-ai-omega-lime.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    health.router,
    prefix="/api/v1",
)

app.include_router(
    chat.router,
    prefix="/api/v1",
)

app.include_router(
    conversations.router,
    prefix="/api/v1",
)

app.include_router(
    orders.router,
    prefix="/api/v1",
)

app.include_router(
    demo_orders.router,
    prefix="/api/v1",
)
