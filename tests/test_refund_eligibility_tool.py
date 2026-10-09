import src.tools.refund_eligibility_tool as module


def test_database_session_failure_returns_safe_error(
    monkeypatch,
):
    def failing_session():
        raise RuntimeError("Internal database connection details")

    monkeypatch.setattr(
        module,
        "SessionLocal",
        failing_session,
    )

    tool = module.RefundEligibilityTool()

    result = tool.execute("ORD-10002")

    assert result.tool_name == ("check_refund_eligibility")

    assert result.success is False

    assert result.data == {
        "order_number": "ORD-10002",
    }

    assert result.error == ("Refund eligibility check failed.")

    assert "Internal database connection details" not in str(result)
