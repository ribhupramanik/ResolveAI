from src.rag.pipeline import ResolveAIPipeline
from src.rag.prompt_builder import PromptPayload
from src.rag.response_validator import ValidationIssue


def test_refund_state_claim_adds_specific_retry_instructions():
    original_prompt = PromptPayload(
        system_prompt="You are ResolveAI, a customer support assistant.",
        user_prompt=("I want to initiate a refund for order ORD-10002."),
    )

    issue = ValidationIssue(
        code="unsupported_refund_state_claim",
        message=(
            "The refund was described as processing, "
            "but the eligibility tool reports action_performed=False."
        ),
        matched_text="The refund is currently processing",
    )

    retry_prompt = ResolveAIPipeline._build_retry_prompt(
        original_prompt,
        [issue],
    )

    retry_text = retry_prompt.user_prompt.lower()

    assert retry_prompt.system_prompt == original_prompt.system_prompt

    assert "unsupported_refund_state_claim" in retry_text

    assert "the order may be processing" in retry_text

    assert "the refund has not been initiated" in retry_text

    assert "eligibility checking does not initiate a refund" in retry_text

    assert "explicit customer confirmation is required" in retry_text

    assert "describe the refund eligibility" in retry_text

    assert "do not claim the refund is processing" in retry_text
