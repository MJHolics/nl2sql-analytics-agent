"""중앙 설정. 환경변수로 모두 덮어쓸 수 있다.

실행 전 필요한 것(둘 다 무료):
  1) Gemini 무료 API 키: https://aistudio.google.com → GEMINI_API_KEY
  2) BigQuery 접근: BigQuery 샌드박스 또는 GCP 프로젝트 →
     gcloud auth application-default login  +  GOOGLE_CLOUD_PROJECT
"""
from __future__ import annotations

import os


def _load_dotenv() -> None:
    """프로젝트 루트의 .env를 os.environ에 주입(이미 설정된 값은 유지). 의존성 없는 간단 파서."""
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    for raw in open(path, encoding="utf-8-sig"):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


_load_dotenv()

# --- BigQuery ---
# 쿼리를 청구할 본인 프로젝트(샌드박스 프로젝트 id도 가능). 데이터는 공개셋이라 무료 티어로 충분.
BILLING_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
# 분석 대상: thelook 이커머스 공개 데이터셋(B2C). `프로젝트.데이터셋` 형식.
SOURCE_DATASET: str = os.getenv("SOURCE_DATASET", "bigquery-public-data.thelook_ecommerce")
# dry-run에서 이 바이트를 넘기면 실행 거부(비용 가드레일). 기본 2GB.
MAX_BYTES_BILLED: int = int(os.getenv("MAX_BYTES_BILLED", str(2 * 1024**3)))

# --- LLM ---
# provider: gemini | anthropic | openai | auto(키 있는 것 자동 선택)
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
LLM_MODEL: dict[str, str] = {
    "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    "openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
}

# --- RAG 그라운딩 ---
CHROMA_DIR: str = os.getenv("CHROMA_DIR", os.path.join(os.path.dirname(__file__), ".chroma"))
RETRIEVE_TOP_K: int = int(os.getenv("RETRIEVE_TOP_K", "6"))
# 검색 최상위 거리(작을수록 유사)가 이 값보다 크면 "근거 빈약"으로 보고 경고.
LOW_GROUNDING_DISTANCE: float = float(os.getenv("LOW_GROUNDING_DISTANCE", "1.1"))
