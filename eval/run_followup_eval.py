"""멀티턴 후속질의 평가 하네스.

각 대화의 setup 턴을 진행해 이력을 쌓고, gold_sql 이 달린 후속질의를
**이력 있음(메모리) vs 이력 없음(단일턴 베이스라인)** 두 조건으로 같은 gold 에 채점한다.
후속질의("그중 상위 3개만", "Men 부서는?")는 단독으로는 의미가 불완전하므로,
메모리가 없으면 베이스라인이 실패/오해석하고 메모리가 있으면 풀린다 — 그 격차가 멀티턴의 값어치다.

실행: python -m eval.run_followup_eval   (LLM 키 + BigQuery 샌드박스 필요, 비용 0)
"""
from __future__ import annotations

import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agent import Nl2SqlAgent  # noqa: E402
from app.bq import BigQueryBackend  # noqa: E402
from app.conversation import Conversation, Turn  # noqa: E402
from app.evalutils import answer_matches  # noqa: E402


def main() -> int:
    qpath = os.path.join(os.path.dirname(__file__), "followup_questions.yaml")
    convs = yaml.safe_load(open(qpath, encoding="utf-8"))

    agent = Nl2SqlAgent()
    print("스키마 그라운딩 인덱스 구축 중…")
    agent.setup()
    bq = BigQueryBackend()

    graded = 0
    with_mem_ok = 0
    no_mem_ok = 0

    for ci, conv in enumerate(convs, 1):
        print(f"\n[대화 {ci}] {conv.get('name', '')}")
        session = Conversation()
        for turn in conv["turns"]:
            q = turn["question"]
            gold = turn.get("gold_sql")

            if not gold:
                # setup 턴: 이력만 쌓는다
                res = agent.answer(q, summarize=False, history=session.history())
                session.record(Turn(question=q, sql=res.sql, answer=res.answer, ok=res.ok))
                print(f"   · (맥락) {q}")
                continue

            # 채점 후속질의: 이력 있음 vs 없음을 같은 gold 로 비교
            graded += 1
            gold_rows = bq.run(gold.strip()).rows

            res_mem = agent.answer(q, summarize=False, history=session.history())
            mem_ok = res_mem.ok and answer_matches(res_mem.rows, gold_rows)
            with_mem_ok += mem_ok

            res_base = agent.answer(q, summarize=False, history="")
            base_ok = res_base.ok and answer_matches(res_base.rows, gold_rows)
            no_mem_ok += base_ok

            print(f"   ▶ 후속질의: {q}")
            print(f"     메모리 있음: {'✓ 정답' if mem_ok else '✗ 오답/실패'}")
            print(f"     메모리 없음: {'✓ 정답' if base_ok else '✗ 오답/실패'}  (베이스라인)")

            # 이어지는 턴을 위해 메모리 조건 결과를 이력에 기록
            session.record(Turn(question=q, sql=res_mem.sql, answer=res_mem.answer, ok=res_mem.ok))

    print("\n===== 결과 (후속질의 해석 정확도) =====")
    if graded:
        print(f"메모리 있음 : {with_mem_ok}/{graded} = {with_mem_ok/graded:.0%}")
        print(f"메모리 없음 : {no_mem_ok}/{graded} = {no_mem_ok/graded:.0%}  (베이스라인)")
        print(f"메모리 이득 : +{(with_mem_ok - no_mem_ok)/graded:.0%}p")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
