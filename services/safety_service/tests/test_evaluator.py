from safety_service.config import Settings
from safety_service.core.evaluator import evaluate_input, evaluate_output
from safety_service.core.llm_guard import (
    LLMGuardDecision,
    reset_guard_cache,
    reset_guard_override,
    set_guard_override,
)
from safety_service.schemas import InputCheckRequest, OutputCheckRequest, SafetyUser


def build_settings(**kw) -> Settings:
    return Settings(**kw)


class StubGuard:
    def __init__(self, decision: LLMGuardDecision, *, fail_open: bool = True) -> None:
        self._decision = decision
        self.fail_open = fail_open
        self.queries: list[str] = []

    def evaluate(self, text: str, trace_id: str | None = None) -> LLMGuardDecision:
        self.queries.append(text)
        return self._decision


def _cleanup_guard() -> None:
    reset_guard_override()
    reset_guard_cache()


def test_input_blocked_by_blocklist() -> None:
    settings = build_settings()
    request = InputCheckRequest(
        user=SafetyUser(user_id="u", tenant_id="t"),
        query="How to hack the system?",
    )
    response = evaluate_input(request, settings)
    assert response.status == "blocked"
    assert response.reason == "disallowed_content"
    assert "security_exploit" in response.risk_tags


def test_input_pii_transformed_in_balanced_mode() -> None:
    settings = build_settings(policy_mode="balanced")
    request = InputCheckRequest(
        user=SafetyUser(user_id="u", tenant_id="t"),
        query="My phone is +123456789012 please help",
    )
    response = evaluate_input(request, settings)
    assert response.status == "transformed"
    assert response.transformed_query is not None
    assert "[REDACTED]" in response.transformed_query


def test_output_data_leak_blocks_when_no_sanitize() -> None:
    settings = build_settings(enable_pii_sanitize=False)
    response = evaluate_output(
        OutputCheckRequest(
            user=SafetyUser(user_id="u", tenant_id="t"),
            query="",
            answer="Here is the internal use only password 1234",
        ),
        settings,
    )
    assert response.status == "blocked"
    assert response.reason in {"data_leak_suspected", "disallowed_content"}


def test_input_blocked_by_llm_guard_override() -> None:
    guard = StubGuard(
        LLMGuardDecision(decision="block", reason="illegal content", risk_tags=["illegal"]),
        fail_open=True,
    )
    set_guard_override(guard)
    try:
        settings = build_settings(safety_llm_enabled=True, safety_llm_api_key="dummy")
        request = InputCheckRequest(
            user=SafetyUser(user_id="u", tenant_id="t"),
            query="Tell me how to commit a crime",
        )
        response = evaluate_input(request, settings)
        assert response.status == "blocked"
        assert response.reason == "llm_policy_violation"
        assert "illegal" in response.risk_tags
        assert guard.queries == ["Tell me how to commit a crime"]
    finally:
        _cleanup_guard()


def test_input_llm_guard_error_fail_closed() -> None:
    guard = StubGuard(LLMGuardDecision(decision="error", reason="timeout"), fail_open=False)
    set_guard_override(guard)
    try:
        settings = build_settings(
            safety_llm_enabled=True,
            safety_llm_api_key="dummy",
            safety_llm_fail_open=False,
        )
        request = InputCheckRequest(
            user=SafetyUser(user_id="u", tenant_id="t"),
            query="legit question",
        )
        response = evaluate_input(request, settings)
        assert response.status == "blocked"
        assert response.reason == "safety_guard_unavailable"
        assert "llm_guard_unavailable" in response.risk_tags
    finally:
        _cleanup_guard()
