"""요청별 트레이싱 — 에이전트 호출을 구조화 로그(JSONL)로 남기고 지표를 집계한다.

운영 관측성: 각 질문마다 생성 SQL 길이·검증/실행 성공·스캔 바이트(=비용)·지연(ms)·
자기수정 여부를 한 줄 JSON으로 기록한다(stdout + 선택적 파일). `summarize()`는 성공률·
지연 분위수·총 스캔량 등 지표를 뽑는 순수 함수라 네트워크 없이 단위 테스트된다.

설정(환경변수):
  TRACE_FILE   기록할 JSONL 경로(비우면 파일 기록 안 함, stdout만). 예: traces/trace.jsonl
  TRACE_ECHO   "0"이면 stdout 출력 끔(기본 켜짐 — HF Spaces 로그에 남도록).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class TraceRecord:
    ts: str
    question: str
    provider: str
    model: str
    ok: bool
    latency_ms: int
    sql_generated: bool = False
    repaired: bool = False
    bytes_processed: int = 0
    rows: int = 0
    warnings: int = 0
    error: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Tracer:
    """JSONL 한 줄씩 기록. 파일 경로/stdout 출력은 환경변수로 제어."""

    def __init__(self, path: str | None = None, echo: bool | None = None) -> None:
        self.path = os.getenv("TRACE_FILE", "") if path is None else path
        self.echo = (os.getenv("TRACE_ECHO", "1") != "0") if echo is None else echo

    def emit(self, rec: TraceRecord) -> None:
        line = json.dumps(asdict(rec), ensure_ascii=False)
        if self.echo:
            print("[trace] " + line, flush=True)
        if self.path:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


def _percentile(values: list[int], p: float) -> int:
    """가장 가까운 순위(nearest-rank 근사) 분위수. values는 비어있지 않다고 가정."""
    s = sorted(values)
    i = min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))
    return s[i]


def summarize(records: list[dict]) -> dict:
    """트레이스 레코드 목록 → 운영 지표(순수 함수)."""
    n = len(records)
    if n == 0:
        return {"count": 0}
    lat = [int(r.get("latency_ms", 0)) for r in records]
    oks = [r for r in records if r.get("ok")]
    return {
        "count": n,
        "success_rate": round(len(oks) / n, 3),
        "repair_rate": round(sum(1 for r in records if r.get("repaired")) / n, 3),
        "latency_ms_p50": _percentile(lat, 50),
        "latency_ms_p95": _percentile(lat, 95),
        "total_mb_scanned": round(sum(int(r.get("bytes_processed", 0)) for r in records) / 1024**2, 1),
        "avg_rows_ok": round(sum(int(r.get("rows", 0)) for r in oks) / len(oks), 1) if oks else 0,
    }


def load_traces(path: str) -> list[dict]:
    """JSONL 파일을 레코드 리스트로 읽는다."""
    out: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line:
                out.append(json.loads(line))
    return out


def _main() -> None:
    """python -m app.trace [경로] → 트레이스 요약 지표를 출력."""
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TRACE_FILE", "traces/trace.jsonl")
    if not os.path.exists(path):
        print(f"트레이스 파일이 없습니다: {path}")
        return
    print(json.dumps(summarize(load_traces(path)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
