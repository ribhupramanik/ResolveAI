from dataclass import dataclass

from src.rag.context_builder import(ContextBuilder, RetrievedContext)

from src.rag.generator import(GeneratedResponse, Generator)

from src.rag.prompt_builder import(PromptBuilder, PromptPayload)

from src.rag.response_validator import(ResponseValidator, ValidationIssue)

SAFE_FALLBACK = (
  "I'm sorry, but I don't have enough verified information to provide a reliable response. "
  "Please provide any relevant order, transaction, or account details or contact a human support agent for further assistance"
)

@dataclass
class RAGResult:
  test:str
  provider: str | None
  model: str | None

  retrieved_count: int
  attempts: int
  used_fallback: bool

  validation_issues: list[ValidationIssue]

class ResolveAPIPipeline:
  def __init__(
      self,
      generator: Generator,
      context_builder: None,
      prompt_builder: None,
      validator: None
  ):
    self.generator: generator

    self.context_builder = (
      context_builder
      if context_builder is not None
      else ContextBuilder()
    )

    self.prompt_builder = (
      prompt_builder
      if prompt_builder is not None
      else PromptBuilder()
    )

    self.validator = (
      validator
      if validator is not None
      else ResponseValidator()
    )

  def run(self, query: str)-> RAGResult:
    if not isinstance(query, str):
      raise TypeError("Query must be a string")

    if not query.strip():
      raise ValueError("Query cannot be empty")

    retrieved_context=(self.context_builder.build(query))

    prompt = (self.prompt_builder.build(query, retrieved_context))

    # First Generation Attempt

    first_response = (self.generator.generate(prompt))

    first_validation = (
      self.validator.validate(
        first_response.text,
        query,
        retrieved_context
      )
    )

    if first_validation.is_valid:
      return RAGResult(
        text=first_response.text,
        provider=first_response.provider,
        model=first_response.model,
        retrieved_count=(retrieved_context.retrieved_count),
        attempts=1,
        used_fallback=False,
        validation_issues=[]
      )

    # Retry using validator feedback.

    retry_prompt = (
      self.build_retry_prompt(prompt, first_validation.issues)
    )

    second_response = ( self.generator.generate(retry_prompt))

    second_validation = (self.validator.validate(second_response.text, query, retrieved_context))

    if second_validation.is_valid:

      return RAGResult(
        text=second_response.text,
        provider=second_response.provider,
        model=second_response.model,
        retrieved_count=(retrieved_context.retrieved_count),
        attempts=2,
        used_fallback=False,
        validation_issues=(
          first_validation.issues
        ),
      )

    # Both generation failed validation.

    all_issues = (
      first_validation.issues + second_validation.issues
    )

    return RAGResult(
      text = SAFE_FALLBACK,
      provider = second_response.provider,
      model = second_response.model,
      retrieved_count=(retrieved_context.retrieved_count),
      attempts=2,
      used_fallback=True,
      validation_issues=all_issues
    )

  @staticmethod
  def _build_retry_prompt(
    original_prompt: PromptPayload,
    issues: list[ValidationIssue],
  ) -> PromptPayload:

    issue_lines=[]

    for issue in issues:
      issue_lines.append(
        (  # noqa: UP034
          f"-{issue.code}: "
          f"{issue.matched_text}"
        )
      )

    feedback = "\n".join(issue_lines)

    retry_user_prompt = f"""
{original_prompt.user_prompt}

VALIDATION FEEDBACK FROM THE PREVIOUS DRAFT:

The previous response was rejected because it contained the following unsupported
content:

{feedback}

Rewrite the response.

Do not repeat any of the flagged claims.
Do not add unsupported facts, numbers, actions, timelines, policies, or promises.
""".strip()

    return PromptPayload(
      system_prompt=(
        original_prompt.system_prompt
      ),
      user_prompt=retry_user_prompt
    )
      

