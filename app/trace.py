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


def render_html(summary: dict, records: list[dict]) -> str:
    """요약 지표 + 최근 요청 표를 담은 정적 HTML 대시보드(순수 함수, 무의존).

    Cloud Monitoring의 무료 등가물 — JSONL 트레이스를 브라우저로 볼 수 있는 한 페이지로.
    """
    import html as _html

    def esc(v: object) -> str:
        return _html.escape(str(v))

    cards = [
        ("요청 수", summary.get("count", 0)),
        ("성공률", f"{summary.get('success_rate', 0):.0%}"),
        ("자기수정률", f"{summary.get('repair_rate', 0):.0%}"),
        ("지연 p50", f"{summary.get('latency_ms_p50', 0)} ms"),
        ("지연 p95", f"{summary.get('latency_ms_p95', 0)} ms"),
        ("총 스캔", f"{summary.get('total_mb_scanned', 0)} MB"),
    ]
    card_html = "".join(
        f'<div class="card"><div class="v">{esc(v)}</div><div class="k">{esc(k)}</div></div>'
        for k, v in cards
    )
    cols = ["ts", "question", "ok", "latency_ms", "bytes_processed", "repaired", "error"]
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body_rows = []
    for r in records[-50:][::-1]:  # 최근 50건, 최신 위로
        cells = "".join(f"<td>{esc(r.get(c, ''))}</td>" for c in cols)
        body_rows.append(f"<tr class=\"{'ok' if r.get('ok') else 'fail'}\">{cells}</tr>")
    table = "".join(body_rows)
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<title>NL2SQL — 운영 대시보드</title>
<style>
 body{{font-family:system-ui,'Malgun Gothic',sans-serif;margin:24px;color:#1a1a2e}}
 h1{{font-size:20px}} .cards{{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}}
 .card{{background:#f4f6fb;border-radius:10px;padding:14px 18px;min-width:110px}}
 .card .v{{font-size:22px;font-weight:700}} .card .k{{font-size:12px;color:#555}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th,td{{border-bottom:1px solid #eee;padding:6px 8px;text-align:left;max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
 tr.fail td{{background:#fff3f3}} th{{background:#fafafa}}
</style>
<h1>🔎 NL2SQL Analytics Agent — 운영 지표</h1>
<div class="cards">{card_html}</div>
<table><thead><tr>{head}</tr></thead><tbody>{table}</tbody></table>
</html>"""


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
    """python -m app.trace [경로] [--html [출력.html]] → 요약 지표 출력 / HTML 대시보드 생성."""
    import sys

    args = [a for a in sys.argv[1:] if a != "--html"]
    want_html = "--html" in sys.argv
    path = args[0] if args else os.getenv("TRACE_FILE", "traces/trace.jsonl")
    if not os.path.exists(path):
        print(f"트레이스 파일이 없습니다: {path}")
        return
    records = load_traces(path)
    summary = summarize(records)
    if want_html:
        out = args[1] if len(args) > 1 else "traces/dashboard.html"
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(render_html(summary, records))
        print(f"대시보드 생성: {out}  (요청 {summary.get('count', 0)}건)")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
