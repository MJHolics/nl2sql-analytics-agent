"""대화 세션 상태 — 멀티턴 후속질의 지원.

에이전트(`Nl2SqlAgent`)는 무상태로 두고, 대화 이력은 이 모듈이 보관한다.
후속 질문("그중 상위 3개만", "카테고리별로 다시")을 직전 SQL·답에 기대어
해석할 수 있도록 최근 턴을 프롬프트 컨텍스트로 렌더링한다.

설계 메모(컨텍스트 오염 방지):
  - 성공(ok)하고 SQL을 만든 턴만 이력에 넣는다(실패 턴은 후속 해석에 해롭다).
  - 최근 `max_turns`개로 윈도우를 제한해 무관한 과거가 끌려오는 것을 줄인다.
  - "무관한 새 질문이면 직전 대화를 무시하라"는 판단은 LLM에 맡기되(프롬프트로 지시),
    이력 자체는 결정적으로 렌더링해 오프라인 단위테스트가 가능하게 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Turn:
    question: str
    sql: str = ""
    answer: str = ""
    ok: bool = False


def render_history(turns: list[Turn], max_turns: int = 3) -> str:
    """최근 성공 턴을 후속질의 해석용 컨텍스트로 렌더링. 이력이 없으면 빈 문자열."""
    recent = [t for t in turns if t.ok and t.sql][-max_turns:]
    if not recent:
        return ""
    blocks = []
    for i, t in enumerate(recent, 1):
        block = f"### 직전 질문 {i}\nQ: {t.question}\nSQL:\n{t.sql}"
        if t.answer:
            block += f"\n답: {t.answer}"
        blocks.append(block)
    return "\n\n".join(blocks)


@dataclass
class Conversation:
    """턴을 누적하고 직전 이력을 렌더링하는 얇은 세션 컨테이너."""

    turns: list[Turn] = field(default_factory=list)
    max_turns: int = 3

    def history(self) -> str:
        return render_history(self.turns, self.max_turns)

    def record(self, turn: Turn) -> None:
        self.turns.append(turn)
