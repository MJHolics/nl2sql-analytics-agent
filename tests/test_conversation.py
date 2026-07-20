"""대화 이력 렌더링(순수 로직) 단위테스트 — 네트워크·LLM 불필요."""
from __future__ import annotations

from app.conversation import Conversation, Turn, render_history


def test_empty_history_is_blank():
    assert render_history([]) == ""


def test_failed_turns_are_excluded():
    turns = [
        Turn(question="실패한 질문", sql="", answer="", ok=False),
        Turn(question="빈 SQL", sql="", answer="x", ok=True),
    ]
    # ok=False 와 sql 없는 턴은 후속 해석에 해로우므로 제외 → 결과 비어야 함
    assert render_history(turns) == ""


def test_successful_turn_renders_question_and_sql():
    turns = [Turn(question="카테고리별 매출 top 5", sql="SELECT 1", answer="A는 100", ok=True)]
    out = render_history(turns)
    assert "카테고리별 매출 top 5" in out
    assert "SELECT 1" in out
    assert "A는 100" in out


def test_window_limits_to_max_turns():
    turns = [Turn(question=f"q{i}", sql=f"SELECT {i}", ok=True) for i in range(5)]
    out = render_history(turns, max_turns=2)
    # 최근 2개(q3, q4)만 포함, 오래된 것(q0~q2)은 제외
    assert "q4" in out and "q3" in out
    assert "q0" not in out and "q2" not in out


def test_order_is_oldest_to_newest():
    turns = [Turn(question="첫째", sql="SELECT 1", ok=True),
             Turn(question="둘째", sql="SELECT 2", ok=True)]
    out = render_history(turns)
    assert out.index("첫째") < out.index("둘째")


def test_conversation_records_and_renders():
    conv = Conversation()
    assert conv.history() == ""
    conv.record(Turn(question="q1", sql="SELECT 1", ok=True))
    assert "q1" in conv.history()
