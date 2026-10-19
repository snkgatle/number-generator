"""Unit tests for Budget Circuit Breaker logic (Directive 3)."""
import pytest
from app.services.budget_service import BudgetService, BudgetExhaustedException


@pytest.mark.asyncio
async def test_circuit_breaker_deduction_and_exhaustion(db_session):
    """Directive 3: Verify budget circuit breaker locks out generation upon exhaustion."""
    budget_service = BudgetService()

    # 1. Initialize budget
    budget = await budget_service.get_or_create_monthly_budget(db_session)
    assert budget.remaining_boards == 40
    assert budget.used_boards == 0

    # 2. Consume 39 boards
    budget = await budget_service.record_board_usage(db_session, boards_used=39)
    assert budget.remaining_boards == 1
    assert budget.used_boards == 39
    assert budget.is_exhausted is False

    # 3. Consume the final board
    budget = await budget_service.record_board_usage(db_session, boards_used=1)
    assert budget.remaining_boards == 0
    assert budget.used_boards == 40
    assert budget.is_exhausted is True

    # 4. Attempting to consume or verify further boards must raise BudgetExhaustedException
    with pytest.raises(BudgetExhaustedException) as exc:
        await budget_service.verify_circuit_breaker(db_session, boards_requested=1)
    assert "Budget Exhausted" in str(exc.value)

    # 5. Calling record_board_usage also fails
    with pytest.raises(BudgetExhaustedException):
        await budget_service.record_board_usage(db_session, boards_used=1)
