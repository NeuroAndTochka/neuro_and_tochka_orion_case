from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import List, Sequence

from safety_service.config import Settings
from safety_service.core.llm_guard import get_llm_guard
from safety_service.schemas import InputCheckRequest, OutputCheckRequest, SafetyResponse

PII_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"\b\d{16}\b"),  # credit card like numbers
    re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b"),  # SSN-style
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE),
    re.compile(r"\b\+?\d{11,14}\b"),
)

DATA_LEAK_KEYWORDS = {"confidential", "internal use", "top secret", "password", "api key", "token"}
PROMPT_INJECTION_MARKERS = {"ignore previous", "disregard", "override", "system prompt"}

PII_REDACTION_TOKEN = "[REDACTED]"


@dataclass
class EvaluationResult:
    status: str
    reason: str
    message: str
    risk_tags: List[str]
    transformed_query: str | None = None
    transformed_answer: str | None = None


def _default_trace_id(request_trace_id: str | None) -> str:
    return request_trace_id or str(uuid.uuid4())


def _contains_blocked_keyword(text: str, blocklist: Sequence[str]) -> str | None:
    lowered = text.lower()
    for keyword in blocklist:
        if keyword and keyword.lower() in lowered:
            return keyword.lower()
    return None


def _detect_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PROMPT_INJECTION_MARKERS)


def _detect_pii(text: str) -> bool:
    return any(pattern.search(text) for pattern in PII_PATTERNS)


def _redact_pii(text: str) -> str:
    redacted = text
    for pattern in PII_PATTERNS:
        redacted = pattern.sub(PII_REDACTION_TOKEN, redacted)
    return redacted


def _pii_action(mode: str) -> str:
    mapping = {
        "strict": "block",
        "balanced": "transform",
        "relaxed": "allow",
    }
    return mapping.get(mode, "transform")


def _merge_risk_tags(*sources: Sequence[str] | None) -> List[str]:
    merged: List[str] = []
    for source in sources:
        if not source:
            continue
        for tag in source:
            if tag not in merged:
                merged.append(tag)
    return merged


def evaluate_input(request: InputCheckRequest, settings: Settings) -> SafetyResponse:
    trace_id = _default_trace_id(request.meta.trace_id if request.meta else None)
    risk_tags: List[str] = []

    blocked_reason = _contains_blocked_keyword(request.query, settings.blocklist)
    if blocked_reason:
        risk_tags.extend(["security_exploit"])
        return SafetyResponse(
            status="blocked",
            reason="disallowed_content",
            message=f"keyword '{blocked_reason}' is not permitted",
            risk_tags=risk_tags,
            policy_id=settings.default_policy_id,
            trace_id=trace_id,
        )

    if _detect_prompt_injection(request.query):
        risk_tags.append("prompt_injection")
        return SafetyResponse(
            status="blocked",
            reason="prompt_injection",
            message="prompt injection attempt detected",
            risk_tags=risk_tags,
            policy_id=settings.default_policy_id,
            trace_id=trace_id,
        )

    if _detect_pii(request.query):
        risk_tags.append("pii")
        action = _pii_action(settings.policy_mode)
        if action == "block":
            return SafetyResponse(
                status="blocked",
                reason="pii_detected",
                message="query contains sensitive information",
                risk_tags=risk_tags,
                policy_id=settings.default_policy_id,
                trace_id=trace_id,
            )
        if action == "transform" and settings.enable_pii_sanitize:
            return SafetyResponse(
                status="transformed",
                reason="pii_sanitized",
                message="Sensitive data removed from query.",
                risk_tags=risk_tags,
                transformed_query=_redact_pii(request.query),
                policy_id=settings.default_policy_id,
                trace_id=trace_id,
            )

    llm_guard = get_llm_guard(
        enabled=settings.safety_llm_enabled,
        base_url=settings.safety_llm_base_url,
        api_key=settings.safety_llm_api_key,
        model=settings.safety_llm_model,
        timeout=settings.safety_llm_timeout,
        fail_open=settings.safety_llm_fail_open,
    )
    if llm_guard:
        decision = llm_guard.evaluate(request.query, trace_id=trace_id)
        if decision.decision == "block":
            combined_risks = _merge_risk_tags(risk_tags, decision.risk_tags)
            return SafetyResponse(
                status="blocked",
                reason="llm_policy_violation",
                message=decision.reason or "Blocked by safeguard model",
                risk_tags=combined_risks,
                policy_id=settings.default_policy_id,
                trace_id=trace_id,
            )
        if decision.decision == "error" and not llm_guard.fail_open:
            combined_risks = _merge_risk_tags(risk_tags, decision.risk_tags, ["llm_guard_unavailable"])
            return SafetyResponse(
                status="blocked",
                reason="safety_guard_unavailable",
                message=decision.reason or "LLM guard unavailable",
                risk_tags=combined_risks,
                policy_id=settings.default_policy_id,
                trace_id=trace_id,
            )

    return SafetyResponse(
        status="allowed",
        reason="clean",
        message="Request complies with safety policy",
        risk_tags=risk_tags,
        policy_id=settings.default_policy_id,
        trace_id=trace_id,
    )


def evaluate_output(request: OutputCheckRequest, settings: Settings) -> SafetyResponse:
    trace_id = _default_trace_id(request.meta.trace_id if request.meta else None)
    risk_tags: List[str] = []

    blocked_reason = _contains_blocked_keyword(request.answer, settings.blocklist)
    if blocked_reason:
        risk_tags.append("disallowed_content")
        return SafetyResponse(
            status="blocked",
            reason="disallowed_content",
            message=f"Answer contains forbidden topic '{blocked_reason}'",
            risk_tags=risk_tags,
            policy_id=settings.default_policy_id,
            trace_id=trace_id,
        )

    if any(keyword in request.answer.lower() for keyword in DATA_LEAK_KEYWORDS):
        risk_tags.append("data_leak")
        sanitized = None
        if settings.enable_pii_sanitize:
            sanitized = _redact_pii(request.answer)
        return SafetyResponse(
            status="transformed" if sanitized else "blocked",
            reason="data_leak_suspected",
            message="Answer references internal or confidential data",
            risk_tags=risk_tags,
            transformed_answer=sanitized,
            policy_id=settings.default_policy_id,
            trace_id=trace_id,
        )

    if _detect_pii(request.answer):
        risk_tags.append("pii")
        sanitized = _redact_pii(request.answer) if settings.enable_pii_sanitize else None
        return SafetyResponse(
            status="transformed" if sanitized else "blocked",
            reason="pii_sanitized" if sanitized else "pii_detected",
            message="Sensitive data removed from answer" if sanitized else "Answer contains PII",
            risk_tags=risk_tags,
            transformed_answer=sanitized,
            policy_id=settings.default_policy_id,
            trace_id=trace_id,
        )

    return SafetyResponse(
        status="allowed",
        reason="clean",
        message="Answer complies with safety policy",
        risk_tags=risk_tags,
        policy_id=settings.default_policy_id,
        trace_id=trace_id,
    )
