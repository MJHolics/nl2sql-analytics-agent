"""RAG 그라운딩: 스키마 카드 + 용어사전 + 예시쿼리를 ChromaDB에 색인하고,
질문에 관련된 컨텍스트만 골라 프롬프트에 넣는다.

임베딩은 ChromaDB 내장 모델(로컬, API 키 불필요)을 사용한다.
"""
from __future__ import annotations

import os

import yaml

import config

_KN = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")


def _load_knowledge_docs() -> list[dict]:
    docs: list[dict] = []
    # 용어사전: 업무 용어 → 컬럼/정의 매핑
    terms = yaml.safe_load(open(os.path.join(_KN, "term_dictionary.yaml"), encoding="utf-8"))
    for t in terms or []:
        docs.append(
            {
                "id": f"term::{t['term']}",
                "text": f"용어 '{t['term']}': {t['definition']}",
                "meta": {"kind": "term"},
            }
        )
    # 예시 쿼리: 질문 → 검증된 SQL (few-shot 근거)
    examples = yaml.safe_load(open(os.path.join(_KN, "example_queries.yaml"), encoding="utf-8"))
    for i, ex in enumerate(examples or []):
        docs.append(
            {
                "id": f"example::{i}",
                "text": f"질문: {ex['question']}\nSQL:\n{ex['sql']}",
                "meta": {"kind": "example"},
            }
        )
    return docs


class Retriever:
    def __init__(self) -> None:
        import chromadb

        self.client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        self.col = self.client.get_or_create_collection("grounding")

    def index(self, schema_cards: list[dict]) -> None:
        """스키마 카드(동적) + 지식문서(정적)를 한 번에 색인. 멱등하게 재구축."""
        docs = schema_cards + _load_knowledge_docs()
        # 깨끗하게 재색인
        try:
            self.client.delete_collection("grounding")
        except Exception:
            pass
        self.col = self.client.get_or_create_collection("grounding")
        self.col.add(
            ids=[d["id"] for d in docs],
            documents=[d["text"] for d in docs],
            metadatas=[d["meta"] for d in docs],
        )

    def retrieve(self, question: str) -> tuple[str, float]:
        """질문에 관련된 컨텍스트 블록과 최상위 거리(근거 신뢰도)를 반환."""
        res = self.col.query(query_texts=[question], n_results=config.RETRIEVE_TOP_K)
        docs = res["documents"][0]
        dists = res["distances"][0] if res.get("distances") else [0.0] * len(docs)
        top_distance = dists[0] if dists else 1.0
        context = "\n\n".join(docs)
        return context, top_distance
