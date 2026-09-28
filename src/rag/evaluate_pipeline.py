from pathlib import Path

import pandas as pd

from src.rag.pipeline import (
    ResolveAIPipeline,
)
from src.rag.providers.groq_provider import (
    GroqGenerator,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EVAL_PATH = PROJECT_ROOT / "data" / "rag_eval" / "rag_eval.csv"

OUTPUT_PATH = PROJECT_ROOT / "artifacts" / "rag" / "rag_eval_results.csv"


def main():

    eval_df = pd.read_csv(EVAL_PATH)

    pipeline = ResolveAIPipeline(generator=GroqGenerator())

    results = []

    for index, row in eval_df.iterrows():
        query = str(row["query"])

        expected_intent = str(row["expected_intent"])

        print(f"[{index + 1}/{len(eval_df)}] {query}")

        result = pipeline.run(query)

        results.append(
            {
                "query": query,
                "expected_intent": expected_intent,
                "response": result.text,
                "retrieved_count": (result.retrieved_count),
                "verified_knowledge_count": (result.verified_knowledge_count),
                "verified_knowledge_topics": (
                    " | ".join(result.verified_knowledge_topics)
                ),
                "system_capability_count": (result.system_capability_count),
                "system_capabilities": (" | ".join(result.system_capabilities)),
                "attempts": result.attempts,
                "used_fallback": result.used_fallback,
                "validation_issue_count": (len(result.validation_issues)),
                "validation_issues": (
                    " | ".join(issue.code for issue in result.validation_issues)
                ),
                "validation_issue_details": (
                    " | ".join(
                        (f"{issue.code}: {issue.matched_text}")
                        for issue in result.validation_issues
                    )
                ),
                "provider": result.provider,
                "model": result.model,
            }
        )

    result_df = pd.DataFrame(results)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("\nEvaluation complete.")

    print("Queries:", len(result_df))

    print("Responses requiring retry:", (result_df["attempts"] == 2).sum())

    first_attempt_success = (result_df["attempts"] == 1).sum()

    retry_success = ((result_df["attempts"] == 2) & (~result_df["used_fallback"])).sum()

    fallback_count = result_df["used_fallback"].sum()

    print(
        "First-attempt successes:",
        first_attempt_success,
    )

    print(
        "Retry successes:",
        retry_success,
    )

    print(
        "Fallbacks:",
        fallback_count,
    )

    issue_counts = {}

    for issues in result_df[
        "validation_issues"
    ]:
        if not isinstance(
            issues,
            str,
        ):
            continue

        if not issues.strip():
            continue

        for issue in issues.split(" | "):
            issue_counts[issue] = (
                issue_counts.get(
                    issue,
                    0,
                )
                + 1
            )

    print(
        "\nValidation issue distribution:"
    )

    if issue_counts:
        for issue, count in sorted(
            issue_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            print(
                f"- {issue}: {count}"
            )
    else:
        print("- None")

    print("\nSaved to:")

    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
