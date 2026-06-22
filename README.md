---
title: NL2SQL Analytics Agent
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.19.0
app_file: app.py
pinned: false
---

# NL2SQL Analytics Agent — BigQuery 자연어 분석 에이전트

[![CI](https://github.com/MJHolics/nl2sql-analytics-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MJHolics/nl2sql-analytics-agent/actions/workflows/ci.yml)

자연어 질문을 **BigQuery Standard SQL로 변환·검증·실행**하고 답을 돌려주는 분석 에이전트입니다.
핵심은 "그럴듯한 SQL"이 아니라 **검증된 SQL** — 실행 전 dry-run으로 문법·컬럼·비용을 확인하고,
RAG로 스키마·용어를 그라운딩하며, 평가 하네스로 정확도를 수치화합니다.

> 데이터: `bigquery-public-data.thelook_ecommerce` (가상 이커머스 B2C 공개 데이터셋)

---

## 무엇을 하나

```
질문(자연어)
  → RAG 그라운딩 (스키마 카드 + 용어사전 + 예시쿼리 검색, ChromaDB)
  → LLM이 BigQuery SQL 생성
  → 검증: dry-run(문법·컬럼·스캔 비용) + SELECT 전용 가드 + 미지 컬럼 점검
  → 실패하면 오류를 피드백해 1회 자기수정
  → 실행 → 결과를 자연어로 요약
```

### 설계 포인트 (이 직무의 요구에 대응)
- **컨텍스트 설계**: 업무 용어(매출/완료주문/객단가…)를 컬럼에 매핑한 용어사전과 검증된 예시 쿼리를
  벡터 검색으로 주입(`knowledge/`). 분석가의 말과 스키마의 간극을 메웁니다.
- **검증 쿼리(dry-run)**: 실제 데이터를 스캔하기 전에 BigQuery dry-run으로 문법·컬럼 오류를 잡고,
  스캔 예상 바이트가 한도를 넘으면 실행을 거부합니다(비용 가드레일).
- **할루시네이션 제어**: 조회(SELECT/WITH) 외 구문 금지, 데이터셋에 없는 컬럼 참조를 탐지해 경고,
  근거(retrieval) 거리가 멀면 "데이터 범위 밖일 수 있음"을 표시합니다.
- **에이전트 평가(Eval)**: `eval/run_eval.py` 가 두 지표를 출력 — 생성 SQL의 **validity rate**(dry-run 통과율)와
  gold SQL 대비 **answer match**(실행 결과 일치율).

---

## 실측 결과 (thelook_ecommerce, 평가셋 6문항)

`python -m eval.run_eval` 로 측정. **validity rate** = 생성 SQL이 dry-run 검증을 통과해 실행된 비율,
**answer match** = gold SQL 결과와 값이 일치한 비율(gold 보유 4문항 한정, 컬럼명·추가컬럼 무시한 값 기준).

| 모델 | validity | answer match | 비고 |
|---|---|---|---|
| gemini-2.5-flash | 100% (6/6) | 100% (4/4) | 4문항 모두 정답 |
| gemini-2.5-flash-lite | 100% (6/6) | 75% (3/4) | Q1에서 "카테고리별"을 상품 단위로 집계 |

**관찰 — 실행가능(validity) ≠ 정답(answer match).** 두 모델 모두 6문항 전부 *문법적으로 유효한*
SQL을 만들어 실행됐지만(validity 100%), 약한 모델은 "카테고리별 매출"을 *상품별*로 잘못 집계했다.
dry-run 검증은 이걸 못 잡는다(유효한 SQL이므로) — 그래서 **gold 기반 answer-match 평가가 따로 필요하다**.
이 평가 하네스가 바로 그 의미적 오류를 잡아낸다.

---

## 빠른 시작 (전부 무료)

### 1) Gemini 무료 API 키
[Google AI Studio](https://aistudio.google.com) → API key 발급(무료, 카드 불필요).
```bash
export GEMINI_API_KEY=...        # Windows PowerShell: $env:GEMINI_API_KEY="..."
```
> Anthropic·OpenAI도 지원합니다. `ANTHROPIC_API_KEY` 또는 `OPENAI_API_KEY` 를 설정하면 자동 선택됩니다.

### 2) BigQuery 접근 (샌드박스도 무료)
[BigQuery 샌드박스](https://cloud.google.com/bigquery/docs/sandbox)는 카드 없이 월 1TB 쿼리가 무료입니다.
프로젝트를 만들고 인증합니다.
```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project-id
```

### 3) 설치 & 실행
```bash
pip install -r requirements.txt

python cli.py "카테고리별 총 매출 상위 5개는?"
python cli.py --dry-run "유입 채널별 고객 수"   # 실행 없이 SQL 생성·검증만(비용 0)
python cli.py                                  # 대화형

python -m eval.run_eval                         # 평가 지표 출력
```

---

## 구조

| 파일 | 역할 |
|---|---|
| `app/agent.py` | 에이전트 오케스트레이션(생성→검증→자기수정→실행→요약) |
| `app/bq.py` | BigQuery 스키마 조회 · **dry-run 검증** · 실행 |
| `app/retriever.py` | ChromaDB 그라운딩(스키마·용어·예시 색인/검색) |
| `app/llm.py` | 제공자 무관 LLM 클라이언트(Gemini/Anthropic/OpenAI) |
| `knowledge/` | 용어사전 · 예시쿼리(컨텍스트 설계 자산) |
| `eval/` | 평가셋 + 하네스(validity / answer match) |

## 테스트 / CI

순수 로직(SQL 추출·조회 전용 가드·미지 컬럼 탐지·채점)을 `app/sqlutils.py`·`app/evalutils.py`로
분리해 네트워크·LLM·BigQuery 없이 단위 테스트한다. GitHub Actions가 push마다 lint(ruff) + pytest를 돌린다.

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest -q          # 22 passed
```

## 한계
- 다중 턴 대화·후속 질의 메모리는 없습니다(단일 질문 단위).
- gold answer match는 평가셋에 정의된 질문에 한합니다. 개방형 질문은 validity만 채점합니다.
- 임베딩은 ChromaDB 내장 모델(로컬)이라 한국어 검색 품질은 전용 임베딩(BGE-M3 등)보다 낮을 수 있습니다.
