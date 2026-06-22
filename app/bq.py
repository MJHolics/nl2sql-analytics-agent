"""BigQuery 백엔드: 스키마 조회 + SQL 검증(dry-run) + 실행.

핵심은 dry-run 검증이다 — 실제 데이터를 스캔하기 전에 문법·컬럼 오류를 잡고,
스캔될 바이트(=비용)를 미리 알아 임계 초과 시 실행을 거부한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from google.cloud import bigquery

import config
from app.sqlutils import check_read_only


@dataclass
class Validation:
    ok: bool
    error: str | None = None
    bytes_processed: int = 0

    @property
    def gb(self) -> float:
        return self.bytes_processed / 1024**3


@dataclass
class QueryResult:
    rows: list[dict] = field(default_factory=list)
    bytes_processed: int = 0
    sql: str = ""


class BigQueryBackend:
    def __init__(self) -> None:
        self.client = bigquery.Client(project=config.BILLING_PROJECT)
        # `프로젝트.데이터셋` 분해
        self.source_project, self.dataset = config.SOURCE_DATASET.split(".", 1)

    # --- 스키마 ---
    def schema_cards(self) -> list[dict]:
        """INFORMATION_SCHEMA에서 테이블/컬럼을 읽어 그라운딩용 카드로 만든다."""
        sql = f"""
            SELECT table_name, column_name, data_type
            FROM `{self.source_project}.{self.dataset}.INFORMATION_SCHEMA.COLUMNS`
            ORDER BY table_name, ordinal_position
        """
        job = self.client.query(sql)
        tables: dict[str, list[str]] = {}
        for r in job.result():
            tables.setdefault(r["table_name"], []).append(f"{r['column_name']} {r['data_type']}")
        cards = []
        for t, cols in tables.items():
            fq = f"{self.source_project}.{self.dataset}.{t}"
            cards.append(
                {
                    "id": f"schema::{t}",
                    "text": f"테이블 `{fq}` 컬럼: " + ", ".join(cols),
                    "meta": {"kind": "schema", "table": t},
                }
            )
        return cards

    def known_columns(self) -> set[str]:
        """할루시네이션 점검용: 데이터셋에 실재하는 컬럼명 집합(소문자)."""
        sql = f"""
            SELECT DISTINCT column_name
            FROM `{self.source_project}.{self.dataset}.INFORMATION_SCHEMA.COLUMNS`
        """
        return {r["column_name"].lower() for r in self.client.query(sql).result()}

    # --- 검증 / 실행 ---
    def validate(self, sql: str) -> Validation:
        """SELECT 전용 가드 + dry-run으로 문법/컬럼/비용 검증."""
        guard = check_read_only(sql)
        if guard is not None:
            return Validation(False, guard)
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        try:
            job = self.client.query(sql, job_config=cfg)
        except Exception as e:  # 문법·컬럼 오류 등
            return Validation(False, str(e).splitlines()[0])
        if job.total_bytes_processed and job.total_bytes_processed > config.MAX_BYTES_BILLED:
            return Validation(
                False,
                f"스캔 예상 {job.total_bytes_processed/1024**3:.2f}GB가 한도를 초과합니다.",
                job.total_bytes_processed,
            )
        return Validation(True, None, job.total_bytes_processed or 0)

    def run(self, sql: str, max_rows: int = 50) -> QueryResult:
        cfg = bigquery.QueryJobConfig(maximum_bytes_billed=config.MAX_BYTES_BILLED)
        job = self.client.query(sql, job_config=cfg)
        rows = [dict(r) for r in job.result(max_results=max_rows)]
        return QueryResult(rows=rows, bytes_processed=job.total_bytes_processed or 0, sql=sql)
