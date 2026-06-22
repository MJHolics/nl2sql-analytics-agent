"""SQL 관련 순수 함수(네트워크·외부 의존 없음). 단위 테스트 대상.

에이전트/백엔드 런타임 로직에서 분리해 빠르게 검증할 수 있도록 모았다.
"""
from __future__ import annotations

import re

_SQL_BLOCK = re.compile(r"```(?:sql)?\s*(.+?)```", re.IGNORECASE | re.DOTALL)
_SELECT_ONLY = re.compile(r"^\s*(with|select)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant)\b", re.IGNORECASE
)
_COLUMN_REF = re.compile(r"\b[a-zA-Z_]\w*\.([a-zA-Z_]\w*)\b")


def extract_sql(text: str) -> str:
    """LLM 응답에서 SQL만 뽑는다. ```sql 블록이 있으면 그 안을, 없으면 전체를."""
    m = _SQL_BLOCK.search(text)
    sql = (m.group(1) if m else text).strip()
    return sql.rstrip(";").strip()


def check_read_only(sql: str) -> str | None:
    """조회 전용 가드. 위반 사유 문자열을 반환하고, 통과면 None."""
    if not _SELECT_ONLY.match(sql):
        return "SELECT/WITH 로 시작하는 조회 쿼리만 허용됩니다."
    if _FORBIDDEN.search(sql):
        return "DML/DDL(쓰기·삭제·생성) 구문은 금지됩니다."
    return None


def find_unknown_columns(sql: str, known_columns: set[str], skip: set[str] | None = None) -> list[str]:
    """`alias.column` 패턴 중 알려진 컬럼 집합에 없는 것을 의심 목록으로(할루시네이션 점검).
    skip은 컬럼이 아닌 토큰(예: 데이터셋·테이블명)을 제외하기 위한 소문자 집합."""
    skip = skip or set()
    refs = set(_COLUMN_REF.findall(sql))
    suspects = [c for c in refs if c.lower() not in known_columns and c.lower() not in skip]
    return sorted(suspects)
