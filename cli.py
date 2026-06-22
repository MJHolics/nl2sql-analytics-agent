"""대화형 CLI. 자연어로 물으면 SQL을 만들어 검증·실행하고 답한다.

  python cli.py                       # 대화형
  python cli.py "카테고리별 매출 top 5"  # 한 번 묻고 종료
  python cli.py --dry-run "..."        # 실행 없이 SQL 생성·검증만(비용 0)
"""
from __future__ import annotations

import argparse

from app.agent import Nl2SqlAgent


def _show(res) -> None:
    if res.sql:
        print("\n-- 생성 SQL" + (" (자기수정됨)" if res.repaired else "") + " --")
        print(res.sql)
    for w in res.warnings:
        print(f"⚠ {w}")
    if not res.ok:
        print(f"\n✗ {res.error}")
        return
    print(f"\n스캔: {res.bytes_processed/1024**2:.1f}MB · 행: {len(res.rows)}")
    if res.answer:
        print(f"\n[답변] {res.answer}")
    for r in res.rows[:10]:
        print("  ", r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*", help="자연어 질문")
    ap.add_argument("--dry-run", action="store_true", help="실행 없이 SQL 생성·검증만")
    args = ap.parse_args()

    agent = Nl2SqlAgent()
    print(f"LLM provider: {agent.llm.provider} ({agent.llm.model})")
    print("스키마 그라운딩 인덱스 구축 중…")
    agent.setup()

    def ask(q: str) -> None:
        if args.dry_run:
            ctx, _ = agent.build_context(q)
            sql = agent._generate_sql(q, ctx)
            val = agent.bq.validate(sql)
            print("\n-- 생성 SQL --\n" + sql)
            print(("✓ 검증 통과, 예상 스캔 %.1fMB" % (val.gb * 1024)) if val.ok else f"✗ {val.error}")
        else:
            _show(agent.answer(q))

    if args.question:
        ask(" ".join(args.question))
        return

    print("질문을 입력하세요(빈 줄/Ctrl-C 종료).")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        ask(q)


if __name__ == "__main__":
    main()
