# PLAN — Cloud-ready 데이터 에이전트 심화 (비용 0)

> 기존 `nl2sql-analytics-agent`(로컬 + HF Spaces 데모)를 **"빌드→검증→운영(파이프라인 자동화·배포 준비·관측성)"** 풀사이클로 끌어올린다.
> **제약: 전부 무료.** 카드 등록·과금 서비스(Vertex AI/Cloud Run/Cloud Functions 라이브 배포)는 제외하고, 무료로 같은 역량을 증명한다.
> 타깃 공고: 이노션 ★★★★★(NL2SQL·BigQuery·파이프라인 자동화) 정면 + 코그니텀·뉴셀렉트(실전 배포·재사용 Agent) 강화.

---

## ① 목표·이유 — 왜 이 심화인가

공고 5건을 매칭하니 빌드(에이전트/RAG/NL2SQL)·검증(eval/가드레일)은 두텁지만 **"실전 배포·파이프라인 자동화"가 비어 있다.** 유일한 ★★★★★(이노션)의 보완점이 정확히 이것 하나였다:
> "Vertex/Cloud Run 배포로 보강하면 ★완벽. 데이터 마트 설계·파이프라인 자동화(Cloud Functions) 실전 사례 보강."

→ 이 갭을 **카드 없이(0원)** 메운다. "검증되는 에이전트"에 **"운영되는 에이전트"**를 붙여, 시장이 요구하는 *빌드→검증→실전배포* 전 주기를 한 프로젝트로 증명한다. 동시에 단일 질문 한계를 깨는 **멀티턴 메모리**를 얹어 실무 에이전트의 기본기를 채운다.

## ② 상품성 — 누가 왜 쓰나

- **사용자**: 데이터팀·현업 비분석가. 자연어로 묻고, **후속 질문**을 이어가며, 신뢰할 수 있는 데이터 마트 위에서 답을 얻는다.
- **가치(신규분)**: ① 후속질의 가능한 대화형 분석 ② 자동 갱신되는 데이터 마트(품질 보장) ③ 스케줄 파이프라인으로 사람 개입 없이 최신화 ④ 컨테이너+IaC로 즉시 배포 가능.

## ③ 무료 대체 매핑 — 카드 필요한 것을 무료로 증명

| 공고 요구 (유료 경로) | 무료 대체 | 증명되는 동일 역량 |
|---|---|---|
| BigQuery 데이터 마트 | **BigQuery 샌드박스**(카드X·월1TB무료) | 마트/뷰 계층 설계·품질관리 |
| Cloud Functions 파이프라인 자동화 | **GitHub Actions 스케줄 워크플로** | 수집→적재→마트화 자동화·스케줄링 |
| Cloud Run 서빙 | **Dockerfile + HF Spaces** | 컨테이너화·서버리스 서빙 |
| IaC(배포 인프라) | **Terraform 설정(미적용)** | IaC 작성 역량(적용 없이도 코드로 증명) |
| Vertex AI(Gemini 엔터프라이즈) | **provider 추상화에 Vertex 분기 + 문서** | "Vertex-ready 아키텍처"로 정직하게 표기 |
| 관측성(Cloud Monitoring) | **trace.py JSONL → 로컬 대시보드** | 트레이스·지연·비용 지표화 |

> 원칙: 라이브 클라우드 URL이 없는 부분은 *숨기지 않고* "카드만 등록하면 즉시 배포되는 구조"로 표기한다.

## ④ 성능 비교 (실측 계획) — 무엇을 숫자로 낼 것인가

- **멀티턴 정확도**: 후속질의 평가셋(신규) — 단일턴 대비 후속질문 해석 성공률. (예: "그중 상위 3개만" → 직전 SQL 컨텍스트 유지 성공률)
- **데이터 마트 효과**: 원본 직접 쿼리 vs 마트 경유 — 스캔 바이트·지연 비교(BigQuery 샌드박스 dry-run으로 측정, 비용 0).
- **파이프라인 자동화**: GitHub Actions 스케줄 실행 로그 — 성공률·소요시간·eval 게이트 통과 여부.
- **회귀 가드**: 기존 eval(validity/answer-match)을 CI에 묶어 파이프라인이 깨지면 잡히게.

## ⑤ 교체 기록 (예정) — 심화 과정에서 남길 의사결정

