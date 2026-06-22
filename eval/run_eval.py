"""에이전트 평가 하네스.

측정 지표:
  - validity rate: 생성 SQL이 dry-run 검증을 통과한 비율
  - answer match: gold_sql 결과와 에이전트 결과가 일치한 비율(gold 보유 항목 한정)

실행: python -m eval.run_eval
"""
from __future__ import annotations

import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agent import Nl2SqlAgent  # noqa: E402
from app.bq import BigQueryBackend  # noqa: E402


def _row_values(row: dict) -> frozenset:
    """행을 값들의 집합으로(컬럼명·자동생성 별칭 차이를 무시)."""
    return frozenset(str(v) for v in row.values())


def _answer_matches(agent_rows: list[dict], gold_rows: list[dict]) -> bool:
    """execution accuracy(값 포함) 방식:
    각 gold 행의 값들이 서로 다른 agent 행에 포함되면 일치로 본다.
    에이전트가 컬럼을 더 반환하거나 별칭이 달라도 값이 맞으면 정답 처리."""
    agent_sets = [_row_values(r) for r in agent_rows]
    used = [False] * len(agent_sets)
    for g in gold_rows:
        gs = _row_values(g)
        for i, a in enumerate(agent_sets):
            if not used[i] and gs <= a:
                used[i] = True
                break
        else:
            return False
    return True


def main() -> int:
    qpath = os.path.join(os.path.dirname(__file__), "questions.yaml")
    questions = yaml.safe_load(open(qpath, encoding="utf-8"))

    agent = Nl2SqlAgent()
    print("스키마 그라운딩 인덱스 구축 중…")
    agent.setup()
    bq = BigQueryBackend()

    n = len(questions)
    valid = 0
    gold_total = 0
    gold_match = 0

    for i, item in enumerate(questions, 1):
        q = item["question"]
        res = agent.answer(q, summarize=False)
        status = "OK " if res.ok else "FAIL"
        print(f"[{i}/{n}] {status} {q}")
        if res.warnings:
            print("       ⚠ " + " / ".join(res.warnings))
        if not res.ok:
            print(f"       error: {res.error}")
            continue
        valid += 1

        gold = item.get("gold_sql")
        if gold:
            gold_total += 1
            try:
                gold_rows = bq.run(gold.strip())
                if _answer_matches(res.rows, gold_rows.rows):
                    gold_match += 1
                    print("       ✓ gold 일치")
                else:
                    print("       ✗ gold 불일치")
                    print(f"         agent: {res.rows[:3]}")
                    print(f"         gold : {gold_rows.rows[:3]}")
            except Exception as e:
                print(f"       gold 실행 오류: {e}")

    print("\n===== 결과 =====")
    print(f"Validity rate : {valid}/{n} = {valid/n:.0%}")
    if gold_total:
        print(f"Answer match  : {gold_match}/{gold_total} = {gold_match/gold_total:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
