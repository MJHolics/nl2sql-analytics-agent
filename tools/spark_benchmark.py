"""pandas vs PySpark(local[*]) — "대용량 데이터" 갭을 크로스오버 지점으로 실측한다.

## 왜 하는가

이 저장소의 대용량 데이터 처리는 전부 **BigQuery(관리형 SQL 엔진)**를 통해서였다
(`build_mart.py`). Spark 자체를 돌려본 적은 없었다 — 여러 공고(디오 AI Platform 데이터
엔지니어 등)가 명시 요구하는 "대용량 데이터(Spark 등)" 경험이 갭으로 남아 있던 이유다.

## 무엇을 재는가

"Spark가 빠르다"는 막연한 주장 대신, **어느 데이터 규모부터 pandas(단일 프로세스, 벡터화)를
역전하는지 크로스오버 지점을 찾는다.** 작은 데이터에서 Spark가 지는 것은 이미 여러 스킬업
(Qdrant·K8s 등)에서 반복된 패턴("오버헤드가 있는 도구는 작은 규모에서 손해")이라 그 자체는
새 발견이 아니다 — 이번엔 **얼마나 커야 이기는지 숫자로** 답한다.

세 가지 실무 패턴의 연산을 규모별로(1만~2천만 행) 양쪽에서 실행:
  1. **groupby-agg** — 라인·제품별 건수·평균 신뢰도 (검사 도메인 스키마, inspection-copilot과 동일 발상)
  2. **join** — 이벤트 테이블과 제품 메타데이터(소규모 차원 테이블) 조인
  3. **window** — 라인별 7행 이동평균(정렬 필요 — Spark의 파티션 간 셔플이 드러나는 연산)

## 실행 (WSL2, Java 17 + PySpark 3.5.3 venv 필요)

    wsl -d Ubuntu -- ~/spark_bench/venv/bin/python /mnt/c/.../tools/spark_benchmark.py

## 정직한 한계

로컬 `local[*]` 단일 머신 모드다 — **실제 멀티노드 클러스터·YARN/K8s 스케줄링·셔플 장애
복구 경험은 아니다.** PySpark API(DataFrame·groupBy·window)를 실무 패턴으로 직접 짜고,
pandas 대비 언제 유리한지를 재본 것까지가 선이다.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
OUT = ROOT / "tools" / "spark_benchmark_result.json"

SCALES = [10_000, 100_000, 1_000_000, 5_000_000, 20_000_000]
SEED = 42

_LINES = np.array(["L1", "L2", "L3"])
_PRODUCTS = np.array(["steel_coil", "steel_plate", "steel_strip"])
_DEFECTS = np.array(["none", "scratches", "patches", "crazing", "inclusion", "pitted_surface", "rolled-in_scale"])


def make_data(n: int, seed: int = SEED) -> pd.DataFrame:
    """검사 이벤트 합성 데이터 — 벡터화 생성(행 단위 루프 없음, 2천만 행도 수 초).

    inspection-copilot/app/db.py와 같은 스키마 발상(검사 이벤트 1건=1행)이지만
    분포는 이 벤치마크 전용 — 라인·제품·결함을 균등 샘플링해 groupby 카디널리티를 고정한다.
    """
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "event_id": np.arange(n, dtype=np.int64),
        "day": rng.integers(0, 90, size=n, dtype=np.int32),
        "line": rng.choice(_LINES, size=n),
        "product": rng.choice(_PRODUCTS, size=n),
        "defect_class": rng.choice(_DEFECTS, size=n, p=[0.6, 0.1, 0.1, 0.06, 0.06, 0.04, 0.04]),
        "confidence": rng.uniform(0.5, 1.0, size=n).astype(np.float32),
    })


def dim_products() -> pd.DataFrame:
    return pd.DataFrame({
        "product": _PRODUCTS,
        "unit_price": [120.5, 98.0, 145.2],
        "plant": ["dangjin", "pohang", "gwangyang"],
    })


_DIM_ROWS = [
    ("steel_coil", 120.5, "dangjin"),
    ("steel_plate", 98.0, "pohang"),
    ("steel_strip", 145.2, "gwangyang"),
]


# ---------------------------------------------------------------------------
# pandas
# ---------------------------------------------------------------------------


def pandas_groupby(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["line", "product"])
        .agg(n=("event_id", "count"), avg_conf=("confidence", "mean"))
        .reset_index()
    )


def pandas_join(df: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    return df.merge(dim, on="product", how="inner")


def pandas_window(df: pd.DataFrame) -> pd.DataFrame:
    d = df.sort_values(["line", "day"])
    d["rolling_conf"] = d.groupby("line")["confidence"].transform(
        lambda s: s.rolling(7, min_periods=1).mean()
    )
    return d


# ---------------------------------------------------------------------------
# spark
# ---------------------------------------------------------------------------


def spark_groupby(sdf, spark):
    from pyspark.sql import functions as F

    return sdf.groupBy("line", "product").agg(
        F.count("event_id").alias("n"), F.avg("confidence").alias("avg_conf")
    )


def spark_join(sdf, sdim):
    return sdf.join(sdim, on="product", how="inner")


def spark_window(sdf):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    w = Window.partitionBy("line").orderBy("day").rowsBetween(-6, 0)
    return sdf.withColumn("rolling_conf", F.avg("confidence").over(w))


def timed(fn, materialize):
    t0 = time.perf_counter()
    result = fn()
    materialize(result)
    return time.perf_counter() - t0


def main() -> None:
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.appName("gap-benchmark")
        .master("local[*]")
        .config("spark.driver.memory", "8g")
        .config("spark.sql.shuffle.partitions", "16")  # 로컬 16코어에 맞춤(기본 200은 소규모에 과함)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    # PySpark 3.5.x + Python 3.12: spark.createDataFrame(pandas_df)의 화살표 변환 경로가
    # distutils(3.12에서 제거됨)를 import하다 죽는다(ModuleNotFoundError). pandas 객체를
    # 드라이버 메모리로 마샬링하는 것 자체도 "대용량"에는 안 맞는 경로라, 실무처럼
    # **Parquet 파일을 거쳐** 읽는 방식으로 우회한다 — 우연한 회피가 아니라 더 현실적인 설계다.
    dim = dim_products()
    sdim = spark.createDataFrame(_DIM_ROWS, schema=["product", "unit_price", "plant"])

    tmp_dir = ROOT / "tools" / "_spark_bench_tmp"
    tmp_dir.mkdir(exist_ok=True)

    rows = []
    for n in SCALES:
        print(f"\n=== n={n:,} ===")
        df = make_data(n)
        pq_path = tmp_dir / f"events_{n}.parquet"
        df.to_parquet(pq_path, index=False)
        sdf = spark.read.parquet(str(pq_path)).cache()
        sdf.count()  # cache materialize, 측정에서 제외

        pd_gb = timed(lambda: pandas_groupby(df), lambda r: len(r))
        sp_gb = timed(lambda: spark_groupby(sdf, spark), lambda r: r.count())

        pd_join = timed(lambda: pandas_join(df, dim), lambda r: len(r))
        sp_join = timed(lambda: spark_join(sdf, sdim), lambda r: r.count())

        pd_win = timed(lambda: pandas_window(df), lambda r: len(r))
        sp_win = timed(lambda: spark_window(sdf), lambda r: r.count())

        row = {
            "n_rows": n,
            "groupby_s": {"pandas": pd_gb, "spark": sp_gb, "spark_wins": sp_gb < pd_gb},
            "join_s": {"pandas": pd_join, "spark": sp_join, "spark_wins": sp_join < pd_join},
            "window_s": {"pandas": pd_win, "spark": sp_win, "spark_wins": sp_win < pd_win},
        }
        rows.append(row)
        print(json.dumps(row, indent=2))
        sdf.unpersist()
        pq_path.unlink(missing_ok=True)

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
