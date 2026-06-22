# 배포 — Hugging Face Spaces (gradio)

이 레포는 `app.py`(gradio 진입점) + README 프런트매터로 **그대로 HF Spaces에 배포**된다.

## 1) Space 만들기
1. https://huggingface.co/new-space → SDK **Gradio**, 가시성 Public.
2. 로컬에서 Space를 원격으로 추가하고 푸시:
   ```bash
   git remote add space https://huggingface.co/spaces/<user>/nl2sql-analytics-agent
   git push space master:main      # Spaces 기본 브랜치는 main
   ```
   (HF 토큰으로 인증. `git push`가 비밀번호를 물으면 토큰을 붙여넣는다.)

## 2) Secret 설정 (Space → Settings → Variables and secrets)
| 키 | 필수 | 설명 |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Gemini 무료 키(aistudio.google.com) |
| `GOOGLE_CLOUD_PROJECT` | ✅ | 쿼리를 청구할 본인 GCP 프로젝트 id |
| `GCP_SA_KEY` | 실행하려면 ✅ | **서비스계정 JSON 전체를 문자열로** 붙여넣기 |

`app.py`가 시작 시 `GCP_SA_KEY`를 임시 파일로 써서 `GOOGLE_APPLICATION_CREDENTIALS`로 노출한다.
서비스계정이 없으면 앱은 로드되지만 BigQuery 호출에서 인증 오류를 **UI에 친절히 표시**한다.

## 3) BigQuery 서비스계정 키 만들기 (로컬, 1회)
원격 호스트는 로컬 gcloud ADC를 못 쓰므로 서비스계정이 필요하다.
```bash
gcloud auth login                       # 토큰 만료 시 먼저 재인증
PROJECT=<your-project-id>
gcloud config set project $PROJECT
gcloud iam service-accounts create nl2sql-demo --display-name="NL2SQL demo"
SA="nl2sql-demo@$PROJECT.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" --role="roles/bigquery.dataViewer"
gcloud iam service-accounts keys create sa.json --iam-account=$SA
# sa.json 내용 전체를 GCP_SA_KEY secret에 붙여넣고, 파일은 안전히 삭제(rm sa.json)
```
> **샌드박스 한계:** BigQuery 샌드박스 프로젝트는 서비스계정 키 발급이 막힐 수 있다.
> 막히면 결제가 연결된 GCP 프로젝트를 쓰면 된다(공개 데이터셋 쿼리는 무료 1TB/월 안에서 비용 0).

## 동작 범위
- **dry-run 모드**: SQL 생성 + 검증만(실행 X). 스키마 조회는 필요하므로 BigQuery 읽기 권한은 있어야 한다.
- **실행 모드**: 위 권한(`bigquery.jobUser` + `dataViewer`)이면 공개 데이터셋을 무료 한도로 실행한다.
