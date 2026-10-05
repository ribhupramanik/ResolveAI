import re
from dataclasses import dataclass
from decimal import (
    Decimal,
    InvalidOperation,
)

from src.rag.knowledge_retriever import (
    VerifiedKnowledgeContext,
)
from src.rag.operational_context import (
    OperationalContext,
)
from src.rag.system_capabilities import (
    SystemCapabilitiesContext,
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
    PLACEHOLDER_PATTERN = re.compile(r"\{\{[^{}]+\}\}")

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
            r"canceled|contacted|escalated|verified|"
            r"forwarded|sent|submitted|routed|"
            r"assigned|transferred)\b",
            re.IGNORECASE,
        ),
        # I've forwarded your request...
        # We have sent this to the team...
        # I've transferred your case...
        re.compile(
            r"\b(?:"
            r"(?:i|we)\s+have\s+"
            r"|"
            r"(?:i|we)['’]ve\s+"
            r")"
            r"(?:forwarded|sent|submitted|routed|"
            r"assigned|transferred)\b",
            re.IGNORECASE,
        ),
        # I can look up...
        # We'll look up...
        # I'll look up...
        re.compile(
            r"\b(?:"
            r"(?:i|we)\s+(?:can\s+|will\s+)?"
            r"|"
            r"(?:i|we)['’]ll\s+"
            r")"
            r"look\s+up\b",
            re.IGNORECASE,
        ),
        # I can connect you...
        # We'll transfer you...
        # I'll route you...
        re.compile(
            r"\b(?:"
            r"(?:i|we)\s+(?:can\s+|will\s+)?"
            r"|"
            r"(?:i|we)['’]ll\s+"
            r")"
            r"(?:connect|transfer|route)\s+you\b",
            re.IGNORECASE,
        ),
        # I can provide you with the latest status...
        # I can give you an accurate delivery estimate...
        re.compile(
            r"\b(?:"
            r"(?:i|we)\s+(?:can\s+|will\s+)?"
            r"|"
            r"(?:i|we)['’]ll\s+"
            r")"
            r"(?:provide|give)\s+"
            r"(?:you\s+)?"
            r"(?:with\s+)?"
            r"(?:the\s+|an?\s+)?"
            r"(?:"
            r"latest\s+|"
            r"updated\s+|"
            r"current\s+|"
            r"accurate\s+|"
            r"up[- ]to[- ]date\s+|"
            r"most\s+up[- ]to[- ]date\s+"
            r")?"
            r"(?:(?:delivery|tracking|refund|order|shipment)\s+)?"
            r"(?:status|estimate)\b",
            re.IGNORECASE,
        ),
        # I'll forward your request...
        # I can forward that information...
        # We will send those details...
        # We'll route this...
        re.compile(
            r"\b(?:"
            r"(?:i|we)\s+(?:can\s+|will\s+)?"
            r"|"
            r"(?:i|we)['’]ll\s+"
            r")"
            r"(?:forward|send|route|transfer|assign|submit)\s+"
            r"(?:"
            r"your\s+(?:request|case|issue|details|information)"
            r"|"
            r"(?:this|that)\s*(?:request|case|issue|information|details)?"
            r"|"
            r"(?:those|the)\s+(?:details|information|request|case|issue)"
            r")\b",
            re.IGNORECASE,
        ),
        # I can help you get connected to...
        # I can help you connect with...
        re.compile(
            r"\b(?:i|we)\s+"
            r"(?:can\s+|will\s+)?"
            r"help(?:\s+you)?\s+"
            r"(?:get\s+connected|connect)\s+"
            r"(?:to|with)\b",
            re.IGNORECASE,
        ),
        # I can help you locate the refund status...
        # I can help you locate your order...
        re.compile(
            r"\b(?:i|we)\s+"
            r"(?:can\s+|will\s+)?"
            r"help(?:\s+you)?\s+"
            r"locate\b",
            re.IGNORECASE,
        ),
        # I can pass along those details...
        # I'll pass along that information...
        # We can pass this along...
        re.compile(
            r"\b(?:"
            r"(?:i|we)\s+(?:can\s+|will\s+)?"
            r"|"
            r"(?:i|we)['’]ll\s+"
            r")"
            r"pass\s+"
            r"(?:"
            r"along\s+"
            r"(?:"
            r"those\s+details"
            r"|that\s+information"
            r"|the\s+(?:details|information)"
            r"|your\s+(?:details|information|request|case|issue)"
            r")"
            r"|"
            r"(?:this|that|it)\s+along"
            r")\b",
            re.IGNORECASE,
        ),
        # If you'd like me to pass along...
        # If you would like me to forward...
        re.compile(
            r"\b(?:"
            r"you['’]d\s+like\s+me\s+to"
            r"|"
            r"you\s+would\s+like\s+me\s+to"
            r")\s+"
            r"(?:"
            r"pass\s+along"
            r"|forward"
            r"|send"
            r"|route"
            r"|transfer"
            r")\b",
            re.IGNORECASE,
        ),
    ]

    SUPPORT_ROUTE_PATTERNS = [  # noqa: RUF012
        # Recommend contacting an unverified support
        # person, team, company, or channel.
        re.compile(
            r"\b(?:"
            r"contact"
            r"|contacting"
            r"|try\s+contacting"
            r"|call"
            r"|email"
            r"|reach\s+out(?:\s+directly)?\s+to"
            r"|speak\s+(?:to|with)"
            r")\s+"
            r"(?:the\s+|their\s+|our\s+|a\s+)?"
            r"(?:company['’]s\s+)?"
            r"(?:"
            r"customer[-‐-‒–— ]support"
            r"|customer[-‐-‒–— ]service"
            r"|support\s+team"
            r"|support\s+department"
            r"|support\s+representative"
            r"|support\s+agent"
            r"|company"
            r")\b",
            re.IGNORECASE,
        ),
        # Recommend checking/visiting/using an
        # unverified website, portal, resource, channel,
        # help center, or communication.
        re.compile(
            r"\b(?:"
            r"check"
            r"|visit"
            r"|use"
            r"|open"
            r"|find"
            r"|look\s+for"
            r"|try"
            r")\s+"
            r"(?:any\s+|the\s+|their\s+|our\s+|a\s+)?"
            r"(?:available\s+)?"
            r"(?:company['’]s\s+)?"
            r"(?:official\s+)?"
            r"(?:"
            r"website"
            r"|resources?"
            r"|channels?"
            r"|help\s+(?:center|resources?|page|portal)"
            r"|support\s+(?:resources?|page|portal|website|channels?)"
            r"|customer[-‐-‒–— ]support\s+resources?"
            r"|customer[-‐-‒–— ]service\s+resources?"
            r"|account\s+portal"
            r"|official\s+communication"
            r"|communications?"
            r")\b",
            re.IGNORECASE,
        ),
        # Recommend using a supposed phone number.
        re.compile(
            r"\b(?:"
            r"call"
            r"|contact"
            r"|use"
            r"|through"
            r"|via"
            r")\s+"
            r"(?:the\s+|their\s+|our\s+|a\s+)?"
            r"(?:"
            r"customer[-‐-‒–— ]support\s+"
            r"|customer[-‐-‒–— ]service\s+"
            r"|support\s+"
            r")?"
            r"phone\s+number\b",
            re.IGNORECASE,
        ),
        # Contact a company through/via an alleged
        # website, channel, portal, or help resource.
        re.compile(
            r"\b(?:"
            r"contact"
            r"|contacting"
            r"|try\s+contacting"
            r"|reach\s+out(?:\s+directly)?\s+to"
            r")\s+"
            r"(?:the\s+|a\s+)?"
            r"company\s+"
            r"(?:through|via)\s+"
            r"(?:their\s+|the\s+)?"
            r"(?:official\s+)?"
            r"(?:"
            r"website"
            r"|channels?"
            r"|help\s+(?:center|resources?|portal)"
            r"|support\s+(?:page|portal|website)"
            r")\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:contact|reach\s+out\s+to)\s+"
            r"(?:the\s+)?"
            r"(?:relevant|appropriate)\s+"
            r"support\s+"
            r"(?:channel|team|department)\b",
            re.IGNORECASE,
        ),
    ]

    THIRD_PARTY_PATTERNS = [  # noqa: RUF012
        # contact merchant/bank/payment provider/courier
        re.compile(
            r"\b(?:contact|call|email)\s+"
            r"(?:the\s+|your\s+|a\s+)?"
            r"(?:"
            r"merchant"
            r"|bank"
            r"|payment\s+provider"
            r"|courier"
            r"|carrier"
            r")\b",
            re.IGNORECASE,
        ),
        # reach out directly to the merchant/bank/etc.
        re.compile(
            r"\breach\s+out"
            r"(?:\s+directly)?"
            r"\s+to\s+"
            r"(?:the\s+|your\s+|a\s+)?"
            r"(?:"
            r"merchant"
            r"|bank"
            r"|payment\s+provider"
            r"|courier"
            r"|carrier"
            r")\b",
            re.IGNORECASE,
        ),
        # check with your bank / merchant
        re.compile(
            r"\bcheck\s+with\s+"
            r"(?:the\s+|your\s+|a\s+)?"
            r"(?:"
            r"merchant"
            r"|bank"
            r"|payment\s+provider"
            r"|courier"
            r"|carrier"
            r")\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:"
            r"contact"
            r"|call"
            r"|email"
            r"|check\s+with"
            r"|reach\s+out(?:\s+directly)?\s+to"
            r")\s+"
            r"(?:the\s+|your\s+|a\s+)?"
            r"(?:"
            r"merchant"
            r"|bank"
            r"|payment\s+provider"
            r"|courier"
            r"|carrier"
            r"|party\s+that\s+(?:processed|handled)"
            r"(?:\s+the)?\s+"
            r"(?:refund|payment|transaction|order)"
            r")\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:use|enter|paste|check|track)\s+"
            r"(?:the\s+|your\s+)?"
            r"tracking\s+(?:number|code)\s+"
            r"(?:on|in|with|through|via)\s+"
            r"(?:"
            r"[A-Za-z0-9][A-Za-z0-9 .&-]*['’]s\s+"
            r")?"
            r"(?:website|app|portal|tracking\s+page)\b",
            re.IGNORECASE,
        ),
    ]

    LOOKED_UP_PATTERN = re.compile(
        r"\b(?:"
        r"(?:i|we)\s+have\s+"
        r"|"
        r"(?:i|we)['’]ve\s+"
        r")"
        r"looked\s+up\b",
        re.IGNORECASE,
    )

    CANCELLATION_PROCEDURE_PATTERNS = [  # noqa: RUF012
        re.compile(
            r"\b(?:use|open|visit|go\s+to)\s+"
            r"(?:the\s+|your\s+|our\s+)?"
            r"(?:"
            r"order[- ]management\s+(?:features?|page|portal)"
            r"|account\s+(?:portal|page)"
            r"|cancellation\s+(?:option|page|portal)"
            r")\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:log|sign)\s+in(?:to)?\s+"
            r"(?:your\s+|the\s+)?account\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bselect(?:ing)?\s+"
            r"(?:the\s+)?cancellation\s+option\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bconfirm\s+(?:the\s+)?"
            r"(?:cancellation\s+)?request\s+"
            r"(?:through|via|using)\s+"
            r"(?:the\s+)?channel\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\border\s+confirmation\s+email\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:use|follow|go\s+through)\s+"
            r"(?:the\s+)?"
            r"cancellation\s+"
            r"(?:process|procedure|workflow)\s+"
            r"(?:available\s+)?"
            r"(?:through|via|in|on)\s+"
            r"(?:your\s+|the\s+)?"
            r"account\b",
            re.IGNORECASE,
        ),
    ]

    CURRENCY_SYMBOL_TO_CODE = {  # noqa: RUF012
        "₹": "inr",
        "$": "usd",
        "€": "eur",
        "£": "gbp",
    }

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
        verified_knowledge: VerifiedKnowledgeContext,
        system_capabilities: SystemCapabilitiesContext,
        operational_context: OperationalContext | None = None,
    ) -> ValidationResult:

        if not isinstance(
            response_text,
            str,
        ):
            raise TypeError("Response text must be a string.")

        if not response_text.strip():
            raise ValueError("Response text cannot be empty.")

        issues: list[ValidationIssue] = []

        self._check_placeholders(
            response_text,
            issues,
        )

        self._check_action_claims(
            response_text,
            issues,
            operational_context=operational_context,
        )

        self._check_support_route_claims(
            response_text,
            issues,
        )

        self._check_third_party_claims(
            response_text,
            issues,
        )

        self._check_numeric_claims(
            response_text,
            query,
            verified_knowledge,
            system_capabilities,
            issues,
            operational_context=operational_context,
        )

        self._check_cancellation_procedure_claims(
            response_text,
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

        for match in self.PLACEHOLDER_PATTERN.finditer(response_text):
            issues.append(
                ValidationIssue(
                    code="unresolved_placeholder",
                    message=("Response contains an unresolved template placeholder."),
                    matched_text=match.group(0),
                )
            )

    def _check_action_claims(
        self,
        response_text: str,
        issues: list[ValidationIssue],
        operational_context: OperationalContext | None = None,
    ) -> None:

        seen_matches = set()

        for match in self.LOOKED_UP_PATTERN.finditer(response_text):
            lookup_was_successful = (
                operational_context is not None
                and operational_context.tool_used
                and operational_context.tool_name == "get_order"
                and operational_context.tool_success
            )

            if lookup_was_successful:
                continue

            issues.append(
                ValidationIssue(
                    code="unsupported_action_claim",
                    message=(
                        "Response claims that ResolveAI "
                        "looked up operational data, but "
                        "no successful order lookup "
                        "supports that claim."
                    ),
                    matched_text=match.group(0),
                )
            )

        for pattern in self.ACTION_PATTERNS:
            for match in pattern.finditer(response_text):
                matched_text = match.group(0)

                normalized = matched_text.lower().strip()

                read_only_check_is_supported = (
                    "checked" in normalized
                    and operational_context is not None
                    and operational_context.tool_used
                    and operational_context.tool_success
                    and operational_context.tool_name
                    in {
                        "get_order",
                        "check_cancellation_eligibility",
                        "get_refund_status",
                    }
                )

                if read_only_check_is_supported:
                    continue

                if normalized in seen_matches:
                    continue

                seen_matches.add(normalized)

                issues.append(
                    ValidationIssue(
                        code=("unsupported_action_claim"),
                        message=(
                            "Response implies that "
                            "ResolveAI can perform "
                            "an external action."
                        ),
                        matched_text=(matched_text),
                    )
                )

    def _check_support_route_claims(
        self,
        response_text: str,
        issues: list[ValidationIssue],
    ) -> None:

        seen_matches = set()

        for pattern in self.SUPPORT_ROUTE_PATTERNS:
            for match in pattern.finditer(response_text):
                matched_text = match.group(0)

                normalized = matched_text.lower().strip()

                if normalized in seen_matches:
                    continue

                seen_matches.add(normalized)

                issues.append(
                    ValidationIssue(
                        code=("unsupported_support_route_claim"),
                        message=(
                            "Response recommends or "
                            "implies a support route "
                            "that is not verified."
                        ),
                        matched_text=matched_text,
                    )
                )

    def _check_third_party_claims(
        self,
        response_text: str,
        issues: list[ValidationIssue],
    ) -> None:

        seen_matches = set()

        for pattern in self.THIRD_PARTY_PATTERNS:
            for match in pattern.finditer(response_text):
                matched_text = match.group(0)

                normalized = matched_text.lower().strip()

                if normalized in seen_matches:
                    continue

                seen_matches.add(normalized)

                issues.append(
                    ValidationIssue(
                        code=("unsupported_third_party_claim"),
                        message=(
                            "Response recommends an "
                            "unverified third-party "
                            "procedure or contact route."
                        ),
                        matched_text=matched_text,
                    )
                )

    def _check_numeric_claims(
        self,
        response_text: str,
        query: str,
        verified_knowledge: VerifiedKnowledgeContext,
        system_capabilities: SystemCapabilitiesContext,
        issues: list[ValidationIssue],
        operational_context: OperationalContext | None = None,
    ) -> None:

        evidence_parts = [
            query,
            verified_knowledge.context,
            system_capabilities.context,
        ]

        if operational_context is not None and operational_context.tool_success:
            evidence_parts.append(operational_context.context)

        evidence = " ".join(evidence_parts)

        normalized_evidence = self._normalize_text(evidence)

        for match in self.NUMERIC_CLAIM_PATTERN.finditer(response_text):
            claim = match.group(0)

            normalized_claim = self._normalize_text(claim)

            if normalized_claim in normalized_evidence:
                continue

            if self._currency_claim_is_supported(
                claim,
                normalized_evidence,
            ):
                continue

            issues.append(
                ValidationIssue(
                    code="unsupported_numeric_claim",
                    message=(
                        "Response contains a "
                        "numerical claim that is "
                        "not present in the customer "
                        "request or authoritative evidence."
                    ),
                    matched_text=claim,
                )
            )

    @classmethod
    def _currency_claim_is_supported(
        cls,
        claim: str,
        normalized_evidence: str,
    ) -> bool:

        currency_symbol = next(
            (symbol for symbol in cls.CURRENCY_SYMBOL_TO_CODE if symbol in claim),
            None,
        )

        if currency_symbol is None:
            return False

        currency_code = cls.CURRENCY_SYMBOL_TO_CODE[currency_symbol]

        amount_match = re.search(
            r"\d+(?:\.\d+)?",
            claim,
        )

        if amount_match is None:
            return False

        try:
            claim_amount = Decimal(amount_match.group(0))
        except InvalidOperation:
            return False

        evidence_amount_matches = re.findall(
            r"\d+(?:\.\d+)?",
            normalized_evidence,
        )

        evidence_amounts = []

        for value in evidence_amount_matches:
            try:
                evidence_amounts.append(Decimal(value))
            except InvalidOperation:
                continue

        amount_is_supported = claim_amount in evidence_amounts

        currency_is_supported = bool(
            re.search(
                rf"\b{re.escape(currency_code)}\b",
                normalized_evidence,
            )
        )

        return amount_is_supported and currency_is_supported

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:

        text = text.lower()

        text = text.replace(
            "–",
            "-",
        ).replace(
            "—",
            "-",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    def _check_cancellation_procedure_claims(
        self,
        response_text: str,
        issues: list[ValidationIssue],
    ) -> None:

        seen_matches = set()

        for pattern in self.CANCELLATION_PROCEDURE_PATTERNS:
            for match in pattern.finditer(response_text):
                matched_text = match.group(0)

                normalized = matched_text.lower().strip()

                if normalized in seen_matches:
                    continue

                seen_matches.add(normalized)

                issues.append(
                    ValidationIssue(
                        code=("unsupported_cancellation_procedure_claim"),
                        message=(
                            "Response recommends or "
                            "describes a cancellation "
                            "procedure that is not "
                            "supported by authoritative "
                            "evidence."
                        ),
                        matched_text=matched_text,
                    )
                )
