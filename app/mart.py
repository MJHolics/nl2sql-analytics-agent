"""데이터 마트 — DDL 템플릿 렌더링·문장 분리(순수 로직, 네트워크 없음).

무료/샌드박스 전제:
  - 원본(`bigquery-public-data.thelook_ecommerce`)은 읽기전용 공개셋이므로,
    마트는 **본인 프로젝트의 별도 데이터셋**에 만든다(샌드박스에서 무료).
  - staging은 뷰(저장 0, 의미 계층) — 업무 용어로 핵심 컬럼만 노출.
  - mart는 사전집계 테이블(CTAS) — 작은 집계라 조회 시 원본 전체 스캔(수백 MB) 대신
    수 KB만 스캔한다 → 비용·지연 절감(dry-run 스캔 바이트로 측정, 비용 0).

DDL 템플릿의 자리표시자:
  {SOURCE} → 원본 `project.dataset`
  {MART}   → 마트 `project.dataset`
"""
from __future__ import annotations


def render_ddl(text: str, *, source: str, mart: str) -> str:
    """DDL 템플릿의 자리표시자를 실제 식별자로 치환."""
    return text.replace("{SOURCE}", source).replace("{MART}", mart)


def split_statements(sql: str) -> list[str]:
    """세미콜론 기준으로 실행 가능한 문장으로 분리.

    각 문장에서 줄 단위 주석(`--`)과 빈 줄을 제거하고, 내용이 남는 문장만 반환한다.
    (DDL에 문자열 리터럴 속 ';'가 없다는 전제 — 본 마트 DDL은 이를 만족.)
    """
    statements = []
    for chunk in sql.split(";"):
        lines = [ln for ln in chunk.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements
