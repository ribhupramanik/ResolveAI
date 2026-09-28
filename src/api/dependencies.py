from fastapi import Request

from src.rag.pipeline import ResolveAIPipeline


def get_pipeline(
    request: Request,
) -> ResolveAIPipeline:

    return request.app.state.pipeline
