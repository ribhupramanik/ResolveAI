from dataclasses import dataclass

from src.retrieval.pgvector_retriever import (
  PgVectorRetriever,
)

DEFAULT_TOP_K = 5

DEFAULT_MIN_SIMILARITY = 0.50

@dataclass
class RetrievedContext:
  context: str
  retrieved_count: int
  max_similarity: float | None
  min_similarity: float | None

class ContextBuilder:
  def __init__(
      self,
      retriever = None,
      top_k: int = DEFAULT_TOP_K,
      min_similarity: float = DEFAULT_MIN_SIMILARITY,
  ):

    self.retriever = ( retriever if retriever is not None else PgVectorRetriever())

    self.top_k = top_k
    self.min_similarity = ( min_similarity )

  def build( self, query: str, ) -> RetrievedContext:
    results = (
      self.retriever.search( query, top_k=self.top_k, )
    )

    if results.empty:
      return RetrievedContext(
        context="",
        retrieved_count=0,
        max_similarity=None,
        min_similarity=None,
      )

    results = results[results["similarity"] >= self.min_similarity].copy()

    if results.empty:
      return RetrievedContext(
          context="",
          retrieved_count=0,
          max_similarity=None,
          min_similarity=None,
      )

    # Avoid giving the LLM repeated copies of the same evidence
    results = (
      results.drop_duplicates(
        subset=[
          "processed_instruction",
          "response",
        ]
      ).reset_index(
        drop=True
      )
    )

    context_parts = []

    for index, row in (
      results.iterrows()
    ):

      context_parts.append(
        "\n".join(
            [
                f"Example {index + 1}",
                (
                    "Customer request: "
                    f"{row['instruction']}"
                ),
                (
                    "Historical resolution: "
                    f"{row['response']}"
                ),
                (
                    "Intent: "
                    f"{row['intent']}"
                ),
                (
                    "Similarity: "
                    f"{row['similarity']:.4f}"
                ),
              ]
          )
      )

    context = "\n\n".join(
      context_parts
    )

    return RetrievedContext(
      context=context,
      retrieved_count=len(results),
      max_similarity=float(results["similarity"].max()),
      min_similarity=float(results['similarity'].min()),
    )