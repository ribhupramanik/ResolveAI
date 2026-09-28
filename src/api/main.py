from fastapi import FastAPI

from src.api.schemas.chat import ChatRequest, ChatResponse

app = FastAPI(
    title="Resolve API",
    description=("API for ResolveAI customer-support intelligence platform"),
    version="0.1.0",
)


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "service": "ResolveAI",
    }


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(
    requests: ChatRequest,
) -> ChatResponse:

    return ChatResponse(message=(f"ResolveAI received: {requests.message}"))
