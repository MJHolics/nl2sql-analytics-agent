# infra/ — 배포 인프라 (Terraform IaC, 미적용)

`main.tf`는 이 에이전트를 GCP에 올리는 인프라를 코드로 정의한다:

- **BigQuery 마트 데이터셋** (`build_mart.py`가 채우는 staging 뷰 + 집계 테이블이 사는 곳)
- **Cloud Run 서비스** (Dockerfile로 빌드한 컨테이너 이미지 서빙, `$PORT`=8080)
- **Vertex AI** 사용을 위한 `LLM_PROVIDER=vertex` 환경변수

## 적용하지 않는 이유 (정직한 표기)

Cloud Run·Vertex AI는 **과금 계정(신용카드) 등록**이 필요하다. 이 포트폴리오는 비용 0 원칙이라 `terraform apply`를 **하지 않는다**. 대신:

- 배포 **인프라를 코드로 정의하는 역량**(IaC)을 무료로 증명하고,
- 카드만 연결하면 그대로 적용 가능한 구조임을 보인다.

```bash
# 카드 연결 후라면:
terraform init
terraform plan  -var project_id=<id> -var image=<artifact-registry-경로>
terraform apply -var project_id=<id> -var image=<artifact-registry-경로>
```

무료 운영 경로는 그대로 유지된다 — 데이터 마트는 **BigQuery 샌드박스**(카드 불필요),
데모는 **HF Spaces**(CPU 무료), 파이프라인은 **GitHub Actions**(무료).
