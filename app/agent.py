"""NL2SQL 분석 에이전트.

흐름: 질문 → (RAG 그라운딩) → SQL 생성 → 검증(dry-run + 컬럼 점검) →
실패 시 1회 자기수정 → 실행 → 자연어 요약.

가드레일:
  - SELECT 전용 / DML·DDL 금지 (bq.validate)
  - dry-run 비용 한도 초과 거부
  - 근거(retrieval) 빈약 시 경고 플래그
  - 생성 SQL이 미지의 컬럼을 참조하면 할루시네이션으로 표시
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.bq import BigQueryBackend
from app.llm import LLM
from app.retriever import Retriever
from app.sqlutils import extract_sql, find_unknown_columns
from app.trace import Tracer, TraceRecord, now_iso
import config

_SYS = """너는 BigQuery Standard SQL을 작성하는 데이터 분석 에이전트다.
규칙:
- 반드시 제공된 스키마의 테이블/컬럼만 사용한다. 모르면 추측하지 말고 빈 SQL을 낸다.
- 테이블은 스키마에 적힌 **전체 경로를 글자 그대로** 백틱으로 감싸 쓴다
  (예: `bigquery-public-data.thelook_ecommerce.orders`). 'project'/'dataset' 같은
  자리표시자를 절대 그대로 쓰지 말고, 스키마의 실제 이름으로 채운다.
- 오직 조회(SELECT/WITH)만 작성한다. 쓰기·삭제·생성 구문 금지.
- 큰 스캔을 피하려 필요한 컬럼만 선택하고 합리적으로 LIMIT을 건다.
- 출력은 SQL 코드 한 블록만. 설명 문장 금지."""

@dataclass
class AgentResult:
    question: str
    sql: str = ""
    rows: list[dict] = field(default_factory=list)
    answer: str = ""
    ok: bool = False
    error: str | None = None
    bytes_processed: int = 0
    warnings: list[str] = field(default_factory=list)
    repaired: bool = False


class Nl2SqlAgent:
    def __init__(self, tracer: Tracer | None = None) -> None:
        self.bq = BigQueryBackend()
        self.llm = LLM()
        self.retriever = Retriever()
        self.tracer = tracer or Tracer()
        self._known_cols: set[str] | None = None
        self.schema_text: str = ""

    def setup(self) -> None:
        """스키마를 읽어 그라운딩 인덱스를 구축. 최초 1회(또는 스키마 변경 시)."""
        cards = self.bq.schema_cards()
        self.retriever.index(cards)
        # 테이블이 7개뿐이라 스키마 전체는 항상 컨텍스트에 넣는다(검색 누락 방지).
        self.schema_text = "\n".join(c["text"] for c in cards)
        self._known_cols = self.bq.known_columns()

    def build_context(self, question: str) -> tuple[str, float]:
        """전체 스키마(항상) + 질문 관련 용어·예시(검색)를 합친 그라운딩 컨텍스트."""
        retrieved, top_distance = self.retriever.retrieve(question)
        context = f"## 스키마(전체)\n{self.schema_text}\n\n## 관련 용어·예시\n{retrieved}"
        return context, top_distance

    def _known_columns(self) -> set[str]:
        if self._known_cols is None:
            self._known_cols = self.bq.known_columns()
        return self._known_cols

    def _hallucinated_columns(self, sql: str) -> list[str]:
        """`alias.column` 패턴의 컬럼이 데이터셋에 없으면 의심 목록으로."""
        # 데이터셋명(테이블 경로의 토큰)은 컬럼이 아니므로 제외
        return find_unknown_columns(sql, self._known_columns(), skip={self.bq.dataset.lower()})

    def _generate_sql(self, question: str, context: str, prior_error: str | None = None) -> str:
        user = f"# 사용 가능한 스키마·용어·예시\n{context}\n\n# 질문\n{question}"
        if prior_error:
            user += (
                f"\n\n# 직전 시도가 다음 오류로 실패했다. 오류를 고쳐 다시 작성하라.\n{prior_error}"
            )
        return extract_sql(self.llm.complete(_SYS, user))

    def answer(self, question: str, summarize: bool = True) -> AgentResult:
        """공개 진입점: 내부 처리를 시간 측정·트레이싱으로 감싼다."""
        t0 = time.perf_counter()
        res = self._answer(question, summarize)
        self.tracer.emit(
            TraceRecord(
                ts=now_iso(),
                question=question,
                provider=self.llm.provider,
                model=self.llm.model,
                ok=res.ok,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                sql_generated=bool(res.sql),
                repaired=res.repaired,
                bytes_processed=res.bytes_processed,
                rows=len(res.rows),
                warnings=len(res.warnings),
                error=res.error,
            )
        )
        return res

    def _answer(self, question: str, summarize: bool = True) -> AgentResult:
        res = AgentResult(question=question)

        context, top_distance = self.build_context(question)
        if top_distance > config.LOW_GROUNDING_DISTANCE:
            res.warnings.append(
                f"근거가 빈약합니다(거리 {top_distance:.2f}). 질문이 데이터 범위 밖일 수 있습니다."
            )

        sql = self._generate_sql(question, context)
        if not sql:
            res.error = "에이전트가 답할 근거를 찾지 못해 SQL 생성을 거부했습니다."
            return res

        # 1차 검증 → 실패 시 오류를 피드백해 1회 자기수정
        val = self.bq.validate(sql)
        if not val.ok:
            repaired = self._generate_sql(question, context, prior_error=val.error)
            if repaired and repaired != sql:
                rval = self.bq.validate(repaired)
                if rval.ok:
                    sql, val, res.repaired = repaired, rval, True
        res.sql = sql

        if not val.ok:
            res.error = f"SQL 검증 실패: {val.error}"
            return res

        suspects = self._hallucinated_columns(sql)
        if suspects:
            res.warnings.append(f"미확인 컬럼 참조 의심: {', '.join(suspects)}")

        out = self.bq.run(sql)
        res.rows = out.rows
        res.bytes_processed = out.bytes_processed
        res.ok = True

        if summarize and out.rows:
            res.answer = self._summarize(question, out.rows)
        return res

    def _summarize(self, question: str, rows: list[dict]) -> str:
        preview = rows[:20]
        sys = "너는 데이터 분석 결과를 한국어로 간결히 요약한다. 숫자는 그대로 인용한다."
        user = f"질문: {question}\n결과(JSON, 일부):\n{preview}\n\n2~3문장으로 답하라."
        try:
            return self.llm.complete(sys, user)
        except Exception:
            return ""
