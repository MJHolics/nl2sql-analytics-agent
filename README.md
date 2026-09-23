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
[![Live Demo](https://img.shields.io/badge/🤗%20Live%20Demo-Spaces-yellow)](https://huggingface.co/spaces/appleholics/nl2sql-analytics-agent)

**▶ 라이브 데모:** https://huggingface.co/spaces/appleholics/nl2sql-analytics-agent
(질문을 입력하면 SQL을 생성·검증·실행합니다. `dry-run` 토글로 비용 0 검증만도 가능.)

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
python cli.py                                  # 대화형(후속 질문이 직전 답을 기억 — 멀티턴)

python -m eval.run_eval                         # validity / answer-match 지표
python -m eval.run_followup_eval                # 멀티턴 후속질의 정확도(메모리 있음 vs 없음)
```

### 데이터 마트 — staging 뷰 + 사전집계 테이블 (스캔 절감)

원본은 읽기전용 공개셋이라, 마트는 **본인 프로젝트의 데이터셋**(`config.MART_DATASET`)에 만든다(BigQuery 샌드박스에서 무료). **staging은 뷰**(저장 0, 업무 용어로 핵심 컬럼만 노출하는 의미 계층)이고, **mart는 사전집계 테이블**(CTAS)이다. 작은 요약 테이블이라 조회 시 원본 전체(수백 MB) 대신 수 KB만 스캔한다.

```bash
python build_mart.py            # staging 뷰 + 집계 마트 생성 + 품질 점검 + 스캔 비교
python build_mart.py --compare  # 원본 직접쿼리 vs 마트 경유 스캔 바이트(dry-run, 비용 0)
```

DDL은 `mart/`(staging·marts·quality_checks `.sql`)에 버전관리하고, 템플릿 렌더링·문장 분리는 순수 함수라 오프라인 단위테스트된다(`app/mart.py`, `tests/test_mart.py`). 품질 점검(키 NULL·음수 매출·완료>전체 모순·빈 테이블)이 마트 운영의 무결성을 수치로 보장한다.

### 파이프라인 자동화 — GitHub Actions 스케줄

`.github/workflows/pipeline.yml`이 마트를 **매일 스케줄(+수동 트리거)로 재적재**하고, 품질 점검이 실패하면 파이프라인을 실패시킨다(품질 게이트). 이는 **Cloud Functions + Cloud Scheduler의 무료 등가물** — 카드 등록 없이 "수집→적재→마트화 자동화"를 증명한다. BigQuery 서비스계정(`GCP_SA_KEY`)·프로젝트(`GOOGLE_CLOUD_PROJECT`)를 레포 Secret으로 두면 동작하고, 없으면 안전하게 건너뛴다(LLM 키 불필요 — 마트 갱신은 결정적).

### 배포 준비 — Cloud Run / Terraform / Vertex-ready

비용 0 원칙이라 클라우드에 **적용(apply)하지는 않지만**, 배포 가능한 구조를 코드로 갖췄다:
- **`Dockerfile`** — `$PORT`를 읽는 Cloud Run-ready 컨테이너(HF Spaces는 자체 빌드라 별도).
- **`infra/main.tf`** — BigQuery 마트 데이터셋 + Cloud Run 서비스 Terraform 정의(미적용 IaC). `infra/README.md` 참조.
- **Vertex-ready** — `app/llm.py`에 `LLM_PROVIDER=vertex` 분기. provider 무관 클라이언트라 무료 Gemini 키 ↔ Vertex AI Gemini가 **환경변수 한 줄**로 전환된다(이노션 "Vertex AI" 요구의 엔터프라이즈 경로).

> 라이브 클라우드 URL이 없는 부분은 숨기지 않는다 — "카드만 연결하면 `terraform apply`로 그대로 배포되는 구조". 무료 운영(BQ 샌드박스·HF Spaces·GitHub Actions)은 그대로 유지된다.

### 관측성 — 트레이스 → 운영 대시보드

각 요청은 JSONL로 트레이싱된다(`app/trace.py`: 성공/지연/스캔바이트/자기수정). 누적 트레이스를 운영 지표·대시보드로 집계한다(Cloud Monitoring의 무료 등가물):

```bash
python -m app.trace traces/trace.jsonl            # 요약 지표(JSON): 성공률·p50/p95·총 스캔
python -m app.trace traces/trace.jsonl --html     # 정적 HTML 대시보드 생성(무의존)
```

HTML 렌더링은 순수 함수라 오프라인 단위테스트되고(XSS 이스케이프 포함, `tests/test_trace.py`), 외부 의존성 없이 브라우저로 운영 현황을 본다.

### 의미 기반(semantic) 캐시 — 패러프레이즈도 히트

`app/semantic_cache.py`는 정확 일치를 넘어 **질의 임베딩의 코사인 유사도가 임계 이상이면 캐시 히트**시킨다. "카테고리별 매출"과 "카테고리 별 매출액"을 다른 키로 보는 정확 캐시와 달리, 패러프레이즈에도 히트해 LLM/실행 호출을 줄인다(비용·지연↓). 코사인·LRU·TTL은 순수 로직이라 오프라인 단위테스트되고(`tests/test_semantic_cache.py`), 임베더는 주입형(무료 BGE-M3/Gemini). SQL 생성 결과를 질의 *의미*로 캐싱하는 운영 옵션.

### 멀티턴 — 후속 질문이 직전 답을 기억

대화형 CLI는 세션 이력을 들고 다닌다(`app/conversation.py`). "카테고리별 매출 top5"에 이어 **"그중 상위 3개만"**처럼 단독으로는 불완전한 후속 질문을, 직전 SQL을 참고해 해석한다. 에이전트 자체는 무상태이고(`answer(..., history=...)`), 이력 렌더링은 순수 함수라 오프라인 단위테스트된다(`tests/test_conversation.py`). 무관한 새 질문이면 직전 대화를 무시하도록 프롬프트로 지시한다. `eval/run_followup_eval.py`가 **이력 있음 vs 없음**을 같은 gold 로 비교해 멀티턴의 이득을 수치화한다.

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
| `app/trace.py` | 요청별 트레이싱(JSONL) + 지표 집계 |

## 관측성 / 트레이싱

각 질문 처리를 한 줄 JSON으로 기록한다 — 생성 SQL 여부·검증/실행 성공·**스캔 바이트(비용)**·
**지연(ms)**·**자기수정 여부**. 기본은 stdout(`[trace] {...}`)이라 Hugging Face Spaces 로그에 그대로 남고,
`TRACE_FILE`을 주면 JSONL 파일로도 쌓인다. 쌓인 트레이스는 운영 지표로 집계한다.

```bash
export TRACE_FILE=traces/trace.jsonl    # 파일에도 기록(선택)
python cli.py "카테고리별 매출 top 5"
python -m app.trace traces/trace.jsonl  # 요약: 성공률·repair율·지연 p50/p95·총 스캔 MB
```
```json
{ "count": 12, "success_rate": 0.917, "repair_rate": 0.083,
  "latency_ms_p50": 1840, "latency_ms_p95": 8470, "total_mb_scanned": 41.2, "avg_rows_ok": 7.5 }
```
> "그럴듯한 답"이 아니라 **운영 가능한 답**을 목표로 — 정확도(eval)뿐 아니라 지연·비용·자기수정률을
> 요청 단위로 측정해 회귀를 감지할 수 있게 했다.

## 테스트 / CI

순수 로직(SQL 추출·조회 전용 가드·미지 컬럼 탐지·채점·트레이스 집계)을 `app/sqlutils.py`·
`app/evalutils.py`·`app/trace.py`로 분리해 네트워크·LLM·BigQuery 없이 단위 테스트한다.
GitHub Actions가 push마다 lint(ruff) + pytest를 돌린다.

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest -q          # 26 passed
```

## 대용량 데이터 — pandas vs PySpark, 연산별 크로스오버 실측 (2026-09-14)

이 프로젝트의 대용량 처리는 전부 BigQuery(관리형 SQL)를 통해서였다. Spark 자체를 붙여
"대용량 데이터(Spark 등)"를 요구하는 공고(디오 AI Platform 데이터 엔지니어 등)의 갭을
닫았다 — WSL2에 Java 17 + PySpark 3.5.3을 로컬(`local[*]`, 클러스터·클라우드 계정 불필요)로
설치해 **"Spark가 빠르다"는 막연한 주장 대신 연산 3종(groupby·join·window)마다 크로스오버
지점을 따로 쟀다.**

```bash
wsl -d Ubuntu -- ~/spark_bench/venv/bin/python tools/spark_benchmark.py
```

| 연산 | 1만행 | 100만행 | 500만행 | 2000만행 | 크로스오버 |
|---|---:|---:|---:|---:|---|
| groupby-agg (pandas/Spark) | 0.008s / 0.49s | 0.056s / 0.196s | 0.34s / **0.22s** | 1.09s / **0.55s** | 100만~500만행 사이 |
| window(7행 이동평균) | 0.006s / 0.13s | 0.230s / **0.082s** | 1.42s / **0.088s** | 5.67s / **0.060s** | **100만행부터**, 2천만행에서 94배 |
| join(3행 차원 테이블) | 0.005s / 1.22s | 0.163s / 0.87s | 0.80s / 1.43s | **3.30s** / 4.23s | 2천만행까지도 없음 |

**정직한 결론 — 연산마다 완전히 다른 곡선이다.** window 함수는 pandas의 `groupby().transform(rolling)`이
그룹마다 파이썬 레벨로 도는 구조적 약점이라 Spark의 카탈리스트 옵티마이저가 100만행부터 압도한다.
반대로 join은 상대가 3행짜리 극소 차원 테이블이라 pandas의 해시 병합이 사실상 공짜에 가깝고,
Spark의 브로드캐스트 조인은 태스크 스케줄링·직렬화 오버헤드가 2천만행에서도 상각이 안 됐다.
**"데이터가 크면 Spark"라는 일반화는 성립하지 않는다 — 크로스오버는 연산의 성격(셔플 필요
여부·상대 테이블 크기)이 결정한다.**

`spark.createDataFrame(pandas_df)`가 Python 3.12 + PySpark 3.5.x 조합에서 `distutils`
제거로 죽는 걸 발견해, 드라이버로 pandas 객체를 마샬링하는 대신 **Parquet 파일을 거쳐 읽는
방식**으로 우회했다 — 회피가 아니라 실무 ETL과 더 가까운 경로였다.

**단 로컬 `local[*]`(16코어 단일 머신) 한정이다.** 멀티노드 클러스터·YARN/K8s 스케줄링·셔플
장애·데이터가 단일 머신 메모리를 초과하는 상황(Spark가 진짜 필요해지는 지점)은 재지 않았다.
상세: `tools/spark_benchmark.py`, 지식베이스 O1~O4.

## 한계
- 다중 턴 대화·후속 질의 메모리는 없습니다(단일 질문 단위).
- gold answer match는 평가셋에 정의된 질문에 한합니다. 개방형 질문은 validity만 채점합니다.
- 임베딩은 ChromaDB 내장 모델(로컬)이라 한국어 검색 품질은 전용 임베딩(BGE-M3 등)보다 낮을 수 있습니다.
