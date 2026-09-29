from dataclasses import dataclass

from src.rag.context_builder import ContextBuilder
from src.rag.conversation import ConversationTurn
from src.rag.generator import Generator
from src.rag.knowledge_retriever import KnowledgeRetriever
from src.rag.prompt_builder import PromptBuilder, PromptPayload
from src.rag.response_validator import ResponseValidator, ValidationIssue
from src.rag.system_capabilities import SystemCapabilitiesProvider

SAFE_FALLBACK = (
    "I'm sorry, but I don't have enough verified information "
    "to provide a reliable response. I cannot provide a "
    "verified next step without guessing."
)


@dataclass
class RAGResult:
    text: str
    provider: str | None
    model: str | None

    retrieved_count: int

    verified_knowledge_count: int
    verified_knowledge_topics: list[str]

    system_capability_count: int
    system_capabilities: list[str]

    attempts: int
    used_fallback: bool

    validation_issues: list[ValidationIssue]


class ResolveAIPipeline:
    def __init__(
        self,
        generator: Generator,
        context_builder: ContextBuilder | None = None,
        knowledge_retriever: KnowledgeRetriever | None = None,
        system_capabilities_provider: SystemCapabilitiesProvider | None = None,
        prompt_builder: PromptBuilder | None = None,
        validator: ResponseValidator | None = None,
    ):
        self.generator = generator

        self.context_builder = (
            context_builder if context_builder is not None else ContextBuilder()
        )

        self.prompt_builder = (
            prompt_builder if prompt_builder is not None else PromptBuilder()
        )

        self.validator = validator if validator is not None else ResponseValidator()

        self.knowledge_retriever = (
            knowledge_retriever
            if knowledge_retriever is not None
            else KnowledgeRetriever()
        )

        self.system_capabilities_provider = (
            system_capabilities_provider
            if system_capabilities_provider is not None
            else SystemCapabilitiesProvider()
        )

    def run(
        self,
        query: str,
        conversation_history: list[ConversationTurn] | None = None,
    ) -> RAGResult:

        if not isinstance(query, str):
            raise TypeError("Query must be a string")

        if not query.strip():
            raise ValueError("Query cannot be empty")

        history = conversation_history or []

        contextual_query = self._build_contextual_query(
            query,
            history,
        )

        knowledge_query = self._build_knowledge_query(
            query,
            history,
        )

        retrieved_context = self.context_builder.build(contextual_query)

        verified_knowledge = self.knowledge_retriever.build(knowledge_query)

        system_capabilities = self.system_capabilities_provider.build()
        prompt = self.prompt_builder.build(
            query,
            retrieved_context,
            verified_knowledge,
            system_capabilities,
            history,
        )

        # First Generation Attempt

        first_response = self.generator.generate(prompt)

        first_validation = self.validator.validate(
            first_response.text,
            contextual_query,
            verified_knowledge,
            system_capabilities,
        )

        if first_validation.is_valid:
            return RAGResult(
                text=first_response.text,
                provider=first_response.provider,
                model=first_response.model,
                retrieved_count=(retrieved_context.retrieved_count),
                verified_knowledge_count=(verified_knowledge.retrieved_count),
                verified_knowledge_topics=(verified_knowledge.topics),
                system_capability_count=(system_capabilities.capability_count),
                system_capabilities=(system_capabilities.capabilities),
                attempts=1,
                used_fallback=False,
                validation_issues=[],
            )

        # Retry using validator feedback.

        retry_prompt = self._build_retry_prompt(prompt, first_validation.issues)

        second_response = self.generator.generate(retry_prompt)

        second_validation = self.validator.validate(
            second_response.text,
            contextual_query,
            verified_knowledge,
            system_capabilities,
        )

        if second_validation.is_valid:
            return RAGResult(
                text=second_response.text,
                provider=second_response.provider,
                model=second_response.model,
                retrieved_count=(retrieved_context.retrieved_count),
                verified_knowledge_count=(verified_knowledge.retrieved_count),
                verified_knowledge_topics=(verified_knowledge.topics),
                system_capability_count=(system_capabilities.capability_count),
                system_capabilities=(system_capabilities.capabilities),
                attempts=2,
                used_fallback=False,
                validation_issues=(first_validation.issues),
            )

        # Both generation failed validation.

        all_issues = first_validation.issues + second_validation.issues

        return RAGResult(
            text=SAFE_FALLBACK,
            provider=second_response.provider,
            model=second_response.model,
            retrieved_count=(retrieved_context.retrieved_count),
            verified_knowledge_count=(verified_knowledge.retrieved_count),
            verified_knowledge_topics=(verified_knowledge.topics),
            system_capability_count=(system_capabilities.capability_count),
            system_capabilities=(system_capabilities.capabilities),
            attempts=2,
            used_fallback=True,
            validation_issues=all_issues,
        )

    @staticmethod
    def _build_contextual_query(
        query: str,
        conversation_history: list[ConversationTurn],
    ) -> str:

        previous_customer_messages = [
            turn.content.strip()
            for turn in conversation_history
            if (turn.role == "user" and turn.content.strip())
        ]

        recent_customer_messages = previous_customer_messages[-3:]

        return "\n".join(
            [
                *recent_customer_messages,
                query.strip(),
            ]
        )

    @staticmethod
    def _build_knowledge_query(
        query: str,
        conversation_history: list[
            ConversationTurn
        ],
    ) -> str:

        normalized_query = (
            query.lower().strip()
        )

        ambiguous_phrases = (
            "do that",
            "do it",
            "how can i do that",
            "how do i do that",
            "how can i do it",
            "how do i do it",
            "what about that",
            "what about it",
            "can i do that",
            "can i do it",
        )

        is_ambiguous = any(
            phrase in normalized_query
            for phrase in ambiguous_phrases
        )

        if not is_ambiguous:
            return query.strip()

        previous_customer_messages = [
            turn.content.strip()
            for turn in conversation_history
            if (
                turn.role == "user"
                and turn.content.strip()
            )
        ]

        if not previous_customer_messages:
            return query.strip()

        previous_message = (
            previous_customer_messages[-1]
        )

        return "\n".join(  # noqa: FLY002
            [
                previous_message,
                query.strip(),
            ]
        )

    @staticmethod
    def _build_retry_prompt(
        original_prompt: PromptPayload,
        issues: list[ValidationIssue],
    ) -> PromptPayload:

        issue_lines = []

        for issue in issues:
            issue_lines.append(
                (  # noqa: UP034
                    f"- {issue.code}: {issue.matched_text}\n  Reason: {issue.message}"
                )
            )

        feedback = "\n".join(issue_lines)

        # Build retry instructions based on
        # the types of validation failures.
        issue_codes = {issue.code for issue in issues}

        retry_rules = []

        if "unsupported_action_claim" in issue_codes:
            retry_rules.append(
                "- Do not claim that ResolveAI can check, "
                "investigate, modify, process, forward, "
                "route, transfer, escalate, contact, or "
                "perform any external action."
            )

        if "unsupported_support_route_claim" in issue_codes:
            retry_rules.append(
                "- Do not mention or recommend a support "
                "team, customer-support department, help "
                "center, support representative, support "
                "agent, or escalation route unless it is "
                "explicitly verified."
            )

        if "unsupported_third_party_claim" in issue_codes:
            retry_rules.append(
                "- Do not recommend contacting, calling, "
                "emailing, checking with, or reaching out "
                "to a merchant, bank, payment provider, "
                "courier, carrier, or other third party."
            )

        if "unsupported_numeric_claim" in issue_codes:
            retry_rules.append(
                "- Remove numerical claims, durations, "
                "deadlines, percentages, prices, or "
                "quantities that are not explicitly "
                "supported by the customer request or "
                "authoritative evidence."
            )

        if "unresolved_placeholder" in issue_codes:
            retry_rules.append("- Remove all unresolved template placeholders.")

        retry_rule_text = "\n".join(retry_rules)

        retry_user_prompt = f"""
    {original_prompt.user_prompt}

    VALIDATION FEEDBACK FROM THE PREVIOUS DRAFT:

    The previous response was rejected because it contained
    unsupported content:

    {feedback}

    REQUIRED CORRECTIONS:

    {retry_rule_text}

    Rewrite the response from scratch.

    Do not merely paraphrase the rejected claims.

    Do not repeat any flagged action, support route,
    third-party recommendation, unsupported numerical
    claim, placeholder, timeline, policy, or promise.

    If the verified evidence only establishes a limitation,
    state that limitation clearly.

    If no verified next step exists, say that no verified
    next step is available.

    Do not invent an alternative action, support route,
    third-party procedure, timeline, policy, capability,
    or contact method.

    Return only the corrected customer-facing response.
    """.strip()

        return PromptPayload(
            system_prompt=original_prompt.system_prompt,
            user_prompt=retry_user_prompt,
        )
