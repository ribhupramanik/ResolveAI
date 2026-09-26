import re
from dataclasses import dataclass

from src.rag.context_builder import (
    RetrievedContext,
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    matched_text: str


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue]

    @property
    def issue_count(self) -> int:
        return len(self.issues)


class ResponseValidator:

    PLACEHOLDER_PATTERN = re.compile(
        r"\{\{[^{}]+\}\}"
    )

    ACTION_PATTERNS = [  # noqa: RUF012

    # I/we can check...
    # I/we will investigate...
    # I'll check...
    re.compile(
        r"\b(?:"
        r"(?:i|we)\s+(?:can\s+|will\s+)?"
        r"|"
        r"(?:i|we)['’]ll\s+"
        r")"
        r"(?:check|review|investigate|process|"
        r"update|change|cancel|contact|"
        r"escalate|verify)\b",
        re.IGNORECASE,
    ),

    # I can help you check...
    # We can help investigate...
    re.compile(
        r"\b(?:i|we)\s+"
        r"(?:can\s+|will\s+)?"
        r"help(?:\s+you)?\s+"
        r"(?:check|review|investigate|process|"
        r"update|change|cancel|contact|"
        r"escalate|verify)\b",
        re.IGNORECASE,
    ),

    # I can look into...
    # I'll look into...
    re.compile(
        r"\b(?:"
        r"(?:i|we)\s+(?:can\s+|will\s+)?"
        r"|"
        r"(?:i|we)['’]ll\s+"
        r")"
        r"look\s+into\b",
        re.IGNORECASE,
    ),

    # I'll be able to look into...
    # We will be able to investigate...
    re.compile(
        r"\b(?:"
        r"(?:i|we)\s+will\s+"
        r"|"
        r"(?:i|we)['’]ll\s+"
        r")"
        r"be\s+able\s+to\s+"
        r"(?:look\s+into|check|review|investigate|"
        r"process|update|change|cancel|contact|"
        r"escalate|verify)\b",
        re.IGNORECASE,
    ),

    # I will follow up...
    # I'll follow up...
    re.compile(
        r"\b(?:"
        r"(?:i|we)\s+(?:will\s+)?"
        r"|"
        r"(?:i|we)['’]ll\s+"
        r")"
        r"follow\s+up\b",
        re.IGNORECASE,
    ),

    # I have checked...
    # I've checked...
    re.compile(
        r"\b(?:"
        r"(?:i|we)\s+(?:have\s+)?"
        r"|"
        r"(?:i|we)['’]ve\s+"
        r")"
        r"(?:checked|reviewed|investigated|"
        r"processed|updated|changed|cancelled|"
        r"canceled|contacted|escalated|verified)\b",
        re.IGNORECASE,
    ),
]
    
    NUMERIC_CLAIM_PATTERN = re.compile(
        r"""
        (?:
            [$€£₹]\s*
            \d+(?:\.\d+)?
        )
        |
        (?:
            \d+(?:\.\d+)?
            (?:\s*[-–—]\s*\d+(?:\.\d+)?)?
            \s*
            (?:
                %
                |
                percent
                |
                minutes?
                |
                hours?
                |
                business\s+days?
                |
                days?
                |
                weeks?
                |
                months?
                |
                years?
                |
                rupees?
                |
                dollars?
                |
                euros?
                |
                pounds?
            )
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    def validate(
        self,
        response_text: str,
        query: str,
        retrieved_context: RetrievedContext,
    ) -> ValidationResult:

        if not isinstance(
            response_text,
            str,
        ):
            raise TypeError(
                "Response text must be a string."
            )

        if not response_text.strip():
            raise ValueError(
                "Response text cannot be empty."
            )

        issues: list[
            ValidationIssue
        ] = []

        self._check_placeholders(
            response_text,
            issues,
        )

        self._check_action_claims(
            response_text,
            issues,
        )

        self._check_numeric_claims(
            response_text,
            query,
            retrieved_context,
            issues,
        )

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
        )

    def _check_placeholders(
        self,
        response_text: str,
        issues: list[ValidationIssue],
    ) -> None:

        for match in (
            self.PLACEHOLDER_PATTERN
            .finditer(
                response_text
            )
        ):

            issues.append(
                ValidationIssue(
                    code="unresolved_placeholder",
                    message=(
                        "Response contains an "
                        "unresolved template "
                        "placeholder."
                    ),
                    matched_text=match.group(
                        0
                    ),
                )
            )

    def _check_action_claims(
        self,
        response_text: str,
        issues: list[ValidationIssue],
    ) -> None:

        seen_matches = set()

        for pattern in (
            self.ACTION_PATTERNS
        ):

            for match in pattern.finditer(
                response_text
            ):

                matched_text = (
                    match.group(0)
                )

                normalized = (
                    matched_text
                    .lower()
                    .strip()
                )

                if normalized in seen_matches:
                    continue

                seen_matches.add(
                    normalized
                )

                issues.append(
                    ValidationIssue(
                        code=(
                            "unsupported_action_claim"
                        ),
                        message=(
                            "Response implies that "
                            "ResolveAI can perform "
                            "an external action."
                        ),
                        matched_text=(
                            matched_text
                        ),
                    )
                )

    def _check_numeric_claims(
        self,
        response_text: str,
        query: str,
        retrieved_context: RetrievedContext,
        issues: list[ValidationIssue],
    ) -> None:

        evidence = " ".join(
            [
                query,
                retrieved_context.context,
            ]
        )

        normalized_evidence = (
            self._normalize_text(
                evidence
            )
        )

        for match in (
            self.NUMERIC_CLAIM_PATTERN
            .finditer(
                response_text
            )
        ):

            claim = match.group(
                0
            )

            normalized_claim = (
                self._normalize_text(
                    claim
                )
            )

            if (
                normalized_claim
                in normalized_evidence
            ):
                continue

            issues.append(
                ValidationIssue(
                    code=(
                        "unsupported_numeric_claim"
                    ),
                    message=(
                        "Response contains a "
                        "numerical claim that is "
                        "not present in the query "
                        "or retrieved evidence."
                    ),
                    matched_text=claim,
                )
            )

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:

        text = text.lower()

        text = (
            text.replace(
                "–",
                "-",
            )
            .replace(
                "—",
                "-",
            )
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()