- 단일턴 → 멀티턴: 세션 상태·대화 컨텍스트 주입 방식 선택 근거.
- 원본 직접 쿼리 → 마트 경유: 마트 도입 전후 스캔/지연 비교로 정당화.
- 무료 대체 선택 근거: 왜 Cloud Functions 대신 GitHub Actions인가(0원·재현성).

## ⑥ 에러 대처 기록 (예정) — 부딪힐 것으로 예상되는 지점

- 멀티턴에서 컨텍스트 오염(직전 SQL이 무관한 후속질의에 끌려옴) → 컨텍스트 리셋/관련성 판단.
- BigQuery 샌드박스 제약(영구 테이블 생성 제한·만료) 안에서 마트 구현하는 법.
- GitHub Actions에서 GCP 인증(서비스계정 키 시크릿) 안전 처리.

## ⑦ 개발 순서 (Phase) — 작은 단위로, 각 단계 무료·측정 동반

| Phase | 작업 | 산출물 | 비용 |
|---|---|---|---|
| **P0** | 본 플랜 작성 | `PLAN_CLOUD_READY.md` | 0 |
| **P1** | **멀티턴 메모리** ✅ — `app/conversation.py`(무상태 세션·이력 렌더링 순수함수) + `agent.py` history 주입(기존 호환) + `cli.py` 대화 이력 유지 + 단위테스트 6개(32 passed) + `eval/followup_questions.yaml`(대화 4·후속질의 4) + `eval/run_followup_eval.py`(메모리 있음 vs 없음 A/B 측정) | 멀티턴 에이전트 + eval | 0 (코드) |
| **P2** | **BigQuery 마트 계층** ✅ — `mart/`(staging 뷰 4 + 집계 테이블 3 + 품질점검 DDL) + `app/mart.py`(렌더링·분리 순수함수) + `build_mart.py`(구축·품질·스캔비교 러너, `--compare` dry-run) + 단위테스트 4개(36 passed) + config.MART_DATASET | 마트 SQL + 스캔/지연 비교 | 0 (샌드박스) |
| **P3** | **파이프라인 자동화** ✅ — `.github/workflows/pipeline.yml`(매일 cron + workflow_dispatch로 마트 재적재 + 품질 게이트). 시크릿 없으면 안전 skip, LLM 불필요. ci.yml은 그대로 유지 | `.github/workflows/pipeline.yml` | 0 |
| **P4** | **배포 준비** ✅ — `Dockerfile`(Cloud Run-ready, $PORT) + `infra/main.tf`·`infra/README.md`(미적용 Terraform IaC: BQ 마트 데이터셋 + Cloud Run) + `app/llm.py` `_vertex` 분기 + config(vertex·VERTEX_LOCATION) + app.py PORT 대응 | Docker/IaC/Vertex-ready 코드 | 0 |
| **P5** | **관측성** ✅ — `app/trace.py`에 `render_html` 순수함수(무의존 HTML 대시보드) + `--html` 플래그 + 단위테스트(XSS 이스케이프 포함, 37 passed) | 운영 지표 대시보드 | 0 |
| **P6** | **서사 정리** ✅ — README에 배포준비·관측성·마트·파이프라인·멀티턴 문서화 + 카드(`01-project-cards/nl2sql-analytics-agent.md`)에 🚀 Cloud-ready 심화 섹션·스택·스위치 갱신·한계 정정(멀티턴 해결 반영) | 갱신된 카드 | 0 |

> 설계 원칙(기존 프로젝트와 동일): **작은 Phase + 각 단계에 측정/회귀 가드 동반.** 한 번에 다 만들지 않고, P1부터 하나씩.

---

## 다음 액션
**P1~P6 전부 완료 (2026-06-29).** Cloud-ready 심화 끝 — 빌드→검증→운영(마트·파이프라인·배포준비·관측) 풀사이클을 비용 0으로 구현. 단위테스트 37 passed.
실측이 필요한 부분(사용자가 무료 Gemini 키 + BQ 샌드박스로):
- `python -m eval.run_followup_eval` → 멀티턴 메모리 이득(%p)
- `python build_mart.py` → 마트 스캔 절감률
- `python -m app.trace traces/trace.jsonl --html` → 운영 대시보드
남은 선택지: ① 실측값 확보 후 카드/README에 수치 박기 ② 다른 정조준 프로젝트(inspection-copilot 등)도 동일 패턴 심화 ③ 실제 지원서 조립.
