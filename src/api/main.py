from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import (
    chat,
    health,
)
from src.rag.pipeline import (
    ResolveAIPipeline,
)
from src.rag.providers.groq_provider import (
    GroqGenerator,
)


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


app.include_router(
    health.router,
    prefix="/api/v1",
)

app.include_router(
    chat.router,
    prefix="/api/v1",
)
