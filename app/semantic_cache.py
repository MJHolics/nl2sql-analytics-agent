"""의미 기반(semantic) 캐시 — 정확 일치를 넘어 *유사* 질의에 캐시 히트.

정확 일치 캐시는 "카테고리별 매출"과 "카테고리 별 매출액"을 다른 키로 본다. 의미 캐시는 질의
임베딩의 코사인 유사도가 임계 이상이면 캐시된 결과를 재사용 → 패러프레이즈에도 히트해 LLM/실행
호출을 줄인다(비용·지연↓). 임베더는 주입형(무료 BGE-M3/Gemini 등), 테스트는 결정적 stub.

순수 로직(코사인·LRU·TTL)이라 네트워크 없이 단위테스트된다. SQL 생성 결과를 질의 의미로
캐싱하는 데 쓴다 — `make_grounding_retriever`처럼 service와 측정이 같은 구현을 공유.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


def cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


@dataclass
class _Entry:
    vec: list[float]
    value: object
    ts: float


@dataclass
class SemanticCache:
    """코사인 유사도 ≥ threshold면 히트하는 캐시. LRU(max_size) + TTL(초) 제거.

    now_fn은 테스트에서 시계를 주입하기 위한 훅(기본 time.time).
    """

    threshold: float = 0.92
    max_size: int = 128
    ttl: float = 300.0
    now_fn: object = time.time
    _store: list[_Entry] = field(default_factory=list)
    hits: int = 0
    misses: int = 0

    def _now(self) -> float:
        return self.now_fn()

    def _evict_expired(self) -> None:
        if self.ttl <= 0:
            return
        now = self._now()
        self._store = [e for e in self._store if now - e.ts <= self.ttl]

    def get(self, query_vec: list[float]):
        """가장 유사한 캐시 항목이 임계 이상이면 그 값을, 아니면 None을 돌려준다(LRU 갱신)."""
        self._evict_expired()
        best_i, best_sim = -1, -1.0
        for i, e in enumerate(self._store):
            s = cosine(query_vec, e.vec)
            if s > best_sim:
                best_i, best_sim = i, s
        if best_i >= 0 and best_sim >= self.threshold:
            e = self._store.pop(best_i)
            e.ts = self._now()
            self._store.append(e)  # 최근 사용을 뒤로(LRU)
            self.hits += 1
            return e.value
        self.misses += 1
        return None

    def put(self, query_vec: list[float], value) -> None:
        self._evict_expired()
        self._store.append(_Entry(vec=list(query_vec), value=value, ts=self._now()))
        while len(self._store) > self.max_size:
            self._store.pop(0)  # 가장 오래 안 쓴 것 제거

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0
