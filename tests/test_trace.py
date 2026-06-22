"""트레이싱 순수 로직 테스트 — 네트워크·LLM·BigQuery 없이."""
from __future__ import annotations

import json

from app.trace import TraceRecord, Tracer, _percentile, load_traces, now_iso, summarize


def _rec(ok=True, latency=100, repaired=False, bytes_=0, rows=0):
    return {
        "ok": ok,
        "latency_ms": latency,
        "repaired": repaired,
        "bytes_processed": bytes_,
        "rows": rows,
    }


def test_summarize_empty():
    assert summarize([]) == {"count": 0}


def test_summarize_metrics():
    recs = [
        _rec(ok=True, latency=100, bytes_=1024**2, rows=5),
        _rec(ok=False, latency=300, repaired=True),
        _rec(ok=True, latency=200, bytes_=1024**2, rows=15),
    ]
    s = summarize(recs)
    assert s["count"] == 3
    assert s["success_rate"] == round(2 / 3, 3)
    assert s["repair_rate"] == round(1 / 3, 3)
    assert s["total_mb_scanned"] == 2.0
    # 성공 케이스 행 평균: (5+15)/2
    assert s["avg_rows_ok"] == 10.0


def test_percentile_bounds():
    vals = [10, 20, 30, 40, 50]
    assert _percentile(vals, 0) == 10
    assert _percentile(vals, 50) == 30
    assert _percentile(vals, 100) == 50


def test_tracer_writes_jsonl(tmp_path):
    path = tmp_path / "t.jsonl"
    tr = Tracer(path=str(path), echo=False)
    tr.emit(TraceRecord(ts=now_iso(), question="q1", provider="gemini", model="m", ok=True, latency_ms=42))
    tr.emit(TraceRecord(ts=now_iso(), question="q2", provider="gemini", model="m", ok=False, latency_ms=99))
    recs = load_traces(str(path))
    assert len(recs) == 2
    assert recs[0]["question"] == "q1" and recs[0]["ok"] is True
    assert recs[1]["latency_ms"] == 99
    # 각 줄이 유효한 JSON인지
    for line in path.read_text(encoding="utf-8").splitlines():
        json.loads(line)
