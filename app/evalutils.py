"""평가(채점) 순수 함수. 네트워크·외부 의존 없음 → 단위 테스트 대상."""
from __future__ import annotations


def row_values(row: dict) -> frozenset:
    """행을 값들의 집합으로(컬럼명·자동생성 별칭 차이를 무시)."""
    return frozenset(str(v) for v in row.values())


def answer_matches(agent_rows: list[dict], gold_rows: list[dict]) -> bool:
    """execution accuracy(값 포함) 방식: 각 gold 행의 값들이 서로 다른 agent 행에
    포함되면 일치로 본다. 에이전트가 컬럼을 더 반환하거나 별칭이 달라도 값이 맞으면 정답."""
    agent_sets = [row_values(r) for r in agent_rows]
    used = [False] * len(agent_sets)
    for g in gold_rows:
        gs = row_values(g)
        for i, a in enumerate(agent_sets):
            if not used[i] and gs <= a:
                used[i] = True
                break
        else:
            return False
    return True
