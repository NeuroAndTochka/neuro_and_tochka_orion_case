from safety_service.config import Settings
from safety_service.core.evaluator import evaluate_input, evaluate_output
from safety_service.schemas import InputCheckRequest, OutputCheckRequest, SafetyUser


def build_settings(**kw) -> Settings:
    return Settings(**kw)


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
