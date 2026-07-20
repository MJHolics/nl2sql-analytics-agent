# Vertex/Cloud Run-ready 인프라 정의 (IaC, 미적용).
# apply는 과금 계정(카드)이 필요하므로 적용하지 않는다 — 무료로 "배포 인프라를 코드로 정의"한
# 역량을 증명하는 산출물이다. 카드만 연결하면 `terraform apply`로 그대로 배포된다.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  type        = string
  description = "쿼리를 청구할 GCP 프로젝트 id"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "mart_dataset" {
  type    = string
  default = "nl2sql_mart"
}

variable "image" {
  type        = string
  description = "에이전트 컨테이너 이미지(Artifact Registry 경로)"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 데이터 마트가 사는 데이터셋. build_mart.py가 staging 뷰 + 집계 테이블을 여기에 만든다.
resource "google_bigquery_dataset" "mart" {
  dataset_id  = var.mart_dataset
  location    = var.region
  description = "NL2SQL 분석 에이전트 데이터 마트(staging 뷰 + 집계 테이블)"
}

# 에이전트 데모를 Cloud Run으로 서빙(Dockerfile로 빌드한 이미지).
resource "google_cloud_run_v2_service" "agent" {
  name     = "nl2sql-analytics-agent"
  location = var.region

  template {
    containers {
      image = var.image
      ports {
        container_port = 8080
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      # LLM_PROVIDER=vertex 로 두면 Vertex AI Gemini를 쓴다(아래 app/llm.py 참조).
      env {
        name  = "LLM_PROVIDER"
        value = "vertex"
      }
    }
  }
}
