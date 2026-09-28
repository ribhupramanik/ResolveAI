from fastapi import FastAPI

app = FastAPI(
  title="Resolve API",
  description=(
    "API for ResolveAI customer-support "
    "intelligence platform"
  ),
  version="0.1.0"
)

@app.get("/api/v1/health")
def health_check():
  return{
    "status": "ok",
    "service": "ResolveAI",
  }