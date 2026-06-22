"""Hugging Face Spaces 진입점 — NL2SQL 분석 에이전트 웹 데모(gradio).

자연어 질문 → BigQuery SQL 생성 → dry-run 검증 → (실행) → 자연어 요약.

원격 호스트(Spaces 등)는 로컬 gcloud ADC가 없으므로 BigQuery 인증을 secret으로 준다:
  - GEMINI_API_KEY           : Gemini 무료 키(필수)
  - GOOGLE_CLOUD_PROJECT     : 쿼리를 청구할 본인 프로젝트 id(필수)
  - GCP_SA_KEY               : (선택) 서비스계정 JSON '문자열'. 주면 파일로 써서 인증.
                               없으면 기존 GOOGLE_APPLICATION_CREDENTIALS/ADC를 그대로 사용.
이 부트스트랩은 config/agent를 import 하기 전에 실행돼야 한다(클라이언트가 그때 만들어지므로).
"""
from __future__ import annotations

import json
import os
import tempfile


def _bootstrap_gcp_credentials() -> None:
    """GCP_SA_KEY(JSON 문자열)가 있으면 임시 파일로 써서 GOOGLE_APPLICATION_CREDENTIALS로 노출."""
    raw = os.getenv("GCP_SA_KEY")
    if not raw or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        return  # 잘못된 JSON이면 ADC 경로로 두고 넘어간다(실행 시 친절한 오류로 안내됨).
    # SA JSON에 project_id가 있으면 청구 프로젝트 기본값으로도 채운다.
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", info.get("project_id", ""))
    path = os.path.join(tempfile.gettempdir(), "gcp-sa.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path


_bootstrap_gcp_credentials()

import gradio as gr  # noqa: E402

# --- 에이전트 지연 초기화 -------------------------------------------------------
# setup()은 BigQuery 스키마 조회 + ChromaDB 색인이라 비싸다. 첫 질문 때 1회만 만든다.
_agent = None
_init_error: str | None = None


def _get_agent():
    global _agent, _init_error
    if _agent is not None or _init_error is not None:
        return _agent
    try:
        from app.agent import Nl2SqlAgent

        agent = Nl2SqlAgent()
        agent.setup()
        _agent = agent
    except Exception as e:  # 키·인증 누락 등 → UI에 친절히 표시
        _init_error = (
            f"{type(e).__name__}: {e}\n\n"
            "필요한 secret을 확인하세요: GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT"
            "(서비스계정을 쓰면 GCP_SA_KEY)."
        )
    return _agent


def _fmt_rows(rows: list[dict]) -> str:
    if not rows:
        return "_(행 없음)_"
    cols = list(rows[0].keys())
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = [
        "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows[:20]
    ]
    return "\n".join([head, sep, *body])


def run_query(question: str, dry_run: bool):
    """gradio 콜백 → (SQL, 상태/요약, 결과표 markdown)."""
    question = (question or "").strip()
    if not question:
        return "", "질문을 입력하세요.", ""

    agent = _get_agent()
    if agent is None:
        return "", f"⚠ 초기화 실패\n\n{_init_error}", ""

    try:
        if dry_run:
            ctx, dist = agent.build_context(question)
            sql = agent._generate_sql(question, ctx)
            if not sql:
                return "", "에이전트가 근거를 찾지 못해 SQL 생성을 거부했습니다.", ""
            val = agent.bq.validate(sql)
            status = (
                f"✓ 검증 통과 · 예상 스캔 {val.gb * 1024:.1f}MB (실행 안 함)"
                if val.ok
                else f"✗ 검증 실패: {val.error}"
            )
            return sql, status, ""

        res = agent.answer(question)
        lines = []
        if res.repaired:
            lines.append("🛠 1회 자기수정으로 통과한 SQL입니다.")
        for w in res.warnings:
            lines.append(f"⚠ {w}")
        if not res.ok:
            lines.append(f"✗ {res.error}")
            return res.sql, "\n".join(lines), ""
        lines.append(
            f"스캔 {res.bytes_processed / 1024**2:.1f}MB · 행 {len(res.rows)}"
        )
        if res.answer:
            lines.append(f"\n**답변** — {res.answer}")
        return res.sql, "\n".join(lines), _fmt_rows(res.rows)
    except Exception as e:
        return "", f"오류: {type(e).__name__}: {e}", ""


_EXAMPLES = [
    ["카테고리별 총 매출 상위 5개는?", False],
    ["유입 채널별 고객 수를 많은 순으로", False],
    ["완료된 주문의 월별 매출 추이", False],
    ["객단가가 가장 높은 카테고리 3개", True],
]

_DESC = """\
자연어 질문을 **BigQuery Standard SQL로 변환·검증·실행**하고 답을 돌려주는 분석 에이전트입니다.
실행 전 **dry-run**으로 문법·컬럼·스캔 비용을 확인하고, RAG로 스키마·용어를 그라운딩합니다.

데이터: `bigquery-public-data.thelook_ecommerce` (가상 이커머스 B2C 공개 데이터셋) ·
[GitHub](https://github.com/MJHolics/nl2sql-analytics-agent)

> **dry-run 모드**를 켜면 SQL 생성·검증만 하고 **실행하지 않습니다**(BigQuery 스캔 비용 0).
"""

with gr.Blocks(title="NL2SQL Analytics Agent") as demo:
    gr.Markdown("# 🔎 NL2SQL Analytics Agent")
    gr.Markdown(_DESC)
    with gr.Row():
        question = gr.Textbox(
            label="질문(자연어)", placeholder="예: 카테고리별 총 매출 상위 5개는?", scale=4
        )
        dry_run = gr.Checkbox(label="dry-run(실행 안 함)", value=False, scale=1)
    submit = gr.Button("질문하기", variant="primary")
    sql_out = gr.Code(label="생성된 SQL", language="sql")
    status_out = gr.Markdown(label="상태 · 요약")
    rows_out = gr.Markdown(label="결과(상위 20행)")

    gr.Examples(examples=_EXAMPLES, inputs=[question, dry_run])
    submit.click(run_query, inputs=[question, dry_run], outputs=[sql_out, status_out, rows_out])
    question.submit(run_query, inputs=[question, dry_run], outputs=[sql_out, status_out, rows_out])


if __name__ == "__main__":
    demo.launch()
