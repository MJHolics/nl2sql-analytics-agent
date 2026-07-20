"""데이터 마트 구축·품질점검·스캔 절감 측정 (전부 무료, BigQuery 샌드박스 OK).

  python build_mart.py            # staging 뷰 + 집계 마트 생성 후 품질 점검
  python build_mart.py --compare  # 원본 직접쿼리 vs 마트 경유 스캔 바이트 비교(dry-run, 비용 0)

원본은 읽기전용 공개셋이라, 마트는 본인 프로젝트의 `config.MART_DATASET`에 만든다.
필요: GOOGLE_CLOUD_PROJECT(샌드박스 프로젝트 id 가능) + `gcloud auth application-default login`.
"""
from __future__ import annotations

import argparse
import os

from google.cloud import bigquery

import config
from app.mart import render_ddl, split_statements

_MART_DIR = os.path.join(os.path.dirname(__file__), "mart")


def _read(name: str) -> str:
    return open(os.path.join(_MART_DIR, name), encoding="utf-8").read()


def _mart_fqn() -> str:
    return f"{config.BILLING_PROJECT}.{config.MART_DATASET}"


def build(client: bigquery.Client) -> None:
    source, mart = config.SOURCE_DATASET, _mart_fqn()
    for fname in ("staging.sql", "marts.sql"):
        ddl = render_ddl(_read(fname), source=source, mart=mart)
        stmts = split_statements(ddl)
        print(f"\n[{fname}] {len(stmts)}개 문장 실행")
        for stmt in stmts:
            head = stmt.splitlines()[0][:70]
            client.query(stmt).result()
            print(f"   ✓ {head}…")


def quality(client: bigquery.Client) -> bool:
    sql = render_ddl(_read("quality_checks.sql"), source=config.SOURCE_DATASET, mart=_mart_fqn())
    # quality_checks.sql 은 단일 SELECT 한 문장
    rows = [dict(r) for r in client.query(split_statements(sql)[0]).result()]
    print("\n===== 품질 점검 =====")
    failed = 0
    for r in rows:
        v = int(r["violations"])
        print(f"   {'✓' if v == 0 else '✗'} {r['check_name']}: 위반 {v}")
        failed += v != 0
    print(f"\n{'전체 통과' if failed == 0 else f'{failed}개 점검 실패'}")
    return failed == 0


def compare(client: bigquery.Client) -> None:
    """같은 질문을 원본 직접쿼리 vs 마트 경유로 dry-run해 스캔 바이트를 비교."""
    source, mart = config.SOURCE_DATASET, _mart_fqn()
    raw = f"""
        SELECT p.category, SUM(oi.sale_price) AS revenue
        FROM `{source}.order_items` oi
        JOIN `{source}.products` p ON oi.product_id = p.id
        GROUP BY p.category ORDER BY revenue DESC LIMIT 3
    """
    via_mart = f"SELECT category, revenue FROM `{mart}.mart_category_revenue` ORDER BY revenue DESC LIMIT 3"

    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    raw_bytes = client.query(raw, job_config=cfg).total_bytes_processed or 0
    mart_bytes = client.query(via_mart, job_config=cfg).total_bytes_processed or 0

    print("\n===== 스캔 절감 (dry-run, 비용 0) =====")
    print(f"   원본 직접쿼리 : {raw_bytes/1024**2:9.2f} MB")
    print(f"   마트 경유     : {mart_bytes/1024**2:9.2f} MB")
    if raw_bytes:
        print(f"   절감          : {(1 - mart_bytes/raw_bytes):.1%}↓")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true", help="원본 vs 마트 스캔 바이트 비교만")
    args = ap.parse_args()

    if not config.BILLING_PROJECT:
        print("✗ GOOGLE_CLOUD_PROJECT(또는 GCP_PROJECT)를 설정하세요.")
        return 1

    client = bigquery.Client(project=config.BILLING_PROJECT)
    print(f"마트 대상: {_mart_fqn()}  (원본: {config.SOURCE_DATASET})")

    if args.compare:
        compare(client)
        return 0

    build(client)
    ok = quality(client)
    compare(client)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
